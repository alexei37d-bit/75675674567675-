import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

BOT_TOKEN = "8666251391:AAEKjitGiCOkRPpIesqUDK4jCXQUr7T-LO8"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Исправлено: внешние кавычки изменены на одинарные, чтобы внутренние двойные не ломали синтаксис
WELCOME_TEXT = (
    '<b> <tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать в @wxs_gamebot</b>'
)

def main_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {
                "text": "Играть",
                "callback_data": "play",
                "icon_custom_emoji_id": "5471895876790161593",
            },
            {
                "text": "Чат",
                "callback_data": "chat",
                "icon_custom_emoji_id": "5235931189591710436",
            },
        ],
        [
            {
                "text": "Профиль",
                "callback_data": "profile",
                "icon_custom_emoji_id": "5870994129244131212",
            }
        ],
        [
            {
                "text": "Правила",
                "callback_data": "rules",
                "icon_custom_emoji_id": "5199867405769151212",
            },
            {
                "text": "Помощь",
                "callback_data": "help",
                "icon_custom_emoji_id": "6028435952299413210",
            },
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

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
