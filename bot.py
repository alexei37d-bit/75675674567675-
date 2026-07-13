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

# Твой тестовый токен
BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WELCOME_TEXT = (
    '<tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> '
    "<b>Добро пожаловать в @wxs_gamebot</b>"
)


def main_keyboard() -> InlineKeyboardMarkup:
    # 1. Возвращаем кавычки (делаем str), чтобы Pydantic пропустил валидацию без ошибок
    markup = InlineKeyboardMarkup(
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
                    icon_custom_emoji_id="5870994129244131212",
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
                    icon_custom_emoji_id="6028435952299413210",
                ),
            ],
        ]
    )

    # 2. ХАК ДЛЯ TELEGRAM: Принудительно превращаем строки в числа во внутреннем JSON-объекте кнопки
    # Это обойдет баг парсинга на серверах Telegram!
    for row in markup.inline_keyboard:
        for button in row:
            if button.icon_custom_emoji_id:
                # Превращаем "12345" в 12345 прямо в словаре перед отправкой
                button.custom_fields["icon_custom_emoji_id"] = int(
                    button.icon_custom_emoji_id
                )

    return markup


@dp.message(CommandStart())
async def start_handler(message: Message):
    # Теперь и Pydantic доволен, и Telegram получит чистые числа
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
