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

# Вставь сюда токен своего бота
BOT_TOKEN = "8666251391:AAEKjitGiCOkRPpIesqUDK4jCXQUr7T-LO8"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ID премиум эмодзи (работают без Premium у бота)
# Можно использовать любые ID, найденные в интернете
CUSTOM_EMOJIS = {
    "fire": "5472419592217332357",
    "play": "5471895876790161593",
    "chat": "5235931189591710436",
    "profile": "5197514090108456970",
    "rules": "5199867405769151212",
    "help": "5199560697859577006",
}

WELCOME_TEXT = (
    f'<tg-emoji emoji-id="{CUSTOM_EMOJIS["fire"]}">🔥</tg-emoji> '
    "<b>Добро пожаловать в @wxs_gamebot</b>"
)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Играть",
                    callback_data="play",
                    icon_custom_emoji_id=CUSTOM_EMOJIS["play"],
                ),
                InlineKeyboardButton(
                    text="Чат",
                    callback_data="chat",
                    icon_custom_emoji_id=CUSTOM_EMOJIS["chat"],
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Профиль",
                    callback_data="profile",
                    icon_custom_emoji_id=CUSTOM_EMOJIS["profile"],
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Правила",
                    callback_data="rules",
                    icon_custom_emoji_id=CUSTOM_EMOJIS["rules"],
                ),
                InlineKeyboardButton(
                    text="Помощь",
                    callback_data="help",
                    icon_custom_emoji_id=CUSTOM_EMOJIS["help"],
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
