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


def premium_emoji(emoji_id: str, fallback: str = "❓") -> str:
    """Создает премиум эмодзи с фолбэком"""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{premium_emoji(EMOJI_IDS['play'], '🎮')} Играть",
                    callback_data="play",
                ),
                InlineKeyboardButton(
                    text=f"{premium_emoji(EMOJI_IDS['chat'], '💬')} Чат",
                    callback_data="chat",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{premium_emoji(EMOJI_IDS['profile'], '👤')} Профиль",
                    callback_data="profile",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{premium_emoji(EMOJI_IDS['rules'], '⛓')} Правила",
                    callback_data="rules",
                ),
                InlineKeyboardButton(
                    text=f"{premium_emoji(EMOJI_IDS['help'], '📖')} Помощь",
                    callback_data="help",
                ),
            ],
        ]
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    welcome = (
        f'{premium_emoji(EMOJI_IDS["home"], "🏘")} '
        '<b>Добро пожаловать в @wxs_gamebot</b>\n\n'
        'Выбери действие:'
    )
    await message.answer(
        welcome,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data.in_({"play", "chat", "profile", "rules", "help"}))
async def handle_buttons(callback: CallbackQuery):
    messages = {
        "play": f'{premium_emoji(EMOJI_IDS["play"], "🎮")} <b>Игра началась!</b>',
        "chat": f'{premium_emoji(EMOJI_IDS["chat"], "💬")} <b>Открываем чат...</b>',
        "profile": f'{premium_emoji(EMOJI_IDS["profile"], "👤")} <b>Твой профиль</b>',
        "rules": f'{premium_emoji(EMOJI_IDS["rules"], "⛓")} <b>Правила игры</b>',
        "help": f'{premium_emoji(EMOJI_IDS["help"], "📖")} <b>Помощь</b>',
    }
    
    await callback.message.edit_text(
        messages.get(callback.data, "❓ Неизвестно"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{premium_emoji(EMOJI_IDS['home'], '🏘')} Назад",
                    callback_data="back"
                )]
            ]
        )
    )
    await callback.answer()


@dp.callback_query(F.data == "back")
async def back_handler(callback: CallbackQuery):
    welcome = (
        f'{premium_emoji(EMOJI_IDS["home"], "🏘")} '
        '<b>Добро пожаловать в @wxs_gamebot</b>\n\n'
        'Выбери действие:'
    )
    await callback.message.edit_text(
        welcome,
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()


@dp.message()
async def check_emoji(message: Message):
    # Проверка всех ID
    if message.text and message.text.startswith('/check'):
        result = "Проверка Premium эмодзи:\n\n"
        for name, emoji_id in EMOJI_IDS.items():
            test_text = f'{premium_emoji(emoji_id, "❓")} {name}: <code>{emoji_id}</code>'
            await message.answer(test_text, parse_mode="HTML")
            result += f"✅ {name}: {emoji_id}\n"
        await message.answer("✅ Все эмодзи отправлены!")
        return
    
    # Если прислали эмодзи - показываем его ID
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                await message.reply(
                    f"✅ ID этого Premium эмодзи:\n"
                    f"<code>{entity.custom_emoji_id}</code>",
                    parse_mode="HTML"
                )
                return


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
