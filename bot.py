import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)

# Твой тестовый токен
BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

# Место для будущих API ключей платежных систем
CRYPTO_BOT_API_KEY = "548204:AAZOXSPMBWOj3XO29UyRcrxpgxlzujtetPO"
XROCKET_API_KEY = "c36722e4cae191a22a9097963"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Имитация БД
USERS_DB = {}

def get_or_create_user(user_id: int, full_name: str) -> dict:
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {
            "name": full_name,
            "id": user_id,
            "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "balance": 0.0,  # Теперь баланс изначально равен 0
            "turnover": 0.0,
            "deposits": 0.0,
            "withdrawals": 0.0,
        }
    return USERS_DB[user_id]

# Текст приветствия
def get_welcome_text(name: str) -> str:
    return (
        f"🔥 <b>Добро пожаловать, {name}!</b>\n\n"
        f"🎰 <b>НОВИНКА В КАЗИНО</b>: Новая игра слот, множество исходов до х64\n\n"
        f"<blockquote>Играть – значит верить в свою интуицию! 🏆 </blockquote>"
    )

# Обычное нижнее меню (3 кнопки не инлайн)
def reply_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="Баланс"),
            KeyboardButton(text="Играть"),
            KeyboardButton(text="Меню")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Главная инлайн-клавиатура
def main_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Профиль", "callback_data": "profile"},
        ],
        [
            {"text": "Реф. программа", "callback_data": "referral"},
        ],
        [
            {"text": "Чеки", "callback_data": "checks"},
            {"text": "Топ", "callback_data": "top_players"},
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

# Клавиатура внутри профиля
def profile_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Пополнить", "callback_data": "deposit_main"},
            {"text": "Вывести", "callback_data": "withdraw_main"},
        ],
        [{"text": "Транзакции", "callback_data": "transactions"}],
        [{"text": "Настройки", "callback_data": "settings"}],
        [{"text": "< Назад", "callback_data": "back_to_main"}],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

# Выбор систем пополнения
def deposit_methods_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Crypto Bot", "callback_data": "dep_cb"},
            {"text": "xRocket", "callback_data": "dep_rocket"},
            {"text": "Stars", "callback_data": "dep_stars"},
        ],
        [
            {"text": "USDT", "callback_data": "dep_usdt"},
            {"text": "TRX", "callback_data": "dep_trx"},
            {"text": "TON", "callback_data": "dep_ton"},
        ],
        [{"text": "< Назад", "callback_data": "profile"}],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

# Выбор систем вывода
def withdraw_methods_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Crypto Bot (API)", "callback_data": "with_cb"},
            {"text": "xRocket (API)", "callback_data": "with_rocket"},
        ],
        [{"text": "< Назад", "callback_data": "profile"}],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

# Общий генератор сообщения профиля
def get_profile_message(user: dict) -> str:
    return (
        f"👤 <b>Имя:</b> {user['name']}\n"
        f"ℹ️ <b>Ваш ID:</b> <code>{user['id']}</code>\n"
        f"⏰ <b>Регистрация:</b> {user['reg_date']}\n\n"
        f"💰 <b>Баланс:</b> {user['balance']} $\n"
        f"📊 <b>Оборот:</b> {user['turnover']} $\n\n"
        f"⬇️ <b>Пополнений:</b> {user['deposits']} $\n"
        f"⬆️ <b>Выводов:</b> {user['withdrawals']} $"
    )

# --- ХЭНДЛЕРЫ ---

@dp.message(CommandStart())
async def start_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(
        get_welcome_text(message.from_user.first_name),
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )
    await message.answer("Используйте меню ниже для навигации:", reply_markup=reply_main_keyboard())

# Реакция на текстовую кнопку "Баланс"
@dp.message(F.text == "Баланс")
async def reply_balance_handler(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(
        text=get_profile_message(user),
        parse_mode="HTML",
        reply_markup=profile_keyboard()
    )

# Реакция на текстовую кнопку "Меню"
@dp.message(F.text == "Меню")
async def reply_menu_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(
        get_welcome_text(message.from_user.first_name),
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )

# Реакция на текстовую кнопку "Играть"
@dp.message(F.text == "Играть")
async def reply_play_handler(message: Message):
    await message.answer("🎰 Раздел с играми находится в разработке!")

# Инлайн Профиль
@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    await callback.message.edit_text(
        text=get_profile_message(user), 
        parse_mode="HTML", 
        reply_markup=profile_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "deposit_main")
async def deposit_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        text="💰 <b>Выберите удобный способ пополнения</b> - средства зачисляются моментально.",
        parse_mode="HTML",
        reply_markup=deposit_methods_keyboard(),
    )
    await callback.answer()

@dp.callback_query(F.data == "withdraw_main")
async def withdraw_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        text="📤 <b>Выберите метод вывода средств:</b>",
        parse_mode="HTML",
        reply_markup=withdraw_methods_keyboard(),
    )
    await callback.answer()

# Пополнение по API (клик имитирует начисление средств)
@dp.callback_query(F.data.in_({"dep_cb", "dep_rocket"}))
async def mock_deposit_process(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    amount = 10.5
    user["balance"] += amount
    user["deposits"] += amount
    method = "Crypto Bot" if callback.data == "dep_cb" else "xRocket"

    await callback.answer(
        f"✅ Тестовое пополнение через {method} на {amount}$ успешно!",
        show_alert=True,
    )
    await profile_handler(callback)

# Вывод по API (с проверкой баланса)
@dp.callback_query(F.data.in_({"with_cb", "with_rocket"}))
async def mock_withdraw_process(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    method = "Crypto Bot" if callback.data == "with_cb" else "xRocket"

    if user["balance"] <= 0:
        await callback.answer(
            f"❌ Ошибка вывода через {method}! У вас нулевой баланс.",
            show_alert=True,
        )
        return

    withdraw_amount = user["balance"]
    user["balance"] = 0.0
    user["withdrawals"] += withdraw_amount

    await callback.answer(
        f"📤 Заявка по API отправлена!\nНа {method} успешно выведено {withdraw_amount}$.",
        show_alert=True,
    )
    await profile_handler(callback)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        text=get_welcome_text(callback.from_user.first_name), 
        parse_mode="HTML", 
        reply_markup=main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.in_({"referral", "checks", "top_players", "transactions", "settings", "dep_stars", "dep_usdt", "dep_trx", "dep_ton"}))
async def silent_callback(callback: CallbackQuery):
    await callback.answer("Эта функция сейчас в разработке!", show_alert=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
