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

# НОВЫЕ ID ИЗ ТВОЕГО СООБЩЕНИЯ
EMOJI_IDS = {
    "home": "5257963315258204021",          # 🏘 (дом - вместо огня)
    "play": "5258508428212445001",          # 🎮 (играть)
    "chat": "5260535596941582167",          # 💬 (чат)
    "profile": "5258011929993026890",       # 👤 (профиль)
    "rules": "5260730055880876557",         # ⛓ (правила)
    "help": "5258328383183396223",          # 📖 (помощь)
}

WELCOME_TEXT = (
    f'<tg-emoji emoji-id="{EMOJI_IDS["home"]}">🏘</tg-emoji> '
    '<b>Добро пожаловать в @wxs_gamebot</b>'
)


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Играть",
                    callback_data="play",
                ),
                InlineKeyboardButton(
                    text="Чат",
                    callback_data="chat",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Профиль",
                    callback_data="profile",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Правила",
                    callback_data="rules",
                ),
                InlineKeyboardButton(
                    text="Помощь",
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
