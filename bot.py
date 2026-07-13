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

# ⚠️ Не забудь вставить свой актуальный токен бота сюда
BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

logging.basicConfig(level=logging.INFO)

# В aiogram 3.x они создаются именно так отдельными объектами:
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Текст приветствия с премиум-эмодзи
WELCOME_TEXT = (
    '<tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> '
    "<b>Добро пожаловать в @wxs_gamebot</b>"
)


def main_keyboard() -> InlineKeyboardMarkup:
    # Теперь icon_custom_emoji_id поддерживается официально и без костылей!
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Играть",
                    callback_data="play",
                    icon_custom_emoji_id="5471895876790161593",
                ),
                InlineKeyboardButton(
                    text="Чат",
                    callback_data="chat",
                    icon_custom_emoji_id="5235931189591710436",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Профиль",
                    callback_data="profile",
                    icon_custom_emoji_id="5197514090108456970",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Правила",
                    callback_data="rules",
                    icon_custom_emoji_id="5199867405769151212",
                ),
                InlineKeyboardButton(
                    text="Помощь",
                    callback_data="help",
                    icon_custom_emoji_id="5199560697859577006",
                ),
            ],
        ]
    )


# Синтаксис aiogram 3.x для команды /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# Обработчик кнопок через магический фильтр F
@dp.callback_query(F.data.in_({"play", "chat", "profile", "rules", "help"}))
async def silent_callback(callback: CallbackQuery):
    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
