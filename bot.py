import asyncio
import logging

from aiogram import Bot, Dispatcher, types

# ⚠️ Замени на свой токен
BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Текст с тегом кастомного эмодзи
WELCOME_TEXT = (
    '<tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> '
    "<b>Добро пожаловать в @wxs_gamebot</b>"
)


def main_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    # ХАК: aiogram 2.x ругается на icon_custom_emoji_id, поэтому мы
    # создаем обычные кнопки, а затем принудительно дописываем
    # этот параметр прямо в их внутренний словарь (.to_python())

    btn_play = types.InlineKeyboardButton(text="Играть", callback_data="play")
    btn_play["icon_custom_emoji_id"] = "5471895876790161593"

    btn_chat = types.InlineKeyboardButton(text="Чат", callback_data="chat")
    btn_chat["icon_custom_emoji_id"] = "5235931189591710436"

    btn_profile = types.InlineKeyboardButton(
        text="Профиль", callback_data="profile"
    )
    btn_profile["icon_custom_emoji_id"] = "5197514090108456970"

    btn_rules = types.InlineKeyboardButton(text="Правила", callback_data="rules")
    btn_rules["icon_custom_emoji_id"] = "5199867405769151212"

    btn_help = types.InlineKeyboardButton(text="Помощь", callback_data="help")
    btn_help["icon_custom_emoji_id"] = "5199560697859577006"

    # Добавляем модифицированные кнопки в клавиатуру
    keyboard.add(btn_play, btn_chat)
    keyboard.add(btn_profile)
    keyboard.add(btn_rules, btn_help)

    return keyboard


# Хэндлер команды /start
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# Заглушка для кнопок
@dp.callback_query_handler(
    lambda c: c.data in {"play", "chat", "profile", "rules", "help"}
)
async def silent_callback(callback: types.types.CallbackQuery):
    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
