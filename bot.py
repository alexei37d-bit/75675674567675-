import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

BOT_TOKEN = "8666251391:AAEKjitGiCOkRPpIesqUDK4jCXQUr7T-LO8"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WELCOME_TEXT = (
    '<tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> '
    '<b>Добро пожаловать в @wxs_gamebot</b>'
)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='<tg-emoji emoji-id="5471895876790161593">🎮</tg-emoji> Играть',
                    callback_data="play",
                ),
                InlineKeyboardButton(
                    text='<tg-emoji emoji-id="5235931189591710436">💬</tg-emoji> Чат',
                    callback_data="chat",
                ),
            ],
            [
                InlineKeyboardButton(
                    text='<tg-emoji emoji-id="5197514090108456970">👤</tg-emoji> Профиль',
                    callback_data="profile",
                ),
            ],
            [
                InlineKeyboardButton(
                    text='<tg-emoji emoji-id="5199867405769151212">🛡</tg-emoji> Правила',
                    callback_data="rules",
                ),
                InlineKeyboardButton(
                    text='<tg-emoji emoji-id="5199560697859577006">⚙️</tg-emoji> Помощь',
                    callback_data="help",
                ),
            ],
        ]
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data.in_({"play", "chat", "profile", "rules", "help"}))
async def silent_callback(callback: CallbackQuery):
    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
