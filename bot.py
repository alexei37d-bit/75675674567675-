import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# ВАЖНО: Смените токен, если вы его опубликовали!
BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WELCOME_TEXT = (
    '<tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> '
    "<b>Добро пожаловать в @wxs_gamebot</b>"
)

def main_keyboard() -> InlineKeyboardMarkup:
    # Мы создаем объекты InlineKeyboardButton, а не просто словари
    keyboard = [
        [
            InlineKeyboardButton(text="Играть", callback_data="play", request_write_access=True), # icon_custom_emoji_id лучше передавать как аргумент, если нужно
            InlineKeyboardButton(text="Чат", callback_data="chat"),
        ],
        [
            InlineKeyboardButton(text="Профиль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton(text="Правила", callback_data="rules"),
            InlineKeyboardButton(text="Помощь", callback_data="help"),
        ],
    ]
    
    # Внимание: параметр icon_custom_emoji_id в InlineKeyboardButton 
    # в aiogram 3.x передается в конструктор, но поддерживается не везде.
    # Если вы хотите передать его, делайте это внутри InlineKeyboardButton(...)
    
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

# ИСПРАВЛЕНО ЗДЕСЬ: двойные подчеркивания
if __name__ == "__main__":
    asyncio.run(main())
