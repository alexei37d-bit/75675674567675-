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

# ID Premium эмодзи
EMOJI_IDS = {
    "home": "5257963315258204021",          # 🏘
    "play": "5258508428212445001",          # 🎮
    "chat": "5260535596941582167",          # 💬
    "profile": "5258011929993026890",       # 👤
    "rules": "5260730055880876557",         # ⛓
    "help": "5258328383183396223",          # 📖
}


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Играть",
                    callback_data="play",
                    icon_custom_emoji_id=EMOJI_IDS["play"]  # 🔥 КАСТОМНЫЙ ЭМОДЗИ В ИКОНКЕ
                ),
                InlineKeyboardButton(
                    text="Чат",
                    callback_data="chat",
                    icon_custom_emoji_id=EMOJI_IDS["chat"]
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Профиль",
                    callback_data="profile",
                    icon_custom_emoji_id=EMOJI_IDS["profile"]
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Правила",
                    callback_data="rules",
                    icon_custom_emoji_id=EMOJI_IDS["rules"]
                ),
                InlineKeyboardButton(
                    text="Помощь",
                    callback_data="help",
                    icon_custom_emoji_id=EMOJI_IDS["help"]
                ),
            ],
        ]
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🏘 <b>Добро пожаловать в @wxs_gamebot</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data.in_({"play", "chat", "profile", "rules", "help"}))
async def handle_buttons(callback: CallbackQuery):
    messages = {
        "play": "🎮 <b>Игра началась!</b>",
        "chat": "💬 <b>Открываем чат...</b>",
        "profile": "👤 <b>Твой профиль</b>",
        "rules": "⛓ <b>Правила игры</b>",
        "help": "📖 <b>Помощь</b>",
    }
    
    await callback.message.edit_text(
        messages.get(callback.data, "❓ Неизвестно"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Назад",
                    callback_data="back",
                    icon_custom_emoji_id=EMOJI_IDS["home"]
                )]
            ]
        )
    )
    await callback.answer()


@dp.callback_query(F.data == "back")
async def back_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏘 <b>Добро пожаловать в @wxs_gamebot</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
