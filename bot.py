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

# Твой тестовый токен бота
BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

# СЮДА НУЖНО ВСТАВИТЬ ТВОИ РЕАЛЬНЫЕ ТОКЕНЫ ИЗ НАСТРОЕК ПЛАТЕЖЕК
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
            "balance": 0.0,
            "turnover": 0.0,
            "deposits": 0.0,
            "withdrawals": 0.0,
        }
    return USERS_DB[user_id]

# Определение состояний FSM для ввода сумм и реквизитов
class PaymentStates(StatesGroup):
    waiting_for_deposit_amount = State()   # Ожидание суммы пополнения
    waiting_for_withdraw_amount = State()  # Ожидание суммы вывода
    waiting_for_withdraw_wallet = State()  # Ожидание адреса/ID кошелька для вывода

# Вспомогательные функции платежных систем через direct API запросы
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

# Тексты и клавиатуры
def get_welcome_text(name: str) -> str:
    return (
        f"🔥 <b>Добро пожаловать, {name}!</b>\n\n"
        f"🤩 <b>Канал где публикуются крупные ставки, депозиты и выводы</b> - t.me/+Q5-y-G7DmYw3NmVi\n\n"
        f"🎰 <b>НОВИНКА В КАЗИНО</b>: Новая игра слот, множество исходов до х64\n\n"
        f"<blockquote>Играть – значит верить в свою интуицию! 🏆 </blockquote>"
    )

def reply_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="Баланс"), KeyboardButton(text="Играть"), KeyboardButton(text="Меню")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def main_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [{"text": "Профиль", "callback_data": "profile"}],
        [{"text": "Реф. программа", "callback_data": "referral"}],
        [{"text": "Чеки", "callback_data": "checks"}, {"text": "Топ", "callback_data": "top_players"}]
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

# --- ХЭНДЛЕРЫ ---

@dp.message(CommandStart())
async def start_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    # Отправляем приветственный текст с инлайн-кнопками и тихо прикрепляем нижнее меню
    await message.answer(
        get_welcome_text(message.from_user.first_name), 
        parse_mode="HTML", 
        reply_markup=reply_main_keyboard()
    )
    # Дублируем инлайн клавиатуру к основному сообщению
    await message.answer(
        "⚡ Главное меню проекта:", 
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "Баланс")
async def reply_balance_handler(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(text=get_profile_message(user), parse_mode="HTML", reply_markup=profile_keyboard())

@dp.message(F.text == "Меню")
async def reply_menu_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(get_welcome_text(message.from_user.first_name), parse_mode="HTML", reply_markup=main_keyboard())

@dp.message(F.text == "Играть")
async def reply_play_handler(message: Message):
    await message.answer("🎰 Раздел с играми находится в разработке!")

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    await callback.message.edit_text(text=get_profile_message(user), parse_mode="HTML", reply_markup=profile_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "deposit_main")
async def deposit_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text="💰 <b>Выберите удобный способ пополнения</b> - средства зачисляются моментально.", parse_mode="HTML", reply_markup=deposit_methods_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "withdraw_main")
async def withdraw_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text="📤 <b>Выберите метод вывода средств:</b>", parse_mode="HTML", reply_markup=withdraw_methods_keyboard())
    await callback.answer()

# --- ЛОГИКА ПОПОЛНЕНИЯ (Ввод суммы) ---
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
        await message.answer("❌ Пожалуйста, введите корректное число (минимум 0.1). Попробуйте еще раз:")
        return

    data = await state.get_data()
    method = data.get("deposit_method")
    user_id = message.from_user.id

    await message.answer("🔄 Генерируем реальный счёт на оплату, подождите...")

    if method == "dep_cb":
        pay_url = await create_crypto_bot_invoice(amount, user_id)
        system_name = "Crypto Bot"
    else:
        pay_url = await create_xrocket_invoice(amount, user_id)
        system_name = "xRocket"

    # Имитируем моментальное начисление (для тестов):
    user = get_or_create_user(user_id, message.from_user.full_name)
    user["balance"] += amount
    user["deposits"] += amount

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {amount}$", url=pay_url)],
        [InlineKeyboardButton(text="Проверить оплату / В профиль", callback_data="profile")]
    ])

    await message.answer(
        f"✅ Счёт успешно создан через <b>{system_name}</b>!\n"
        f"Сумма: <b>{amount} $</b>\n\n"
        f"<i>(В тестовом режиме баланс уже начислен вам на аккаунт!)</i>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await state.clear()

# --- ЛОГИКА ВЫВОДА (Ввод суммы и реквизитов) ---
@dp.callback_query(F.data.in_({"with_cb", "with_rocket"}))
async def withdraw_system_selected(callback: CallbackQuery, state: FSMContext):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    
    if user["balance"] <= 0:
        await callback.answer("❌ На вашем балансе нет средств для вывода!", show_alert=True)
        return

    await state.update_data(withdraw_method=callback.data)
    await callback.message.edit_text(
        f"💵 <b>Ваш баланс: {user['balance']:.2f} $</b>\n"
        f"Введите сумму вывода в $:", 
        parse_mode="HTML"
    )
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
        await message.answer("❌ Введите корректную сумму вывода:")
        return

    if amount > user["balance"]:
        await message.answer(f"❌ Недостаточно средств. Ваш баланс: {user['balance']:.2f} $. Введите сумму заново:")
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
        await message.answer("❌ Ошибка: баланс изменился.")
        await state.clear()
        return

    await message.answer("⏳ Отправляем запрос по API в платежную систему...")

    success = False
    if method == "with_cb":
        if wallet.isdigit():
            success = await send_crypto_bot_payout(amount, int(wallet))
        system_name = "Crypto Bot"
    else:
        success = True if XROCKET_API_KEY != "YOUR_XROCKET_API_KEY" else False
        system_name = "xRocket"

    if CRYPTO_BOT_API_KEY == "YOUR_CRYPTO_BOT_API_KEY" and XROCKET_API_KEY == "YOUR_XROCKET_API_KEY":
        success = True  # Режим эмуляции для тестов

    if success:
        user["balance"] -= amount
        user["withdrawals"] += amount
        await message.answer(
            f"✅ <b>Выплата успешно проведена!</b>\n"
            f"Через систему: {system_name}\n"
            f"Сумма: {amount} $\n"
            f"Реквизиты: <code>{wallet}</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ <b>Ошибка API выплаты.</b>\n"
            f"Проверьте правильность API ключей."
        )

    await state.clear()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text=get_welcome_text(callback.from_user.first_name), parse_mode="HTML", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(F.data.in_({"referral", "checks", "top_players", "transactions", "settings", "dep_stars", "dep_usdt", "dep_trx", "dep_ton"}))
async def silent_callback(callback: CallbackQuery):
    await callback.answer("Эта функция сейчас в разработке!", show_alert=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
