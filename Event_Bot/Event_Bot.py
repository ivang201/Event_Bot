import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram import F
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, Boolean, select, insert, update
from config_reader import config
from sqlalchemy.exc import IntegrityError
from typing import AsyncGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = config.DATABASE_URL.get_secret_value()

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    is_authorized = Column(Boolean, default=False)

class AuthCode(Base):
    __tablename__ = 'auth_codes'
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False)

bot = Bot(token=config.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())

def get_main_menu(is_authorized: bool) -> ReplyKeyboardMarkup:
    keyboard_builder = ReplyKeyboardBuilder()
    
    keyboard_builder.add(
        KeyboardButton(text="Speakers"),
        KeyboardButton(text="Networking"),
    )
    
    keyboard_builder.add(
        KeyboardButton(text="Information"),
        KeyboardButton(text="Agenda"),
    )
    
    keyboard_builder.add(
        KeyboardButton(text="Sign In")
    )
    
    return keyboard_builder.as_markup(resize_keyboard=True)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id

    async with SessionLocal() as session:
        result = await session.execute(select(User).filter_by(telegram_id=user_id))
        user = result.scalars().first()
        is_authorized = user.is_authorized if user else False
    
    await message.answer(
        "Welcome! Please select an option from the menu:",
        reply_markup=get_main_menu(is_authorized)
    )

@dp.message(F.text == "Speakers")
async def speakers_handler(message: types.Message):
    user_id = message.from_user.id

    async with SessionLocal() as session:
        result = await session.execute(select(User).filter_by(telegram_id=user_id))
        user = result.scalars().first()

        if not user or not user.is_authorized:
            await message.answer("You need to be authorized to access this section.")
        else:
            await message.answer("List of speakers: ...")

@dp.message(F.text == "Networking")
async def networking_handler(message: types.Message):
    user_id = message.from_user.id

    async with SessionLocal() as session:
        result = await session.execute(select(User).filter_by(telegram_id=user_id))
        user = result.scalars().first()

        if not user or not user.is_authorized:
            await message.answer("You need to be authorized to access Networking.")
        else:
            await message.answer("Networking section: ...")

@dp.message(F.text == "Information")
async def information_handler(message: types.Message):
    await message.answer("Here is some information about the event...")

@dp.message(F.text == "Agenda")
async def agenda_handler(message: types.Message):
    await message.answer("Here is the event agenda...")

@dp.message(F.text == "Sign In")
async def sign_in_handler(message: types.Message):
    await message.answer("Please enter your unique code to sign in:")

@dp.message(F.text.regexp(r"^\d{4}$"))
async def auth_code_handler(message: types.Message):
    user_code = message.text
    user_id = message.from_user.id

    logger.info(f"Received auth code {user_code} from user {user_id}")

    async with SessionLocal() as session:
        try:
            result = await session.execute(select(AuthCode).filter_by(code=user_code))
            auth_code = result.scalars().first()

            if auth_code:
                result = await session.execute(select(User).filter_by(telegram_id=user_id))
                user = result.scalars().first()

                if user:
                    stmt = update(User).where(User.telegram_id == user_id).values(is_authorized=True)
                    await session.execute(stmt)
                else:
                    stmt = insert(User).values(telegram_id=user_id, is_authorized=True)
                    await session.execute(stmt)

                await session.commit()
                logger.info(f"User {user_id} authorized successfully.")
                await message.answer("Authorization successful!", reply_markup=get_main_menu(is_authorized=True))
            else:
                logger.info(f"Invalid code {user_code} for user {user_id}.")
                await message.answer("Invalid code. Please try again.")
        except IntegrityError as e:
            logger.error(f"IntegrityError during authorization: {e}")
            await session.rollback()
            await message.answer("User is already authorized.")
        except Exception as e:
            logger.error(f"Error during authorization: {e}")
            await session.rollback()
            await message.answer("An error occurred. Please try again later.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())



