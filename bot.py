import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CustomEmoji,
)

BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"  # обязательно замените!

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WELCOME_TEXT = (
    '<tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> '
    "<b>Добро пожаловать в @wxs_gamebot</b>"
)

# Создаём объекты CustomEmoji для нужных ID
EMOJI_PLAY = CustomEmoji(custom_emoji_id="5471895876790161593")
EMOJI_CHAT = CustomEmoji(custom_emoji_id="5235931189591710436")
EMOJI_PROFILE = CustomEmoji(custom_emoji_id="5870994129244131212")
EMOJI_RULES = CustomEmoji(custom_emoji_id="5199867405769151212")
EMOJI_HELP = CustomEmoji(custom_emoji_id="6028435952299413210")


def main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Играть", callback_data="play", emoji=EMOJI_PLAY),
            InlineKeyboardButton(text="Чат", callback_data="chat", emoji=EMOJI_CHAT),
        ],
        [InlineKeyboardButton(text="Профиль", callback_data="profile", emoji=EMOJI_PROFILE)],
        [
            InlineKeyboardButton(text="Правила", callback_data="rules", emoji=EMOJI_RULES),
            InlineKeyboardButton(text="Помощь", callback_data="help", emoji=EMOJI_HELP),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data.in_({"play", "chat", "profile", "rules", "help"}))
async def silent_callback(callback: CallbackQuery):
    # Здесь можно добавить логику, пока просто подтверждаем нажатие
    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
