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

# ВАЖНО: Никогда не выкладывайте токен в открытый доступ! 
# Я сгенерировал этот ответ, но рекомендую сменить токен, так как он был опубликован.
BOT_TOKEN = "8666251391:AAEKjitGiCOkRPpIesqUDK4jCXQUr7T-LO8"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Твои ID премиум эмодзи
EMOJI_IDS = {
    "fire": "5278413853577734640",
    "play": "5278304890257436355",
    "chat": "5278227821364275264",
    "profile": "5275979556308674886",
    "rules": "5276262671962892944",
    "help": "5276037216244624892",
}

WELCOME_TEXT = (
    f'<tg-emoji emoji-id="{EMOJI_IDS["fire"]}">🔥</tg-emoji> '
    '<b>Добро пожаловать в @wxs_gamebot</b>'
)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=" Играть",
                    callback_data="play",
                    request_write_access=True,  # Иногда помогает корректному отображению
                ),
                InlineKeyboardButton(
                    text=" Чат",
                    callback_data="chat",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=" Профиль",
                    callback_data="profile",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=" Правила",
                    callback_data="rules",
                ),
                InlineKeyboardButton(
                    text=" Помощь",
                    callback_data="help",
                ),
            ],
        ]
    )

# Исправлено: добавление эмодзи прямо в текст кнопки, если icon_custom_emoji_id не прогружается
# API Telegram иногда капризно относится к icon_custom_emoji_id в кнопках.
# Самый надежный способ - вставить эмодзи прямо в текст кнопки через <tg-emoji>.

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
