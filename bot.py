import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WELCOME_TEXT = (
    '<tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> '
    "<b>Добро пожаловать в @wxs_gamebot</b>"
)

# ID кастомных эмодзи передаём как строки прямо в emoji
def main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="Играть",
                callback_data="play",
                emoji="5471895876790161593",
            ),
            InlineKeyboardButton(
                text="Чат",
                callback_data="chat",
                emoji="5235931189591710436",
            ),
        ],
        [
            InlineKeyboardButton(
                text="Профиль",
                callback_data="profile",
                emoji="5870994129244131212",
            )
        ],
        [
            InlineKeyboardButton(
                text="Правила",
                callback_data="rules",
                emoji="5199867405769151212",
            ),
            InlineKeyboardButton(
                text="Помощь",
                callback_data="help",
                emoji="6028435952299413210",
            ),
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
    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
