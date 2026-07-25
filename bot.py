import asyncio
import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiocryptopay import AioCryptoPay, Networks

# -------------------------------------------------------------
# НАСТРОЙКИ
# -------------------------------------------------------------
TOKEN = "8831174244:AAHL_uTfgQEA4zaPsp3UkhHjv5ePb2rn8xE"  # Токен от @BotFather
CRYPTO_TOKEN = "613373:AAMtHeqDU9uXDRpfGSSw5g4KNRHeuouK5X2"  # Токен от CryptoPay (CryptoBot)

# Обязательный текст, который должен быть в Био пользователя
REQUIRED_BIO = "@Sparta_cash — место где зарабатывают деньги!"

# Награда за 1 сообщение
REWARD_PER_MESSAGE = 0.00024

# Инициализация бота, диспетчера и CryptoPay API (Main Net - основная сеть)
bot = Bot(token=TOKEN)
dp = Dispatcher()
cryptopay = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)

# Кэш для отслеживания задержки (5 секунд)
user_cooldowns = {}
# Кэш для био (защита от лимитов Telegram)
bio_cache = {}


# -------------------------------------------------------------
# БАЗА ДАННЫХ (SQLite)
# -------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("sparta_cash.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            messages_count INTEGER DEFAULT 0,
            balance REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = sqlite3.connect("sparta_cash.db")
    cursor = conn.cursor()
    cursor.execute("SELECT messages_count, balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, messages_count, balance) VALUES (?, 0, 0.0)", (user_id,))
        conn.commit()
        user = (0, 0.0)
    conn.close()
    return user

def add_message_reward(user_id: int):
    conn = sqlite3.connect("sparta_cash.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, messages_count, balance)
        VALUES (?, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            messages_count = messages_count + 1,
            balance = balance + ?
    """, (user_id, REWARD_PER_MESSAGE, REWARD_PER_MESSAGE))
    conn.commit()
    conn.close()

def reset_user_balance(user_id: int):
    # Обнуляем ТОЛЬКО баланс, сообщения не трогаем
    conn = sqlite3.connect("sparta_cash.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# ТЕКСТЫ И КЛАВИАТУРЫ
# -------------------------------------------------------------
START_TEXT = (
    "<b>👋 Добро пожаловать в Sparta Cash!\n\n"
    "💸 Зарабатывай кэш просто общаясь у нас в чате!</b>\n\n"
    "<blockquote><b>🎯 Как участвовать:\n"
    "1️⃣ Добавь в био: @Sparta_cash — место где зарабатывают деньги!\n"
    "2️⃣ Общайся в чатах из нашего списка\n"
    "3️⃣  Награда — 0,24$ за 1000 сообщений 🥰</b></blockquote>\n\n"
    "<b>💰 Выплаты осуществляются мгновенно на @send \n"
    "🔓 Вывод — от 0.10$\n\n"
    "⚠️ Важно :\n"
    "Допустима только приписка @Sparta_cash\n\n"
    "🏆 Оплата за 1 сообщение - 0.00024$</b>"
)

CHATS_TEXT = (
    "<b>Вот список всех доступных чатов для общения :</b>\n\n"
    "<b>🔥 Чат Sparta - 0.00024$</b>\n\n"
    "<b>Сообщения засчитываются раз в 5 секунд !</b>"
)

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="💬 Чаты", callback_data="chats")]
    ])

def get_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw")],
        [InlineKeyboardButton(text="В главное меню ⬅️", callback_data="main_menu")]
    ])

def get_chats_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="В главное меню ⬅️", callback_data="main_menu")]
    ])

def get_check_keyboard(check_url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Активировать чек", url=check_url)],
        [InlineKeyboardButton(text="В главное меню ⬅️", callback_data="main_menu")]
    ])


# -------------------------------------------------------------
# ХЕНДЛЕРЫ ЛИЧНЫХ СООБЩЕНИЙ
# -------------------------------------------------------------
@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(START_TEXT, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())


@dp.callback_query(F.data == "main_menu")
async def back_to_main_menu(call: CallbackQuery):
    await call.message.edit_text(START_TEXT, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())
    await call.answer()


@dp.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery):
    msg_count, balance = get_user(call.from_user.id)
    user_name = call.from_user.full_name

    profile_text = (
        "<b>👤 Профиль</b>\n\n"
        f"<b>🎮 Имя : {user_name}</b>\n"
        f"<b>📨 Всего сообщений отправлено: {msg_count}</b>\n"
        f"<b>💰 Баланс: {balance:.6f} USDT</b>"
    )
    await call.message.edit_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=get_profile_keyboard())
    await call.answer()


@dp.callback_query(F.data == "chats")
async def show_chats(call: CallbackQuery):
    await call.message.edit_text(CHATS_TEXT, parse_mode=ParseMode.HTML, reply_markup=get_chats_keyboard())
    await call.answer()


@dp.callback_query(F.data == "withdraw")
async def handle_withdraw(call: CallbackQuery):
    msg_count, balance = get_user(call.from_user.id)
    
    # Проверка на минимальную сумму
    if balance < 0.1:
        await call.answer("⚠️ Минимальный вывод от 0.1$", show_alert=True)
        return

    # Округляем до 6 знаков, чтобы избежать ошибок с длинными дробями
    amount_to_withdraw = round(balance, 6)
    
    try:
        # Пытаемся создать чек в CryptoBot
        check = await cryptopay.create_check(asset="USDT", amount=amount_to_withdraw)
        
        # Если чек успешно создан - списываем баланс
        reset_user_balance(call.from_user.id)
        
        # Изменяем сообщение на чек
        check_text = (
            "<b>✅ Вывод успешно выполнен!</b>\n\n"
            f"<b>Вот ваш чек на {amount_to_withdraw} USDT:</b>\n"
            f"{check.bot_check_url}"
        )
        await call.message.edit_text(
            check_text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=get_check_keyboard(check.bot_check_url)
        )
        await call.answer()
        
    except Exception as e:
        # Ошибка (например, нет денег на балансе приложения в CryptoBot)
        logging.error(f"Ошибка вывода: {e}")
        await call.answer("❌ Ошибка, попробуйте позже", show_alert=True)


# -------------------------------------------------------------
# ХЕНДЛЕР ОБРАБОТКИ СООБЩЕНИЙ В ЧАТАХ (ГРУППАХ)
# -------------------------------------------------------------
async def check_user_bio(user_id: int) -> bool:
    current_time = time.time()
    if user_id in bio_cache:
        has_bio, last_check = bio_cache[user_id]
        if current_time - last_check < 300:
            return has_bio

    try:
        chat_info = await bot.get_chat(user_id)
        user_bio = chat_info.bio or ""
        has_bio = REQUIRED_BIO in user_bio
    except Exception:
        has_bio = False

    bio_cache[user_id] = (has_bio, current_time)
    return has_bio

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def track_group_messages(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    user_id = message.from_user.id
    current_time = time.time()

    last_time = user_cooldowns.get(user_id, 0)
    if current_time - last_time < 5:
        return

    if await check_user_bio(user_id):
        add_message_reward(user_id)
        user_cooldowns[user_id] = current_time


# -------------------------------------------------------------
# ЗАПУСК БОТА
# -------------------------------------------------------------
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("🚀 Бот Sparta Cash успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
if __name__ == "__main__":
    asyncio.run(main())
