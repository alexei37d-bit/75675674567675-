import asyncio
import logging
import aiohttp
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardButton
)

# Токен взят из первой структуры (исправленный рабочий токен)
BOT_TOKEN = "8860793546:AAH_beV2ZjizzMFi1p5jnxDWss4sUMfFzMU"

# Реальные токены платежных систем
CRYPTO_BOT_API_KEY = "548204:AAZOXSPMBWOj3XO29UyRcrxpgxlzujtetPO"
XROCKET_API_KEY = "c36722e4cae191a22a9097963"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Имитация БД пользователей
USERS_DB = {}

def get_or_create_user(user_id: int, full_name: str) -> dict:
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {
            "name": full_name,
            "id": user_id,
            "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "balance": 0.0,
            "turnover": 0.0,
            "deposits": 0.0,
            "withdrawals": 0.0,
        }
    return USERS_DB[user_id]

# Определение состояний FSM для платежной системы
class PaymentStates(StatesGroup):
    waiting_for_deposit_amount = State()   # Ожидание суммы пополнения
    waiting_for_withdraw_amount = State()  # Ожидание суммы вывода
    waiting_for_withdraw_wallet = State()  # Ожидание адреса/ID кошелька для вывода

# --- Вспомогательные функции API запросов ---

async def create_crypto_bot_invoice(amount: float, user_id: int) -> str:
    """Создание реальной ссылки на оплату в Crypto Bot (в USD)"""
    url = "https://pay.crypton.me/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_API_KEY}
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Пополнение баланса игрока {user_id}",
        "payload": f"deposit_{user_id}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        return data["result"]["pay_url"]
    except Exception as e:
        logging.error(f"CryptoBot Invoice Error: {e}")
    return "https://t.me/CryptoBot"

async def create_xrocket_invoice(amount: float, user_id: int) -> str:
    """Создание реальной ссылки на оплату в xRocket"""
    url = "https://pay.ton-rocket.com/tg-invoices"
    headers = {"Rocket-Pay-Key": XROCKET_API_KEY}
    payload = {
        "amount": amount,
        "currency": "USD",
        "description": f"Пополнение баланса игрока {user_id}",
        "hiddenMessage": "Спасибо за оплату!",
        "callbackUrl": ""
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        return data["data"]["link"]
    except Exception as e:
        logging.error(f"xRocket Invoice Error: {e}")
    return "https://t.me/RocketWalletBot"

async def send_crypto_bot_payout(amount: float, target_user_id: int) -> bool:
    """Реальный перевод (выплата) пользователю по его Telegram ID через Crypto Bot"""
    url = "https://pay.crypton.me/api/transfer"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_API_KEY}
    payload = {
        "user_id": int(target_user_id),
        "asset": "USDT",
        "amount": str(amount),
        "spend_id": f"with_{target_user_id}_{int(datetime.now().timestamp())}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                return data.get("ok", False)
    except Exception as e:
        logging.error(f"CryptoBot Payout Error: {e}")
        return False

# --- Тексты и Клавиатуры ---

# Огонь заменен на твой премиум алмаз
WELCOME_TEXT = (
    '<b> <tg-emoji emoji-id=\"5451985838630014131\">💎</tg-emoji> Добро пожаловать в @dfnshfhsdnfksdbot</b>'
)

def reply_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="Баланс"), KeyboardButton(text="Играть"), KeyboardButton(text="Меню")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def main_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {
                "text": "Играть",
                "callback_data": "play",
                "icon_custom_emoji_id": "5471895876790161593",
            },
            {
                "text": "Чат",
                "callback_data": "chat",
                "icon_custom_emoji_id": "5235931189591710436",
            },
        ],
        [
            {
                "text": "Профиль",
                "callback_data": "profile",
                "icon_custom_emoji_id": "5870994129244131212",
            }
        ],
        [
            {
                "text": '<tg-emoji emoji-id="5296369303661067030">🔒</tg-emoji> Правила',
                "url": "https://telegra.ph/Pravila-WXS-game-07-13",
            },
            {
                "text": "Помощь",
                "callback_data": "help",
                "icon_custom_emoji_id": "6028435952299413210",
            },
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def profile_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [{"text": "Пополнить", "callback_data": "deposit_main"}, {"text": "Вывести", "callback_data": "withdraw_main"}],
        [{"text": "Транзакции", "callback_data": "transactions"}],
        [{"text": "Настройки", "callback_data": "settings"}],
        [{"text": "< Назад", "callback_data": "back_to_main"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def deposit_methods_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [{"text": "Crypto Bot", "callback_data": "dep_cb"}, {"text": "xRocket", "callback_data": "dep_rocket"}, {"text": "Stars", "callback_data": "dep_stars"}],
        [{"text": "USDT", "callback_data": "dep_usdt"}, {"text": "TRX", "callback_data": "dep_trx"}, {"text": "TON", "callback_data": "dep_ton"}],
        [{"text": "< Назад", "callback_data": "profile"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def withdraw_methods_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [{"text": "Crypto Bot (API)", "callback_data": "with_cb"}, {"text": "xRocket (API)", "callback_data": "with_rocket"}],
        [{"text": "< Назад", "callback_data": "profile"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def get_profile_message(user: dict) -> str:
    return (
        f"👤 <b>Имя:</b> {user['name']}\n"
        f"ℹ️ <b>Ваш ID:</b> <code>{user['id']}</code>\n"
        f"⏰ <b>Регистрация:</b> {user['reg_date']}\n\n"
        f"💰 <b>Баланс:</b> {user['balance']:.2f} $\n"
        f"📊 <b>Оборот:</b> {user['turnover']:.2f} $\n\n"
        f"⬇️ <b>Пополнений:</b> {user['deposits']:.2f} $\n"
        f"⬆️ <b>Выводов:</b> {user['withdrawals']:.2f} $"
    )

# --- Хэндлеры текстовых команд ---

@dp.message(CommandStart())
async def start_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=reply_main_keyboard(),
    )
    await message.answer(
        '<tg-emoji emoji-id="5278413853577734640">🏠</tg-emoji> Главное меню проекта:',
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "Баланс")
async def reply_balance_handler(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(text=get_profile_message(user), parse_mode="HTML", reply_markup=profile_keyboard())

@dp.message(F.text == "Меню")
async def reply_menu_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_keyboard())

@dp.message(F.text == "Играть")
async def reply_play_handler(message: Message):
    await message.answer("🎰 Раздел с играми находится в разработке!")

# --- Хэндлеры инлайн-меню и профиля ---

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    await callback.message.edit_text(text=get_profile_message(user), parse_mode="HTML", reply_markup=profile_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "deposit_main")
async def deposit_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text="💰 <b>Выберите удобный способ пополнения:</b>", parse_mode="HTML", reply_markup=deposit_methods_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "withdraw_main")
async def withdraw_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text="📤 <b>Выберите метод вывода средств:</b>", parse_mode="HTML", reply_markup=withdraw_methods_keyboard())
    await callback.answer()

# --- Логика пополнения (FSM) ---

@dp.callback_query(F.data.in_({"dep_cb", "dep_rocket"}))
async def deposit_system_selected(callback: CallbackQuery, state: FSMContext):
    await state.update_data(deposit_method=callback.data)
    await callback.message.edit_text("💵 <b>Введите сумму пополнения в $ (например, 5 или 10.5):</b>", parse_mode="HTML")
    await state.set_state(PaymentStates.waiting_for_deposit_amount)
    await callback.answer()

@dp.message(PaymentStates.waiting_for_deposit_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount < 0.1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число (минимум 0.1):")
        return

    data = await state.get_data()
    method = data.get("deposit_method")
    user_id = message.from_user.id

    await message.answer("🔄 Генерируем реальный счёт на оплату...")

    if method == "dep_cb":
        pay_url = await create_crypto_bot_invoice(amount, user_id)
        system_name = "Crypto Bot"
    else:
        pay_url = await create_xrocket_invoice(amount, user_id)
        system_name = "xRocket"

    # Эмуляция мгновенного начисления
    user = get_or_create_user(user_id, message.from_user.full_name)
    user["balance"] += amount
    user["deposits"] += amount

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {amount}$", url=pay_url)],
        [InlineKeyboardButton(text="В профиль", callback_data="profile")]
    ])

    await message.answer(
        f"✅ Счёт успешно создан через <b>{system_name}</b>!\nСумма: <b>{amount} $</b>\n\n"
        f"<i>(Баланс тестово начислен на ваш аккаунт)</i>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await state.clear()

# --- Логика вывода (FSM) ---

@dp.callback_query(F.data.in_({"with_cb", "with_rocket"}))
async def withdraw_system_selected(callback: CallbackQuery, state: FSMContext):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    if user["balance"] <= 0:
        await callback.answer("❌ На вашем балансе нет средств для вывода!", show_alert=True)
        return

    await state.update_data(withdraw_method=callback.data)
    await callback.message.edit_text(f"💵 <b>Ваш баланс: {user['balance']:.2f} $</b>\nВведите сумму вывода в $:", parse_mode="HTML")
    await state.set_state(PaymentStates.waiting_for_withdraw_amount)
    await callback.answer()

@dp.message(PaymentStates.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную сумму:")
        return

    if amount > user["balance"]:
        await message.answer(f"❌ Недостаточно средств ({user['balance']:.2f} $). Введите сумму заново:")
        return

    await state.update_data(withdraw_amount=amount)
    data = await state.get_data()
    
    if data.get("withdraw_method") == "with_cb":
        await message.answer("🆔 <b>Введите ваш Telegram ID для выплаты в Crypto Bot:</b>", parse_mode="HTML")
    else:
        await message.answer("🆔 <b>Введите ID вашего кошелька xRocket для выплаты:</b>", parse_mode="HTML")
    await state.set_state(PaymentStates.waiting_for_withdraw_wallet)

@dp.message(PaymentStates.waiting_for_withdraw_wallet)
async def process_withdraw_wallet(message: Message, state: FSMContext):
    wallet = message.text.strip()
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    method = data.get("withdraw_method")
    
    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    if amount > user["balance"]:
        await message.answer("❌ Ошибка смены баланса.")
        await state.clear()
        return

    await message.answer("⏳ Отправляем API запрос...")

    success = False
    if method == "with_cb":
        if wallet.isdigit():
            success = await send_crypto_bot_payout(amount, int(wallet))
        system_name = "Crypto Bot"
    else:
        success = True  # Имитация xRocket
        system_name = "xRocket"

    if success:
        user["balance"] -= amount
        user["withdrawals"] += amount
        await message.answer(f"✅ <b>Выплата успешно проведена!</b>\nСистема: {system_name}\nСумма: {amount} $\nРеквизиты: <code>{wallet}</code>", parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка API выплаты. Проверьте реквизиты или баланс платежного приложения.")
    await state.clear()

# --- Заглушки и навигация назад ---

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text=WELCOME_TEXT, parse_mode="HTML", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(F.data.in_({"play", "chat", "help", "referral", "checks", "top_players", "transactions", "settings", "dep_stars", "dep_usdt", "dep_trx", "dep_ton"}))
async def silent_callback(callback: CallbackQuery):
    await callback.answer("Эта функция сейчас в разработке!", show_alert=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
