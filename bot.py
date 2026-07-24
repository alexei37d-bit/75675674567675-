import asyncio
import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message

# -------------------------------------------------------------
# НАСТРОЙКИ
# -------------------------------------------------------------
TOKEN = "8831174244:AAHL_uTfgQEA4zaPsp3UkhHjv5ePb2rn8xE"  # Твой токен

# Обязательный текст, который должен быть в Био пользователя
REQUIRED_BIO = "@Sparta_cash — место где зарабатывают деньги!"

# Награда за 1 сообщение
REWARD_PER_MESSAGE = 0.00024

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Кэш для отслеживания задержки (5 секунд)
user_cooldowns = {}
# Кэш для хранения результатов проверки БИО (user_id: (has_bio_bool, check_timestamp))
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
    # Исправлено: если пользователя нет в базе, он создаётся автоматически
    cursor.execute("""
        INSERT INTO users (user_id, messages_count, balance)
        VALUES (?, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            messages_count = messages_count + 1,
            balance = balance + ?
    """, (user_id, REWARD_PER_MESSAGE, REWARD_PER_MESSAGE))
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
    await call.answer("⚠️ Вывод средств пока временно недоступен.", show_alert=True)


# -------------------------------------------------------------
# ХЕНДЛЕР ОБРАБОТКИ СООБЩЕНИЙ В ЧАТАХ (ГРУППАХ)
# -------------------------------------------------------------
async def check_user_bio(user_id: int) -> bool:
    current_time = time.time()
    # Если запрашивали био меньше 5 минут назад, берём значение из кэша
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

    # Проверка КД в 5 секунд на отправку сообщений
    last_time = user_cooldowns.get(user_id, 0)
    if current_time - last_time < 5:
        return

    # Проверка наличия нужного био
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
