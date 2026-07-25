import asyncio
import logging
import time
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiocryptopay import AioCryptoPay, Networks

# -------------------------------------------------------------
# НАСТРОЙКИ
# -------------------------------------------------------------
TOKEN = "8829468133:AAFKB7SOH7pERK0TWfw3T_AroQoK6kCTij0"
CRYPTO_TOKEN = "613373:AAMtHeqDU9uXDRpfGSSw5g4KNRHeuouK5X2"  # ЗАМЕНИТЕ НА ОСНОВНОЙ ТОКЕН!
ADMIN_ID = 7921743592

REQUIRED_BIO = "@Sparta_cash — место где зарабатывают деньги!"
REWARD_PER_MESSAGE = 0.00024
DB_NAME = "sparta_cash.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()
cryptopay = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)

user_cooldowns = {}
bio_cache = {}


# -------------------------------------------------------------
# МАШИНА СОСТОЯНИЙ ДЛЯ АДМИНА
# -------------------------------------------------------------
class AdminStates(StatesGroup):
    waiting_for_topup = State()
    waiting_for_withdraw = State()
    waiting_for_accrual_id = State()
    waiting_for_accrual_amount = State()


# -------------------------------------------------------------
# АСИНХРОННАЯ БАЗА ДАННЫХ (aiosqlite)
# -------------------------------------------------------------
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                messages_count INTEGER DEFAULT 0,
                balance REAL DEFAULT 0.0
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT messages_count, balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                await db.execute("INSERT INTO users (user_id, messages_count, balance) VALUES (?, 0, 0.0)", (user_id,))
                await db.commit()
                return (0, 0.0)
            return user

async def add_message_reward(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, messages_count, balance)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                messages_count = messages_count + 1,
                balance = balance + ?
        """, (user_id, REWARD_PER_MESSAGE, REWARD_PER_MESSAGE))
        await db.commit()

async def add_user_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, messages_count, balance)
            VALUES (?, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                balance = balance + ?
        """, (user_id, amount, amount))
        await db.commit()

async def deduct_balance(user_id: int, amount: float) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user or user[0] < amount:
                return False
        
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()
        return True

async def refund_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_db_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*), SUM(balance) FROM users") as cursor:
            stats = await cursor.fetchone()
        async with db.execute("SELECT user_id, balance, messages_count FROM users ORDER BY balance DESC LIMIT 20") as cursor:
            top_users = await cursor.fetchall()
    return stats, top_users


# -------------------------------------------------------------
# ТЕКСТЫ И КЛАВИАТУРЫ
# -------------------------------------------------------------
START_TEXT = (
    "<b>👋 Добро пожаловать в Sparta Cash!\n\n"
    "💸 Зарабатывай кэш, просто общаясь у нас в чате!</b>\n\n"
    "<b>🎯 Как участвовать:</b>\n"
    "<b>1️⃣ Добавь в био:</b> <code>@Sparta_cash — место где зарабатывают деньги!</code>\n"
    "<b>2️⃣ Общайся в чатах из нашего списка</b>\n"
    "<b>3️⃣ Награда — 0,24$ за 1000 сообщений 🥰</b>\n\n"
    "<b>💰 Выплаты осуществляются мгновенно на @send \n"
    "🔓 Вывод — от 0.10$\n\n"
    "⚠️ Важно:\n"
    "Допустима только приписка @Sparta_cash\n\n"
    "🏆 Оплата за 1 сообщение - 0.00024$</b>"
)

CHATS_TEXT = (
    "<b>Вот список всех доступных чатов для общения:</b>\n\n"
    "<b>Сообщения засчитываются раз в 5 секунд!</b>"
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
        [InlineKeyboardButton(text="🔥 Чат Sparta - 0.00024$", url="https://t.me/spartacashchat")],
        [InlineKeyboardButton(text="В главное меню ⬅️", callback_data="main_menu")]
    ])

def get_check_keyboard(check_url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Активировать чек", url=check_url)],
        [InlineKeyboardButton(text="В главное меню ⬅️", callback_data="main_menu")]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить казну", callback_data="admin_topup"),
         InlineKeyboardButton(text="💸 Вывести чеком", callback_data="admin_withdraw")],
        [InlineKeyboardButton(text="➕ Начислить баланс", callback_data="admin_accrual")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton(text="Закрыть ❌", callback_data="admin_close")]
    ])


# -------------------------------------------------------------
# ХЕНДЛЕРЫ АДМИНА
# -------------------------------------------------------------
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    
    usdt_balance = "0.0"
    try:
        app_balances = await cryptopay.get_balance()
        if isinstance(app_balances, list):
            for b in app_balances:
                curr = getattr(b, 'currency_code', None) or getattr(b, 'currency', None)
                if curr == "USDT":
                    usdt_balance = str(getattr(b, 'available', getattr(b, 'amount', 0.0)))
                    break
        elif hasattr(app_balances, 'available'):
            usdt_balance = str(app_balances.available)
    except Exception as e:
        logging.error(f"Ошибка получения баланса казны: {e}")
        usdt_balance = "Ошибка API"

    stats, _ = await get_db_stats()
    total_users = stats[0] or 0
    total_debt = stats[1] or 0.0

    text = (
        "<b>👑 Админ Панель</b>\n\n"
        f"<b>🏦 Баланс казны:</b> <code>{usdt_balance} USDT</code>\n"
        f"<b>👥 Всего пользователей:</b> {total_users}\n"
        f"<b>💰 Долг игрокам (общий баланс):</b> <code>{total_debt:.6f} USDT</code>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "admin_close", F.from_user.id == ADMIN_ID)
async def admin_close(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()

@dp.callback_query(F.data == "admin_users", F.from_user.id == ADMIN_ID)
async def admin_show_users(call: CallbackQuery, state: FSMContext):
    await state.clear()
    _, top_users = await get_db_stats()
    text = "<b>Топ-20 пользователей:</b>\n\n"
    for uid, bal, msgs in top_users:
        text += f"ID: <code>{uid}</code> | {msgs} смс | {bal:.4f} USDT\n"
    
    if not top_users:
        text += "Пользователей пока нет."

    await call.message.answer(text, parse_mode=ParseMode.HTML)
    await call.answer()

# --- Пополнение казны ---
@dp.callback_query(F.data == "admin_topup", F.from_user.id == ADMIN_ID)
async def admin_topup_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("<b>Введите сумму в USDT, на которую хотите пополнить казну:</b>", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_topup)
    await call.answer()

@dp.message(AdminStates.waiting_for_topup, F.from_user.id == ADMIN_ID)
async def admin_topup_process(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        invoice = await cryptopay.create_invoice(asset="USDT", amount=amount)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить счет", url=invoice.bot_invoice_url)]
        ])
        await message.answer(f"<b>Счет на {amount} USDT создан!</b>\nПосле оплаты казна пополнится автоматически.", parse_mode=ParseMode.HTML, reply_markup=kb)
    except ValueError:
        await message.answer("❌ Ошибка: Введите число (например, 1.5)")
    except Exception as e:
        await message.answer(f"❌ Ошибка API: {e}")
    finally:
        await state.clear()

# --- Вывод чеком из казны (админ) ---
@dp.callback_query(F.data == "admin_withdraw", F.from_user.id == ADMIN_ID)
async def admin_withdraw_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("<b>Введите сумму в USDT для вывода чеком из казны:</b>", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_withdraw)
    await call.answer()

@dp.message(AdminStates.waiting_for_withdraw, F.from_user.id == ADMIN_ID)
async def admin_withdraw_process(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        check = await cryptopay.create_check(asset="USDT", amount=amount)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Активировать чек", url=check.bot_check_url)]
        ])
        await message.answer(f"<b>✅ Чек на {amount} USDT успешно создан!</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
    except ValueError:
        await message.answer("❌ Ошибка: Введите число (например, 1.5)")
    except Exception as e:
        await message.answer(f"❌ Ошибка (возможно в казне не хватает средств): {e}")
    finally:
        await state.clear()

# --- Ручное начисление баланса по ID ---
@dp.callback_query(F.data == "admin_accrual", F.from_user.id == ADMIN_ID)
async def admin_accrual_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("<b>Введите ID пользователя, которому хотите начислить баланс:</b>", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_accrual_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_accrual_id, F.from_user.id == ADMIN_ID)
async def admin_accrual_get_id(message: Message, state: FSMContext):
    try:
        target_id = int(message.text.strip())
        await state.update_data(target_user_id=target_id)
        await message.answer(f"<b>ID <code>{target_id}</code> принят.\nТеперь введите сумму USDT для начисления (например, 1.5):</b>", parse_mode=ParseMode.HTML)
        await state.set_state(AdminStates.waiting_for_accrual_amount)
    except ValueError:
        await message.answer("❌ Ошибка: ID должен состоять только из цифр. Попробуйте снова:")

@dp.message(AdminStates.waiting_for_accrual_amount, F.from_user.id == ADMIN_ID)
async def admin_accrual_finish(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        data = await state.get_data()
        target_id = data.get("target_user_id")
        
        await add_user_balance(target_id, amount)
        await message.answer(f"<b>✅ Успешно! Пользователю <code>{target_id}</code> начислено {amount} USDT.</b>", parse_mode=ParseMode.HTML)
    except ValueError:
        await message.answer("❌ Ошибка: Введите число (например, 1.5)")
    except Exception as e:
        await message.answer(f"❌ Ошибка при начислении: {e}")
    finally:
        await state.clear()


# -------------------------------------------------------------
# ХЕНДЛЕРЫ ЛИЧНЫХ СООБЩЕНИЙ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ
# -------------------------------------------------------------
@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(START_TEXT, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())


@dp.callback_query(F.data == "main_menu")
async def back_to_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(START_TEXT, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())
    except TelegramBadRequest:
        pass
    await call.answer()


@dp.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery, state: FSMContext):
    await state.clear()
    msg_count, balance = await get_user(call.from_user.id)
    user_name = call.from_user.full_name

    profile_text = (
        "<b>👤 Профиль</b>\n\n"
        f"<b>🎮 Имя : {user_name}</b>\n"
        f"<b>📨 Всего сообщений отправлено: {msg_count}</b>\n"
        f"<b>💰 Баланс: {balance:.6f} USDT</b>"
    )
    try:
        await call.message.edit_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=get_profile_keyboard())
    except TelegramBadRequest:
        pass
    await call.answer()


@dp.callback_query(F.data == "chats")
async def show_chats(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(CHATS_TEXT, parse_mode=ParseMode.HTML, reply_markup=get_chats_keyboard())
    except TelegramBadRequest:
        pass
    await call.answer()


@dp.callback_query(F.data == "withdraw")
async def handle_withdraw(call: CallbackQuery, state: FSMContext):
    await state.clear()
    _, balance = await get_user(call.from_user.id)
    
    if balance < 0.1:
        await call.answer("⚠️ Минимальный вывод от 0.1$", show_alert=True)
        return

    amount_to_withdraw = round(balance, 6)
    
    success = await deduct_balance(call.from_user.id, amount_to_withdraw)
    if not success:
        await call.answer("❌ Ошибка списания баланса", show_alert=True)
        return
    
    try:
        # СОЗДАЕМ ЧЕК ДЛЯ ПОЛЬЗОВАТЕЛЯ
        check = await cryptopay.create_check(asset="USDT", amount=amount_to_withdraw)
        
        check_text = (
            "<b>✅ Вывод успешно выполнен!</b>\n\n"
            f"<b>Вот ваш чек на {amount_to_withdraw} USDT:</b>\n"
            f"{check.bot_check_url}\n\n"
            "💡 Нажмите кнопку ниже, чтобы активировать чек и получить средства"
        )
        await call.message.edit_text(
            check_text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=get_check_keyboard(check.bot_check_url)
        )
        await call.answer()
        
    except Exception as e:
        logging.error(f"Ошибка вывода у юзера {call.from_user.id}: {e}")
        await refund_balance(call.from_user.id, amount_to_withdraw)
        await call.answer("❌ Ошибка казны, попробуйте позже. Средства возвращены на баланс.", show_alert=True)


# -------------------------------------------------------------
# ХЕНДЛЕР ОБРАБОТКИ СООБЩЕНИЙ В ЧАТАХ (ГРУППАХ)
# -------------------------------------------------------------
async def check_user_bio(user_id: int) -> bool:
    current_time = time.time()
    
    if len(bio_cache) > 5000:
        bio_cache.clear()
        
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
    
    if len(user_cooldowns) > 5000:
        user_cooldowns.clear()

    last_time = user_cooldowns.get(user_id, 0)
    if current_time - last_time < 5:
        return

    if await check_user_bio(user_id):
        await add_message_reward(user_id)
        user_cooldowns[user_id] = current_time


# -------------------------------------------------------------
# ЗАПУСК БОТА
# -------------------------------------------------------------
async def main():
    await init_db()
    logging.basicConfig(level=logging.INFO)
    print("🚀 Бот Sparta Cash успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
