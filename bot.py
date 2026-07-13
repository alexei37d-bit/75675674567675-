import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, MessageEntity,
)

BOT_TOKEN = "8860793546:AAFd2zuBMwPy4d-erg_BVg0EcOBdz1rtoLs"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WELCOME_TEXT = "🔥 Добро пожаловать в @wxs_gamebot"


def main_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="Играть", callback_data="play", icon_custom_emoji_id="5471895876790161593"),
            InlineKeyboardButton(text="Чат", callback_data="chat", icon_custom_emoji_id="5235931189591710436"),
        ],
        [
            InlineKeyboardButton(text="Профиль", callback_data="profile", icon_custom_emoji_id="5870994129244131212"),
        ],
        [
            InlineKeyboardButton(text="Правила", callback_data="rules", icon_custom_emoji_id="5199867405769151212"),
            InlineKeyboardButton(text="Помощь", callback_data="help", icon_custom_emoji_id="6028435952299413210"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


@dp.message(CommandStart())
async def start_handler(message: Message):
    emoji_u16 = _utf16_len("🔥")  # 2 — surrogate pair
    bold_offset = emoji_u16 + 1   # after "🔥 "
    bold_text = WELCOME_TEXT[2:]
    entities = [
        MessageEntity(type="custom_emoji", offset=0, length=emoji_u16, custom_emoji_id="5472419592217332357"),
        MessageEntity(type="bold", offset=bold_offset, length=_utf16_len(bold_text)),
    ]
    await message.answer(
        WELCOME_TEXT,
        entities=entities,
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
