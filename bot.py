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

# ПРАВИЛЬНЫЕ ID ИЗ ТВОЕГО HTML
EMOJI_IDS = {
    "fire": "5206476089127372379",          # 🔥 (звезда)
    "play": "5278304890257436355",          # 🎮
    "chat": "5278227821364275264",          # 📁 (файл)
    "profile": "5275979556308674886",       # 👤
    "rules": "5276262671962892944",         # 🛡
    "help": "5276037216244624892",          # 💼
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


# ДОБАВЛЯЮ ОБРАБОТЧИК ДЛЯ ПРОВЕРКИ ТВОИХ ID
@dp.message()
async def check_emoji(message: Message):
    """Отправь боту ID или эмодзи для проверки"""
    if message.text and message.text.startswith('/check'):
        # Проверяем каждый ID
        result = "Проверка твоих ID:\n\n"
        for name, emoji_id in EMOJI_IDS.items():
            # Пробуем отправить эмодзи с этим ID
            try:
                test_text = f'<tg-emoji emoji-id="{emoji_id}">❓</tg-emoji> {name}'
                await message.answer(test_text, parse_mode="HTML")
                result += f"✅ {name}: {emoji_id} - работает\n"
            except:
                result += f"❌ {name}: {emoji_id} - НЕ РАБОТАЕТ\n"
        await message.answer(result)
    
    # Если отправлен эмодзи - показываем его ID
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                await message.reply(
                    f"✅ ID этого эмодзи:\n"
                    f"<code>{entity.custom_emoji_id}</code>\n\n"
                    f"Скопируй и вставь в словарь EMOJI_IDS",
                    parse_mode="HTML"
                )
                return


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
