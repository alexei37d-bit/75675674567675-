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
    # ПРАВИЛЬНЫЙ СПОСОБ - через tg-emoji в HTML
    welcome_text = f"""<b><tg-emoji emoji-id="{EMOJI_IDS['home']}">🏘</tg-emoji> Добро пожаловать, {message.from_user.first_name}!</b>

<tg-emoji emoji-id="{EMOJI_IDS['play']}">🎮</tg-emoji> <b>Играй</b> - участвуй в играх и соревнованиях
<tg-emoji emoji-id="{EMOJI_IDS['chat']}">💬</tg-emoji> <b>Общайся</b> - общайся с другими игроками
<tg-emoji emoji-id="{EMOJI_IDS['profile']}">👤</tg-emoji> <b>Профиль</b> - смотри свою статистику
<tg-emoji emoji-id="{EMOJI_IDS['rules']}">⛓</tg-emoji> <b>Правила</b> - узнай правила игры
<tg-emoji emoji-id="{EMOJI_IDS['help']}">📖</tg-emoji> <b>Помощь</b> - получи помощь

<i>Выбери действие ниже:</i>"""

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data.in_({"play", "chat", "profile", "rules", "help"}))
async def handle_buttons(callback: CallbackQuery):
    messages = {
        "play": f"""<tg-emoji emoji-id="{EMOJI_IDS['play']}">🎮</tg-emoji> <b>Игра началась!</b>

Выбери режим игры и начни соревноваться!""",
        "chat": f"""<tg-emoji emoji-id="{EMOJI_IDS['chat']}">💬</tg-emoji> <b>Общий чат</b>

Здесь ты можешь общаться с другими игроками.""",
        "profile": f"""<tg-emoji emoji-id="{EMOJI_IDS['profile']}">👤</tg-emoji> <b>Твой профиль</b>

Имя: {callback.from_user.first_name}
ID: {callback.from_user.id}""",
        "rules": f"""<tg-emoji emoji-id="{EMOJI_IDS['rules']}">⛓</tg-emoji> <b>Правила игры</b>

1. Будь вежливым
2. Не спамить
3. Наслаждайся игрой!""",
        "help": f"""<tg-emoji emoji-id="{EMOJI_IDS['help']}">📖</tg-emoji> <b>Помощь</b>

Если у тебя возникли вопросы - напиши @support"""
    }
    
    await callback.message.edit_text(
        messages.get(callback.data, "❓ Неизвестная команда"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ]
        )
    )
    await callback.answer()


@dp.callback_query(F.data == "back")
async def back_handler(callback: CallbackQuery):
    welcome_text = f"""<b><tg-emoji emoji-id="{EMOJI_IDS['home']}">🏘</tg-emoji> Добро пожаловать, {callback.from_user.first_name}!</b>

<tg-emoji emoji-id="{EMOJI_IDS['play']}">🎮</tg-emoji> <b>Играй</b> - участвуй в играх и соревнованиях
<tg-emoji emoji-id="{EMOJI_IDS['chat']}">💬</tg-emoji> <b>Общайся</b> - общайся с другими игроками
<tg-emoji emoji-id="{EMOJI_IDS['profile']}">👤</tg-emoji> <b>Профиль</b> - смотри свою статистику
<tg-emoji emoji-id="{EMOJI_IDS['rules']}">⛓</tg-emoji> <b>Правила</b> - узнай правила игры
<tg-emoji emoji-id="{EMOJI_IDS['help']}">📖</tg-emoji> <b>Помощь</b> - получи помощь

<i>Выбери действие ниже:</i>"""

    await callback.message.edit_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()


# Проверка ID
@dp.message()
async def check_emoji(message: Message):
    if message.text and message.text.startswith('/check'):
        result = "Проверка Premium эмодзи:\n\n"
        for name, emoji_id in EMOJI_IDS.items():
            test_text = f'<tg-emoji emoji-id="{emoji_id}">❓</tg-emoji> {name}: <code>{emoji_id}</code>'
            await message.answer(test_text, parse_mode="HTML")
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
