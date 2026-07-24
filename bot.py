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
TOKEN = "8831174244:AAHL_uTfgQEA4zaPsp3UkhHjv5ePb2rn8xE"  # Вставь сюда токен от @BotFather

# Обязательный текст, который должен быть в Био пользователя
REQUIRED_BIO = "@Sparta_cash — место где зарабатывают деньги!"

# Награда за 1 сообщение
REWARD_PER_MESSAGE = 0.00024

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Кэш для отслеживания задержки (5 секунд) отправки сообщений пользователями
user_cooldowns = {}


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
        UPDATE users 
        SET messages_count = messages_count + 1, 
            balance = balance + ? 
        WHERE user_id = ?
    """, (REWARD_PER_MESSAGE, user_id))
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# ТЕКСТЫ И КЛАВИАТУРЫ
# -------------------------------------------------------------
START_TEXT = (
    "<b>👋 Добро пожаловать в Sparta Cash!</b>\n"
    "<b>💸 Зарабатывай кэш просто общаясь у нас в чате!</b>\n"
    "<b>🎯 Как участвовать:</b>\n"
    "<b>1️⃣ Добавь в био: @Sparta_cash — место где зарабатывают деньги!</b>\n"
    "<b>2️⃣ Общайся в чатах из нашего списка</b>\n"
    "<b>3️⃣  Награда — 0,24$ за 1000 сообщений 🥰</b>\n"
    "<b>💰 Выплаты осуществляются мгновенно на @send</b>\n"
    "<b>🔓 Вывод — от 0.10$</b>\n"
    "<b>⚠️ Важно :</b>\n"
    "<b>Допустима только приписка @Sparta_cash</b>\n"
    "<b>🏆 Оплата за 1 сообщение - 0.00024$</b>"
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
        [
            InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw"),
            InlineKeyboardButton(text=" ", callback_data="none")  # Пустая кнопка без действия
        ],
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
    # Удаляем сообщение с командой /start от пользователя
    try:
        await message.delete()
    except Exception:
        pass

    # Отправляем приветственное сообщение
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
        f"<b>🎮 Имя игрока: {user_name}</b>\n"
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


@dp.callback_query(F.data == "none")
async def handle_none(call: CallbackQuery):
    await call.answer()


# -------------------------------------------------------------
# ХЕНДЛЕР ОБРАБОТКИ СООБЩЕНИЙ В ЧАТАХ (ГРУППАХ)
# -------------------------------------------------------------
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def track_group_messages(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    user_id = message.from_user.id
    current_time = time.time()

    # Проверка КД в 5 секунд
    last_time = user_cooldowns.get(user_id, 0)
    if current_time - last_time < 5:
        return

    # Проверяем био пользователя через Telegram API
    try:
        chat_info = await bot.get_chat(user_id)
        user_bio = chat_info.bio or ""
    except Exception:
        user_bio = ""

    # Если нужная строчка есть в описании профиля
    if REQUIRED_BIO in user_bio:
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
