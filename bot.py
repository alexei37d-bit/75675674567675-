import random
import asyncio
import string
import aiohttp
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F, html
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    KeyboardButton, Message, ReplyKeyboardMarkup,
)

# --- ИНИЦИАЛИЗАЦИЯ ---
logger = logging.getLogger(__name__)
TOKEN = "8740242990:AAF2I7c7x_SD6-Dww3WQJKQYbk3WsXYP5BI"
CRYPTO_PAY_TOKEN = "548204:AAZOXSPMBWOj3XO29UyRcrxpgxlzujtetPO"
XROCKET_LINK = "https://t.me/xrocket?start=inv_KzKYP17T8CLzQxQ"
dp = Dispatcher()

# Константы вагера
WAGER_MULTIPLIER = 1.52
MIN_DEPOSIT_FOR_WITHDRAW = 0.3

# --- БАЗА ДАННЫХ ---
DB_NAME = "bot_data.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS balances (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)")
        await db.execute("CREATE TABLE IF NOT EXISTS turnover (user_id INTEGER PRIMARY KEY, amount REAL DEFAULT 0.0)")
        await db.execute("CREATE TABLE IF NOT EXISTS global_stats (key TEXT PRIMARY KEY, value REAL DEFAULT 0.0)")
        # Таблица для вагера и общего депозита
        await db.execute("CREATE TABLE IF NOT EXISTS user_stats (user_id INTEGER PRIMARY KEY, total_deposited REAL DEFAULT 0.0, wager_remaining REAL DEFAULT 0.0)")
        
        await db.execute("INSERT OR IGNORE INTO global_stats VALUES ('deposited', 0.0), ('withdrawn', 0.0), ('turnover_all', 0.0)")
        await db.commit()

async def update_balance(user_id: int, amount: float):
    """
    Обновляет баланс. 
    Если amount > 0 (пополнение), также обновляет вагер и общий депозит.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # Обновляем баланс
        await db.execute(
            "INSERT OR REPLACE INTO balances (user_id, balance) VALUES (?, COALESCE((SELECT balance FROM balances WHERE user_id = ?), 0) + ?)",
            (user_id, user_id, amount)
        )
        
        # Если это пополнение
        if amount > 0:
            wager_add = amount * WAGER_MULTIPLIER
            await db.execute(
                "INSERT INTO user_stats (user_id, total_deposited, wager_remaining) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "total_deposited = total_deposited + ?, "
                "wager_remaining = wager_remaining + ?",
                (user_id, amount, wager_add, amount, wager_add)
            )
            
        await db.commit()

    # Обновляем кэш (если используется)
    if user_id in user_balances:
        user_balances[user_id] += amount
    else:
        # Если в кэше нет, лучше перечитать из БД или установить
        user_balances[user_id] = amount 

async def reduce_wager(user_id: int, amount: float):
    """Уменьшает остаток вагера при игре"""
    if amount <= 0: return
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE user_stats SET wager_remaining = MAX(0, wager_remaining - ?) WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def get_user_wager_info(user_id: int):
    """Возвращает (total_deposited, wager_remaining)"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT total_deposited, wager_remaining FROM user_stats WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return row[0], row[1]
        return 0.0, 0.0

async def update_global_stat(key: str, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE global_stats SET value = value + ? WHERE key = ?", (amount, key))
        await db.commit()

# --- АДМИН-ПАНЕЛЬ ---
ADMIN_IDS = {8207980755, 7921743592}
REQUIRED_CHANNELS = ["@project_impassL", "@DuckBets", "@Duckcasn"]
BETS_CHANNEL = "@test_k_anal"
WITHDRAW_CHANNEL = "@Duckcasn"

class AdminState(StatesGroup):
    waiting_for_add_admin = State()
    waiting_for_add_balance_user = State()
    waiting_for_add_balance_amount = State()
    waiting_for_sub_balance_user = State()
    waiting_for_sub_balance_amount = State()
    waiting_for_broadcast_text = State()
    waiting_for_withdraw_check_url = State()
    waiting_for_manual_deposit_confirm = State()

async def check_subscription(bot: Bot, user_id: int) -> bool:
    try:
        for channel in REQUIRED_CHANNELS:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                return False
        return True
    except Exception:
        return False

async def force_subscription_check(message_or_call, state=None):
    user_id = message_or_call.from_user.id
    bot = message_or_call.bot if hasattr(message_or_call, 'bot') else message_or_call.message.bot
    is_subbed = await check_subscription(bot, user_id)
    if is_subbed:
        return True
    
    kb = await get_subscription_keyboard(bot)
    text = '<b><tg-emoji emoji-id="5312140414982071786">⚠️</tg-emoji> Для использования бота вы должны быть подписаны на все каналы!</b>'
    
    if isinstance(message_or_call, Message):
        await message_or_call.answer(text, parse_mode="HTML", reply_markup=kb, reply_to_message_id=message_or_call.message_id)
    else:
        try:
            await message_or_call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await message_or_call.message.answer(text, parse_mode="HTML", reply_markup=kb)
        await message_or_call.answer()
    
    if state:
        await state.clear()
    return False

async def get_subscription_keyboard(bot: Bot) -> InlineKeyboardMarkup:
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"📢 Подписаться на {ch}", url=f"https://t.me/{ch.replace('@', '')}")])
    buttons.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription_again")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def log_bet_to_channel(bot: Bot, user, game_name: str, bet: float, outcome: str, win_amount: float = 0.0):
    user_link = f'<a href="tg://user?id={user.id}">{html.quote(user.full_name)}</a>'
    if win_amount > 0:
        status_text = f'<tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Выигрыш: <b>{win_amount:.2f} $</b>'
    else:
        status_text = f'<tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Проигрыш: <b>{bet:.2f} $</b>'
    
    text = (
        f'<tg-emoji emoji-id="5451807640436903198">🎰</tg-emoji> <b>Новая ставка!</b>\n'
        f'<tg-emoji emoji-id="5197514090108456970">👤</tg-emoji> Игрок: {user_link} (<code>{user.id}</code>)\n'
        f'<tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Игра: <b>{game_name}</b>\n'
        f'<tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Ставка: <b>{bet:.2f} $</b>\n'
        f'<tg-emoji emoji-id="5307942883314147223">🎯</tg-emoji> Исход: <b>{outcome}</b>\n'
        f"{status_text}"
    )
    try:
        await bot.send_message(chat_id=BETS_CHANNEL, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to log bet to channel: {e}")

def get_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add_admin")],
        [
            InlineKeyboardButton(text="💵 Начислить баланс", callback_data="admin_add_balance"),
            InlineKeyboardButton(text="📉 Отнять баланс", callback_data="admin_sub_balance"),
        ],
        [
            InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users_list"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        ],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📤 Заявки на вывод", callback_data="admin_withdraw_requests")],
        [InlineKeyboardButton(text="🏀 Канал ставок", url=f"https://t.me/{BETS_CHANNEL.replace('@', '')}")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("admin"))
async def admin_panel_handler(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE: return
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in ADMIN_IDS: return
    await message.answer(
        '<b><tg-emoji emoji-id="5451807640436903198">⚙️</tg-emoji> Панель администратора:</b>',
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(user_id),
    )

@dp.callback_query(F.data == "admin_close")
async def admin_close_handler(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    await state.clear()
    await call.message.delete()

@dp.callback_query(F.data == "admin_add_admin")
async def admin_add_admin_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminState.waiting_for_add_admin)
    await call.message.edit_text(
        '<b><tg-emoji emoji-id="5449526218233779946">➕</tg-emoji> Введите Telegram ID пользователя, которого хотите сделать админом:</b>\n\n'
        '<i>Для отмены введите /cancel</i>',
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_add_admin)
async def admin_add_admin_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    try:
        new_admin_id = int(message.text.strip())
        ADMIN_IDS.add(new_admin_id)
        await state.clear()
        await message.answer(
            f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Пользователь {new_admin_id} успешно добавлен в список администраторов!</b>',
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(message.from_user.id),
        )
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректный ID. Введите число:</b>', parse_mode="HTML")

@dp.callback_query(F.data == "admin_add_balance")
async def admin_add_balance_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminState.waiting_for_add_balance_user)
    await call.message.edit_text(
        '<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите ID игрока, которому нужно НАЧИСЛИТЬ баланс:</b>\n\n'
        '<i>Для отмены введите /cancel</i>',
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_add_balance_user)
async def admin_add_balance_user_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    try:
        target_id = int(message.text.strip())
        await state.update_data(target_id=target_id)
        await state.set_state(AdminState.waiting_for_add_balance_amount)
        await message.answer(
            '<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите сумму для начисления:</b>\n\n'
            '<i>Для отмены введите /cancel</i>',
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректный ID. Введите число:</b>', parse_mode="HTML")

@dp.message(AdminState.waiting_for_add_balance_amount)
async def admin_add_balance_amount_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0: raise ValueError
        data = await state.get_data()
        target_id = data["target_id"]
        await update_balance(target_id, amount)
        await state.clear()
        new_bal = get_user_balance(target_id)
        await message.answer(
            f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Успешно начислено {amount:.2f} $ игроку <code>{target_id}</code>!\n'
            f"Новый баланс: {new_bal:.2f} $</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(message.from_user.id),
        )
    except (ValueError, KeyError):
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма. Введите положительное число:</b>', parse_mode="HTML")

@dp.callback_query(F.data == "admin_sub_balance")
async def admin_sub_balance_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminState.waiting_for_sub_balance_user)
    await call.message.edit_text(
        '<b><tg-emoji emoji-id="5452042536493288421">📉</tg-emoji> Введите ID игрока, у которого нужно ОТНЯТЬ баланс:</b>\n\n'
        '<i>Для отмены введите /cancel</i>',
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_sub_balance_user)
async def admin_sub_balance_user_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    try:
        target_id = int(message.text.strip())
        await state.update_data(target_id=target_id)
        await state.set_state(AdminState.waiting_for_sub_balance_amount)
        await message.answer(
            '<b><tg-emoji emoji-id="5452042536493288421">📉</tg-emoji> Введите сумму для списания:</b>\n\n'
            '<i>Для отмены введите /cancel</i>',
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректный ID. Введите число:</b>', parse_mode="HTML")

@dp.message(AdminState.waiting_for_sub_balance_amount)
async def admin_sub_balance_amount_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0: raise ValueError
        data = await state.get_data()
        target_id = data["target_id"]
        diff = -amount
        await update_balance(target_id, diff)
        await state.clear()
        new_bal = get_user_balance(target_id)
        await message.answer(
            f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Успешно списано {amount:.2f} $ у игрока <code>{target_id}</code>!\n'
            f"Новый баланс: {new_bal:.2f} $</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(message.from_user.id),
        )
    except (ValueError, KeyError):
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма. Введите положительное число:</b>', parse_mode="HTML")

@dp.callback_query(F.data == "admin_users_list")
async def admin_users_list_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    if not user_balances:
        await call.message.edit_text(
            '<b><tg-emoji emoji-id="5197514090108456970">👥</tg-emoji> Список пользователей пуст.</b>',
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(call.from_user.id),
        )
        return
    text = '<b><tg-emoji emoji-id="5197514090108456970">👥</tg-emoji> Список пользователей и их балансов:</b>\n\n'
    for uid, bal in user_balances.items():
        text += f"• ID: <code>{uid}</code> | Баланс: <code>{bal:.2f} $</code>\n"
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=get_admin_keyboard(call.from_user.id)
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    total_users = len(user_balances)
    total_balance = sum(user_balances.values())
    active_games_cnt = len(active_games) + len(active_tower_games)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT key, value FROM global_stats")
        rows = await cursor.fetchall()
        stats = {r[0]: r[1] for r in rows}
    total_deposited = stats.get('deposited', 0.0)
    total_withdrawn = stats.get('withdrawn', 0.0)
    total_turnover_all = stats.get('turnover_all', 0.0)
    text = (
        '<b><tg-emoji emoji-id="5452042536493288421">📊</tg-emoji> Статистика бота:</b>\n\n'
        f"<b>• Всего пользователей:</b> <code>{total_users}</code>\n"
        f"<b>• Общая сумма балансов:</b> <code>{total_balance:.2f} $</code>\n"
        f"<b>• Активных игр сейчас:</b> <code>{active_games_cnt}</code>\n"
        f"<b>• Всего депнули:</b> <code>{total_deposited:.2f} $</code>\n"
        f"<b>• Всего вывели:</b> <code>{total_withdrawn:.2f} $</code>\n"
        f"<b>• Общий оборот:</b> <code>{total_turnover_all:.2f} $</code>\n"
        f"<b>• Администраторов:</b> <code>{len(ADMIN_IDS)}</code>"
    )
    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=get_admin_keyboard(call.from_user.id)
    )

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminState.waiting_for_broadcast_text)
    await call.message.edit_text(
        '<b><tg-emoji emoji-id="5449465422971711717">📢</tg-emoji> Введите текст для рассылки всем пользователям:</b>\n\n'
        '<i>Для отмены введите /cancel</i>',
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_broadcast_text)
async def admin_broadcast_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear()
    broadcast_text = message.text
    success = 0
    failed = 0
    status_msg = await message.answer('<b><tg-emoji emoji-id="5451845260055450038">⏳</tg-emoji> Рассылка выполняется...</b>', parse_mode="HTML")
    for uid in list(user_balances.keys()):
        try:
            await message.bot.send_message(
                chat_id=uid, text=broadcast_text, parse_mode="HTML"
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await status_msg.edit_text(
        f'<b><tg-emoji emoji-id="5449465422971711717">📢</tg-emoji> Рассылка завершена!</b>\n\n'
        f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Успешно доставлено:</b> {success}\n'
        f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Не доставлено:</b> {failed}',
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(message.from_user.id),
    )

@dp.callback_query(F.data == "admin_withdraw_requests")
async def admin_withdraw_requests_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    if not withdraw_requests:
        await call.message.edit_text(
            '<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Нет активных заявок на вывод.</b>',
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(call.from_user.id)
        )
        return
    text = '<b><tg-emoji emoji-id="5255868234506213301">📤</tg-emoji> Активные заявки на вывод:</b>\n\n'
    keyboard = []
    for w_id, req in withdraw_requests.items():
        user_link = f'<a href="tg://user?id={req["user_id"]}">{html.quote(req["user_name"])}</a>'
        text += f"• {user_link} (<code>{req['user_id']}</code>): <b>{req['amount']:.2f} $</b>\n"
        keyboard.append([
            InlineKeyboardButton(text=f"✅ Одобрить ({req['user_id']})", callback_data=f"admin_approve_withdraw:{w_id}"),
            InlineKeyboardButton(text=f"❌ Отклонить", callback_data=f"admin_reject_withdraw:{w_id}")
        ])
    keyboard.append([InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_back_main")])
    await call.message.edit_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data == "admin_back_main")
async def admin_back_main_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    await call.message.edit_text(
        '<b><tg-emoji emoji-id="5451807640436903198">⚙️</tg-emoji> Панель администратора:</b>',
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(call.from_user.id)
    )

@dp.callback_query(F.data == "check_subscription_again")
async def check_subscription_again_handler(call: CallbackQuery) -> None:
    is_subbed = await check_subscription(call.bot, call.from_user.id)
    if is_subbed:
        await call.answer("✅ Подписка подтверждена!", show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass
    else:
        await call.answer("❌ Вы подписались не на все каналы!", show_alert=True)

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
user_balances = {}
user_turnover = {}
active_games = {}
game_settings = {}
active_tower_games = {}
tower_game_settings = {}
user_bets_counter = {}
top_modes = {}
user_names = {}
basketball_settings = {}
basketball_coeffs = {
    'гол': 1.9,
    'мимо': 1.4,
    'застрял': 2.75
}
football_settings = {}
football_coeffs = {
    'гол': 1.4,
    'мимо': 1.85,
    'штанга': 2.75
}
created_cheks = {}
user_active_game_msg = {}
withdraw_requests = {}
user_rigged_counters = {}

class MinesState(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_custom_mines = State()

class TowerState(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_custom_traps = State()

class BasketballState(StatesGroup):
    waiting_for_custom_bet = State()

class FootballState(StatesGroup):
    waiting_for_custom_bet = State()

class DiceState(StatesGroup):
    waiting_for_custom_bet = State()

class ChekState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_activations = State()
    waiting_for_password = State()
    waiting_for_check_pass_input = State()
    waiting_for_target_user = State()

class DepositState(StatesGroup):
    waiting_for_method = State()
    waiting_for_amount = State()

class WithdrawState(StatesGroup):
    waiting_for_amount = State()

FIELD_SIZE = 25

# --- ИНТЕГРАЦИЯ CRYPTO BOT ---
async def create_crypto_invoice(amount: float) -> dict:
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount)
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data["result"]
    return None

async def get_crypto_invoice_status(invoice_id: int) -> str:
    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]["status"]
    return "failed"

def generate_check_code() -> str:
    chars = string.ascii_letters + string.digits
    return "chek_" + "".join(random.choices(chars, k=10))

def get_user_balance(user_id: int) -> float:
    return user_balances.setdefault(user_id, 0.00)

def get_user_turnover(user_id: int) -> float:
    return user_turnover.setdefault(user_id, 0.00)

def get_game_settings(user_id: int):
    if user_id not in game_settings:
        game_settings[user_id] = {"bet": 0.10, "mines": 3}
    return game_settings[user_id]

def get_tower_settings(user_id: int):
    if user_id not in tower_game_settings:
        tower_game_settings[user_id] = {"bet": 0.10, "traps": 1}
    return tower_game_settings[user_id]

def get_basketball_settings(user_id: int):
    if user_id not in basketball_settings:
        basketball_settings[user_id] = {"bet": 0.10}
    return basketball_settings[user_id]

def get_football_settings(user_id: int):
    if user_id not in football_settings:
        football_settings[user_id] = {"bet": 0.10}
    return football_settings[user_id]

# Клавиатуры
menu_inline_keyboard_no_bottom = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Профиль", icon_custom_emoji_id="5308004189677330658", callback_data="open_profile")],
        [InlineKeyboardButton(text="Топ за все время", icon_custom_emoji_id="5307942883314147223", callback_data="open_top_menu")],
        [
            InlineKeyboardButton(text="Играть", icon_custom_emoji_id="5471895876790161593", callback_data="back_to_games"),
            InlineKeyboardButton(text="Кошелек", icon_custom_emoji_id="5197686464325915345", callback_data="open_wallet_inline"),
        ],
        [InlineKeyboardButton(text="Чеки", icon_custom_emoji_id="5452157517062770940", callback_data="open_cheks_menu")],
    ]
)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Кошелек", icon_custom_emoji_id="5197686464325915345"),
            KeyboardButton(text="Играть", icon_custom_emoji_id="5471895876790161593"),
            KeyboardButton(text="Меню", icon_custom_emoji_id="4958624886663678191"),
        ]
    ],
    resize_keyboard=True,
)

menu_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Профиль", icon_custom_emoji_id="5308004189677330658", callback_data="open_profile")],
        [InlineKeyboardButton(text="Топ за все время", icon_custom_emoji_id="5307942883314147223", callback_data="open_top_menu")],
        [
            InlineKeyboardButton(text="Играть", icon_custom_emoji_id="5471895876790161593", callback_data="back_to_games"),
            InlineKeyboardButton(text="Кошелек", icon_custom_emoji_id="5197686464325915345", callback_data="open_wallet_inline"),
        ],
        [InlineKeyboardButton(text="Чеки", icon_custom_emoji_id="5452157517062770940", callback_data="open_cheks_menu")],
    ]
)

wallet_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Пополнить", icon_custom_emoji_id="5255805270285653933", callback_data="deposit"),
            InlineKeyboardButton(text="Вывести", icon_custom_emoji_id="5255868234506213301", callback_data="withdraw"),
        ]
    ]
)

profile_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Пополнить", icon_custom_emoji_id="5255805270285653933", callback_data="deposit"),
            InlineKeyboardButton(text="Вывести", icon_custom_emoji_id="5255868234506213301", callback_data="withdraw"),
        ],
        [InlineKeyboardButton(text="◀ Назад", callback_data="close_profile")],
    ]
)

games_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Мины", icon_custom_emoji_id="5452018153963948977", callback_data="mines_choose_bet"),
            InlineKeyboardButton(text="Башня", icon_custom_emoji_id="5449397725697187601", callback_data="tower_choose_bet")
        ],
        [InlineKeyboardButton(text="Баскетбол", icon_custom_emoji_id="5465317563145686803", callback_data="basketball_choose_bet")],
        [InlineKeyboardButton(text="Футбол", icon_custom_emoji_id="5319298377412812014", callback_data="football_choose_bet")],
        [InlineKeyboardButton(text="Куб", icon_custom_emoji_id="5451788978804001506", callback_data="dice_choose_bet")]
    ]
)

def get_top_keyboard(mode: str) -> InlineKeyboardMarkup:
    turnover_emoji = "5312019687746349814" if mode == "turnover" else "5307942883314147223"
    balance_emoji = "5312019687746349814" if mode == "balance" else "5197422813463483902"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Оборот", icon_custom_emoji_id=turnover_emoji, callback_data="top_mode_turnover"),
                InlineKeyboardButton(text="Баланс", icon_custom_emoji_id=balance_emoji, callback_data="top_mode_balance"),
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data="close_profile")],
        ]
    )

def generate_top_text(user_id: int) -> str:
    mode = top_modes.get(user_id, "turnover")
    all_users = set(user_balances.keys()).union(set(user_turnover.keys()))
    users_data = []
    for uid in all_users:
        bal = get_user_balance(uid)
        turn = get_user_turnover(uid)
        users_data.append({"id": uid, "balance": bal, "turnover": turn})
    
    if mode == "turnover":
        users_data.sort(key=lambda x: x["turnover"], reverse=True)
        mode_title = "по обороту"
    else:
        users_data.sort(key=lambda x: x["balance"], reverse=True)
        mode_title = "по балансу"
    
    top_10 = users_data[:10]
    text = f'<b><tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Топ за все время ({mode_title}):</b>\n\n'
    if not top_10:
        text += "Список лидеров пока пуст."
    else:
        for idx, udata in enumerate(top_10, 1):
            uid = udata["id"]
            val = udata["turnover"] if mode == "turnover" else udata["balance"]
            nickname = user_names.get(uid, f"Игрок {uid}")
            prem_emoji = '<tg-emoji emoji-id="5449789954995559460">💎</tg-emoji>'
            dollar_emoji = '<tg-emoji emoji-id="5197422813463483902">💵</tg-emoji>'
            text += f"{idx}. {nickname} - {prem_emoji} {val:.2f} {dollar_emoji}\n"
    return text

@dp.callback_query(F.data == "open_top_menu")
async def open_top_menu_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    user_id = call.from_user.id
    if user_id not in top_modes:
        top_modes[user_id] = "turnover"
    text = generate_top_text(user_id)
    await safe_edit_message(call, text, get_top_keyboard(top_modes[user_id]))

@dp.callback_query(F.data == "top_mode_turnover")
async def top_mode_turnover_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    user_id = call.from_user.id
    top_modes[user_id] = "turnover"
    text = generate_top_text(user_id)
    await safe_edit_message(call, text, get_top_keyboard("turnover"))

@dp.callback_query(F.data == "top_mode_balance")
async def top_mode_balance_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    user_id = call.from_user.id
    top_modes[user_id] = "balance"
    text = generate_top_text(user_id)
    await safe_edit_message(call, text, get_top_keyboard("balance"))

def get_cheks_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать чек", callback_data="chek_create_start")],
            [InlineKeyboardButton(text="Активные чеки", callback_data="chek_active_list")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="close_profile")],
        ]
    )

def get_chek_amount_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.1$", callback_data="chek_amount_0.1"),
                InlineKeyboardButton(text="Весь баланс", callback_data="chek_amount_all"),
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data="open_cheks_menu")],
        ]
    )

def get_chek_manage_keyboard(chek_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Поделиться", switch_inline_query=f"{chek_id}"),
                InlineKeyboardButton(text="Скопировать", icon_custom_emoji_id="5377535110289576661", callback_data=f"chek_copy_link:{chek_id}"),
            ],
            [
                InlineKeyboardButton(text="Ограничения", icon_custom_emoji_id="5312462735097764089", callback_data=f"chek_limits_menu:{chek_id}"),
                InlineKeyboardButton(text="Удалить чек", icon_custom_emoji_id="5296410453742753454", callback_data=f"chek_delete:{chek_id}"),
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data="open_cheks_menu")],
        ]
    )

def get_chek_limits_keyboard(chek_id: str) -> InlineKeyboardMarkup:
    chek = created_cheks.get(chek_id, {})
    if chek.get("password"):
        pass_text = "Удалить пароль"
        pass_emoji = "5444856076954520455"
        pass_cbd = f"chek_remove_pass:{chek_id}"
    else:
        pass_text = "Поставить пароль"
        pass_emoji = "5312281637801729565"
        pass_cbd = f"chek_set_pass:{chek_id}"
    
    prem_text = "Для всех игроков" if chek.get("only_premium") else "Только для TG Premium"
    
    if chek.get("target_user"):
        pin_limit_text = "Открепить чек"
        pin_limit_cbd = f"chek_unpin_user:{chek_id}"
    else:
        pin_limit_text = "Закрепить за пользователем"
        pin_limit_cbd = f"chek_pin_user:{chek_id}"
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=pass_text, icon_custom_emoji_id=pass_emoji, callback_data=pass_cbd)],
            [InlineKeyboardButton(text=prem_text, icon_custom_emoji_id="5303170015007119865", callback_data=f"chek_toggle_premium:{chek_id}")],
            [InlineKeyboardButton(text=pin_limit_text, icon_custom_emoji_id="5197269100878907942", callback_data=pin_limit_cbd)],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"chek_manage:{chek_id}")],
        ]
    )

def get_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.1$", callback_data=f"select_bet_0.1:{owner_id}"),
                InlineKeyboardButton(text="0.5$", callback_data=f"select_bet_0.5:{owner_id}"),
                InlineKeyboardButton(text="1$", callback_data=f"select_bet_1.0:{owner_id}"),
            ],
            [InlineKeyboardButton(text="✏️ Своя ставка", callback_data=f"custom_bet_mines:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

def get_preview_game_keyboard(user_id: int, owner_id: int = None) -> InlineKeyboardMarkup:
    if owner_id is None:
        owner_id = user_id
    st = get_game_settings(user_id)
    bet = st["bet"]
    mines = st["mines"]
    keyboard = []
    for _ in range(5):
        row = [InlineKeyboardButton(text="🌑", callback_data="locked_cell") for _ in range(5)]
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton(text=f"Играть {bet:.2f}", icon_custom_emoji_id="5305445793623218874", callback_data=f"start_mines_game:{owner_id}")
    ])
    keyboard.append([
        InlineKeyboardButton(text=f"💣 Мин: {mines}", callback_data=f"screen_choose_mines:{owner_id}"),
        InlineKeyboardButton(text="◀ Ставка", callback_data=f"mines_choose_bet:{owner_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_mines_count_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="2", callback_data=f"set_mines_cnt_2:{owner_id}"),
                InlineKeyboardButton(text="3", callback_data=f"set_mines_cnt_3:{owner_id}"),
                InlineKeyboardButton(text="5", callback_data=f"set_mines_cnt_5:{owner_id}"),
                InlineKeyboardButton(text="10", callback_data=f"set_mines_cnt_10:{owner_id}"),
            ],
            [
                InlineKeyboardButton(text="15", callback_data=f"set_mines_cnt_15:{owner_id}"),
                InlineKeyboardButton(text="20", callback_data=f"set_mines_cnt_20:{owner_id}"),
                InlineKeyboardButton(text="24", callback_data=f"set_mines_cnt_24:{owner_id}"),
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"screen_game_confirm:{owner_id}")],
        ]
    )

def build_game_keyboard(game_data: dict, finished: bool = False) -> InlineKeyboardMarkup:
    keyboard = []
    opened = game_data["opened"]
    game_over = game_data["game_over"]
    mines_positions = game_data["mines_positions"]
    game_id = game_data.get("game_id", game_data.get("owner_id"))
    owner_id = game_data["owner_id"]
    
    for row in range(5):
        row_buttons = []
        for col in range(5):
            idx = row * 5 + col
            if idx in opened:
                if idx in mines_positions:
                    text = "💥"
                else:
                    text = "🎁"
            elif game_over and idx in mines_positions:
                text = "💣"
            else:
                text = "🌑"
            row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"open_cell_{idx}:{game_id}"))
        keyboard.append(row_buttons)
    
    if not game_over and len(opened) > 0:
        current_win = game_data["current_win"]
        keyboard.append([
            InlineKeyboardButton(text=f"Забрать {current_win:.2f}", icon_custom_emoji_id="5305445793623218874", callback_data=f"cashout_mines:{game_id}")
        ])
    
    if finished:
        keyboard.append([
            InlineKeyboardButton(text="🔄 Сыграть снова", callback_data=f"screen_game_confirm:{owner_id}"),
            InlineKeyboardButton(text="◀ Меню", callback_data=f"mines_choose_bet:{owner_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def calculate_multiplier(mines_count: int, opened_count: int) -> float:
    base = 1.0 + (mines_count * 0.05)
    mult = base ** opened_count
    return max(round(mult, 2), 1.01)

def build_profile_text(user_id: int, full_name: str) -> str:
    balance = get_user_balance(user_id)
    turnover = get_user_turnover(user_id)
    return (
        f'<b><tg-emoji emoji-id="5197514090108456970">👤</tg-emoji> Имя: {html.quote(full_name)}\n</b>'
        f'<b><tg-emoji emoji-id="5449624985301717991">💳</tg-emoji> Ваш ID: {user_id}\n</b>'
        f'<b><tg-emoji emoji-id="5451845260055450038">💰</tg-emoji> Баланс: {balance:.2f} <tg-emoji emoji-id="5197422813463483902">💵</tg-emoji>\n</b>'
        f'<b><tg-emoji emoji-id="5452042536493288421">📊</tg-emoji> Оборот: {turnover:.2f} <tg-emoji emoji-id="5197422813463483902">💵</tg-emoji></b>'
    )

TOWER_FLOORS = 8

def calculate_tower_multiplier(traps_count: int, floor: int) -> float:
    safe_count = 5 - traps_count
    mult = (5 / safe_count) ** floor
    return max(round(mult, 2), 1.01)

def get_tower_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.1$", callback_data=f"select_tower_bet_0.1:{owner_id}"),
                InlineKeyboardButton(text="0.5$", callback_data=f"select_tower_bet_0.5:{owner_id}"),
                InlineKeyboardButton(text="1$", callback_data=f"select_tower_bet_1.0:{owner_id}"),
            ],
            [InlineKeyboardButton(text="✏️ Своя ставка", callback_data=f"custom_bet_tower:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

def get_preview_tower_keyboard(user_id: int, owner_id: int = None) -> InlineKeyboardMarkup:
    if owner_id is None:
        owner_id = user_id
    st = get_tower_settings(user_id)
    bet = st["bet"]
    traps = st["traps"]
    keyboard = []
    for floor_idx in range(TOWER_FLOORS):
        x_mult = calculate_tower_multiplier(traps, floor_idx + 1)
        row = [InlineKeyboardButton(text=f"x{x_mult:.1f}", callback_data="locked_cell")]
        row.extend([InlineKeyboardButton(text="🌑", callback_data="locked_cell") for _ in range(5)])
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton(text=f"Играть {bet:.2f}", icon_custom_emoji_id="5305445793623218874", callback_data=f"start_tower_game:{owner_id}")
    ])
    keyboard.append([
        InlineKeyboardButton(text=f"💣 Мин: {traps}", callback_data=f"screen_choose_tower_traps:{owner_id}"),
        InlineKeyboardButton(text="◀ Ставка", callback_data=f"tower_choose_bet:{owner_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_tower_traps_count_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data=f"set_tower_traps_cnt_1:{owner_id}"),
                InlineKeyboardButton(text="2", callback_data=f"set_tower_traps_cnt_2:{owner_id}"),
                InlineKeyboardButton(text="3", callback_data=f"set_tower_traps_cnt_3:{owner_id}"),
                InlineKeyboardButton(text="4", callback_data=f"set_tower_traps_cnt_4:{owner_id}"),
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"screen_tower_game_confirm:{owner_id}")],
        ]
    )

def build_tower_game_keyboard(game_data: dict, finished: bool = False) -> InlineKeyboardMarkup:
    keyboard = []
    current_floor = game_data["current_floor"]
    history = game_data["history"]
    game_over = game_data["game_over"]
    trap_positions = game_data["trap_positions"]
    traps_count = game_data["traps_count"]
    game_id = game_data.get("game_id", game_data.get("owner_id"))
    owner_id = game_data["owner_id"]
    
    for floor_idx in range(TOWER_FLOORS):
        row_buttons = []
        x_mult = calculate_tower_multiplier(traps_count, floor_idx + 1)
        row_buttons.append(InlineKeyboardButton(text=f"x{x_mult:.1f}", callback_data="locked_cell"))
        
        is_active_row = (floor_idx == current_floor) and not game_over
        is_passed = floor_idx < current_floor
        
        for col in range(5):
            if floor_idx in history:
                chosen_col, is_win = history[floor_idx]
                if col == chosen_col:
                    text = "🎁" if is_win else "💥"
                elif col in trap_positions[floor_idx]:
                    text = "💣"
                else:
                    text = "🌑"
                cbd = "locked_cell"
            elif is_passed:
                if col in trap_positions[floor_idx]:
                    text = "💣"
                else:
                    text = "🌑"
                cbd = "locked_cell"
            elif game_over:
                if col in trap_positions[floor_idx]:
                    text = "💣"
                else:
                    text = "🌑"
                cbd = "locked_cell"
            elif is_active_row:
                text = "🌑"
                cbd = f"open_tower_{floor_idx}_{col}:{game_id}"
            else:
                text = "🌑"
                cbd = "locked_cell"
            row_buttons.append(InlineKeyboardButton(text=text, callback_data=cbd))
        keyboard.append(row_buttons)
    
    if not game_over and current_floor > 0:
        current_win = game_data["current_win"]
        keyboard.append([
            InlineKeyboardButton(text=f"Забрать {current_win:.2f}", icon_custom_emoji_id="5305445793623218874", callback_data=f"cashout_tower:{game_id}")
        ])
    
    if finished:
        keyboard.append([
            InlineKeyboardButton(text="🔄 Сыграть снова", callback_data=f"screen_tower_game_confirm:{owner_id}"),
            InlineKeyboardButton(text="◀ Меню", callback_data=f"tower_choose_bet:{owner_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- БАСКЕТБОЛ ---
def get_basketball_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.1$", callback_data=f"select_basketball_bet_0.1:{owner_id}"),
                InlineKeyboardButton(text="0.5$", callback_data=f"select_basketball_bet_0.5:{owner_id}"),
                InlineKeyboardButton(text="1$", callback_data=f"select_basketball_bet_1.0:{owner_id}"),
            ],
            [InlineKeyboardButton(text="✏️ Своя ставка", callback_data=f"custom_bet_basketball:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

def get_basketball_type_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Гол (x{basketball_coeffs['гол']})", callback_data=f"basketball_bet_гол_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Мимо (x{basketball_coeffs['мимо']})", callback_data=f"basketball_bet_мимо_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Застрял (x{basketball_coeffs['застрял']})", callback_data=f"basketball_bet_застрял_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="◀ Изменить ставку", callback_data=f"basketball_choose_bet:{owner_id}")],
        ]
    )

def get_basketball_result_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏀 Сыграть ещё", callback_data=f"basketball_repeat_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад к играм", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

def get_basketball_bet_type_name(bet_type: str) -> str:
    names = {'гол': 'Гол', 'мимо': 'Мимо', 'застрял': 'Застрял'}
    return names.get(bet_type, bet_type)

def calculate_basketball_result(basketball_value: int, bet_type: str):
    result = {'win': False, 'multiplier': 0}
    if bet_type == 'гол':
        result['win'] = basketball_value in [4, 5]
        result['multiplier'] = basketball_coeffs['гол']
    elif bet_type == 'мимо':
        result['win'] = basketball_value in [1, 2]
        result['multiplier'] = basketball_coeffs['мимо']
    elif bet_type == 'застрял':
        result['win'] = basketball_value == 3
        result['multiplier'] = basketball_coeffs['застрял']
    return result

# --- ФУТБОЛ ---
def get_football_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.1$", callback_data=f"select_football_bet_0.1:{owner_id}"),
                InlineKeyboardButton(text="0.5$", callback_data=f"select_football_bet_0.5:{owner_id}"),
                InlineKeyboardButton(text="1$", callback_data=f"select_football_bet_1.0:{owner_id}"),
            ],
            [InlineKeyboardButton(text="✏️ Своя ставка", callback_data=f"custom_bet_football:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

def get_football_type_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Гол (x{football_coeffs['гол']})", callback_data=f"football_bet_гол_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Мимо (x{football_coeffs['мимо']})", callback_data=f"football_bet_мимо_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Штанга (x{football_coeffs['штанга']})", callback_data=f"football_bet_штанга_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="◀ Изменить ставку", callback_data=f"football_choose_bet:{owner_id}")],
        ]
    )

def get_football_result_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚽ Сыграть ещё", callback_data=f"football_repeat_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад к играм", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

def get_football_bet_type_name(bet_type: str) -> str:
    names = {'гол': 'Гол', 'мимо': 'Мимо', 'штанга': 'Штанга'}
    return names.get(bet_type, bet_type)

def calculate_football_result(football_value: int, bet_type: str):
    result = {'win': False, 'multiplier': 0}
    if bet_type == 'гол':
        result['win'] = football_value in [3, 4, 5]
        result['multiplier'] = football_coeffs['гол']
    elif bet_type == 'мимо':
        result['win'] = football_value in [1, 6]
        result['multiplier'] = football_coeffs['мимо']
    elif bet_type == 'штанга':
        result['win'] = football_value == 2
        result['multiplier'] = football_coeffs['штанга']
    return result

# --- КУБ ---
DICE_EMOJI_ID = "5451788978804001506"
DICE_COEFF_1 = 1.9
DICE_COEFF_2 = 3.8
DICE_COEFF_SEVEN = 6.0

def get_dice_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.1$", callback_data=f"select_dice_bet_0.1:{owner_id}"),
                InlineKeyboardButton(text="0.5$", callback_data=f"select_dice_bet_0.5:{owner_id}"),
                InlineKeyboardButton(text="1$", callback_data=f"select_dice_bet_1.0:{owner_id}"),
            ],
            [InlineKeyboardButton(text="✏️ Своя ставка", callback_data=f"custom_bet_dice:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

def get_dice_type_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Чет (x{DICE_COEFF_1})", callback_data=f"dice_bet_even_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Нечет (x{DICE_COEFF_1})", callback_data=f"dice_bet_odd_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Больше (x{DICE_COEFF_1})", callback_data=f"dice_bet_more_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Меньше (x{DICE_COEFF_1})", callback_data=f"dice_bet_less_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="🎲 2 Куба", callback_data=f"dice_2_menu_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="◀ Изменить ставку", callback_data=f"dice_choose_bet:{owner_id}")],
        ]
    )

def get_dice_2_menu_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Чет (x{DICE_COEFF_2})", callback_data=f"dice2_bet_even_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Нечет (x{DICE_COEFF_2})", callback_data=f"dice2_bet_odd_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Больше 7 (x{DICE_COEFF_2})", callback_data=f"dice2_bet_more_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Меньше 7 (x{DICE_COEFF_2})", callback_data=f"dice2_bet_less_{bet}:{owner_id}")],
            [InlineKeyboardButton(text=f"Ровно 7 (x{DICE_COEFF_SEVEN})", callback_data=f"dice2_bet_seven_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"dice_type_menu_{bet}:{owner_id}")],
        ]
    )

def get_dice_result_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Сыграть ещё", callback_data=f"dice_repeat_{bet}:{owner_id}")],
            [InlineKeyboardButton(text="◀ Назад к играм", callback_data=f"back_to_games:{owner_id}")],
        ]
    )

async def safe_edit_message(call: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    try:
        await call.message.edit_text(text=text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer()
        else:
            raise e

def check_owner(call: CallbackQuery, owner_id: int) -> bool:
    if call.from_user.id != owner_id:
        return False
    return True

@dp.callback_query(F.data == "locked_cell")
async def locked_cell_handler(call: CallbackQuery) -> None:
    await call.answer()

# --- ПОПОЛНЕНИЕ ---
@dp.callback_query(F.data == "deposit")
async def deposit_start_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    await state.set_state(DepositState.waiting_for_method)
    text = '<b><tg-emoji emoji-id="5449789954995559460">💎</tg-emoji> Выберите способ пополнения:</b>'
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="XRocket", icon_custom_emoji_id="5451692831666112994", callback_data="deposit_method_xrocket")],
            [InlineKeyboardButton(text="CryptoBot", icon_custom_emoji_id="5452124248246096392", callback_data="deposit_method_cryptobot")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="open_wallet_inline")]
        ]
    )
    await safe_edit_message(call, text, kb)

@dp.callback_query(F.data.startswith("deposit_method_"))
async def deposit_method_selected(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    method = call.data.split("_")[2]
    if method == "xrocket":
        user_id = call.from_user.id
        text = (
            '<b><tg-emoji emoji-id="5451692831666112994">🚀</tg-emoji> Пополнение через XRocket</b>\n\n'
            '1. Нажмите кнопку ниже для оплаты\n'
            '2. <b>ОБЯЗАТЕЛЬНО</b> укажите ваш ID в комментарии к платежу:\n'
            f'<code>{user_id}</code>\n\n'
            '<i>Без указания ID баланс не будет зачислен автоматически!</i>'
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💵 Оплатить через XRocket", url=XROCKET_LINK)],
                [InlineKeyboardButton(text="✅ Я оплатил (Проверить)", callback_data=f"manual_deposit_check:{user_id}")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="deposit")]
            ]
        )
        await safe_edit_message(call, text, kb)
    else:
        await state.update_data(deposit_method=method)
        await state.set_state(DepositState.waiting_for_amount)
        text = (
            f'<tg-emoji emoji-id="5449789954995559460">💎</tg-emoji> <b>Введите сумму для пополнения через CryptoBot в USDT (например: 0.10):</b>\n\n'
            '<i>Для отмены введите /cancel</i>'
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="deposit")]])
        await safe_edit_message(call, text, kb)

@dp.callback_query(F.data.startswith("manual_deposit_check:"))
async def manual_deposit_check_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    user_id = int(call.data.split(":")[1])
    if call.from_user.id != user_id:
        await call.answer("Это чужая кнопка!", show_alert=True)
        return
    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm_deposit:{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_deposit:{user_id}")
            ]
        ]
    )
    user_link = f'<a href="tg://user?id={user_id}">{html.quote(call.from_user.full_name)}</a>'
    admin_text = (
        f'<b><tg-emoji emoji-id="5451692831666112994">🚀</tg-emoji> Заявка на ручное пополнение (XRocket)!</b>\n\n'
        f'<b>Игрок:</b> {user_link} (<code>{user_id}</code>)\n'
        f'<i>Проверьте поступление на кошельке XRocket и подтвердите.</i>'
    )
    for admin_id in ADMIN_IDS:
        try:
            await call.bot.send_message(admin_id, admin_text, parse_mode="HTML", reply_markup=admin_kb)
        except Exception:
            pass
    await call.answer("✅ Заявка отправлена администраторам! Ожидайте зачисления.", show_alert=True)

@dp.callback_query(F.data.startswith("admin_confirm_deposit:"))
async def admin_confirm_deposit_handler(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    user_id = int(call.data.split(":")[1])
    await state.update_data(target_deposit_user=user_id)
    await state.set_state(AdminState.waiting_for_manual_deposit_confirm)
    await call.message.edit_text(
        f'<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите сумму пополнения для пользователя <code>{user_id}</code>:</b>',
        parse_mode="HTML"
    )

@dp.message(AdminState.waiting_for_manual_deposit_confirm)
async def admin_confirm_deposit_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0: raise ValueError
        data = await state.get_data()
        user_id = data["target_deposit_user"]
        await update_balance(user_id, amount)
        await update_global_stat('deposited', amount)
        await state.clear()
        await message.answer(
            f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Баланс пользователя <code>{user_id}</code> пополнен на {amount:.2f} $!</b>',
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(message.from_user.id)
        )
        try:
            await message.bot.send_message(
                user_id,
                f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Ваше пополнение через XRocket подтверждено! Зачислено: {amount:.2f} $</b>',
                parse_mode="HTML"
            )
        except: pass
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма.</b>', parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_reject_deposit:"))
async def admin_reject_deposit_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    user_id = int(call.data.split(":")[1])
    await call.answer("Заявка отклонена", show_alert=True)
    try:
        await call.message.edit_text(f'<b>❌ Заявка на пополнение от <code>{user_id}</code> отклонена.</b>', parse_mode="HTML")
        await call.bot.send_message(user_id, '<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Ваше пополнение через XRocket отклонено администратором.</b>', parse_mode="HTML")
    except: pass

@dp.message(DepositState.waiting_for_amount)
async def deposit_amount_process(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)
        return
    if not await force_subscription_check(message, state): return
    try:
        amount = float(message.text.replace("$", "").replace(",", ".").strip())
        if amount < 0.1:
            raise ValueError
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Введите корректную сумму больше 0.1 USDT или /cancel для отмены:</b>', parse_mode="HTML")
        return
    
    data = await state.get_data()
    method = data.get("deposit_method", "cryptobot")
    await state.clear()
    invoice = await create_crypto_invoice(amount)
    if not invoice:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Ошибка создания счета. Попробуйте позже.</b>', parse_mode="HTML")
        return
    invoice_id = invoice["invoice_id"]
    pay_url = invoice["pay_url"]
    check_data = f"check_pay_crypto:{invoice_id}:{amount}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💵 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=check_data)],
            [InlineKeyboardButton(text="◀ Назад", callback_data="open_wallet_inline")]
        ]
    )
    await message.answer(
        f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Счет на пополнение {amount:.2f} USDT создан!</b>\n\nОплатите его по кнопке ниже и нажмите «Проверить оплату»:',
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("check_pay_"))
async def check_pay_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    method = parts[1]
    invoice_id = parts[2]
    amount = float(parts[3])
    status = "failed"
    if method == "crypto":
        status = await get_crypto_invoice_status(int(invoice_id))
    if status == "paid":
        user_id = call.from_user.id
        await update_balance(user_id, amount)
        await update_global_stat('deposited', amount)
        await call.answer("✅ Оплата успешно подтверждена!", show_alert=True)
        text = f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Баланс успешно пополнен на {amount:.2f} $!</b>'
        await safe_edit_message(call, text, wallet_inline_keyboard)
    else:
        await call.answer("❌ Счет еще не оплачен!", show_alert=True)

# --- ВЫВОД ---
@dp.callback_query(F.data == "withdraw")
async def withdraw_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    await state.set_state(WithdrawState.waiting_for_amount)
    text = (
        '<b><tg-emoji emoji-id="5255868234506213301">📤</tg-emoji> Вывод средств</b>\n\n'
        '<b>Введите сумму для вывода в USDT (минимум 1.10 $):</b>\n\n'
        '<i><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Для отмены введите /cancel</i>'
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="open_wallet_inline")]])
    await safe_edit_message(call, text, kb)

@dp.message(WithdrawState.waiting_for_amount)
async def withdraw_amount_process(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)
        return
    if not await force_subscription_check(message, state): return
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    
    # Проверки вагера и депозита
    total_dep, wager_rem = await get_user_wager_info(user_id)
    
    if total_dep < MIN_DEPOSIT_FOR_WITHDRAW:
        await message.answer(
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Для вывода необходимо пополнить баланс минимум на {MIN_DEPOSIT_FOR_WITHDRAW:.2f}$!</b>',
            parse_mode="HTML"
        )
        await state.clear()
        return
        
    if wager_rem > 0.01:
        prem_emoji = '<tg-emoji emoji-id="5449789954995559460">💎</tg-emoji>'
        await message.answer(
            f'<b>{prem_emoji} Отработайте вагер для вывода!</b>\n\n'
            f'<b>Осталось отыграть:</b> <code>{wager_rem:.2f} $</code>',
            parse_mode="HTML"
        )
        await state.clear()
        return

    try:
        amount = float(message.text.replace("$", "").replace(",", ".").strip())
        if amount < 1.10:
            await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Минимальная сумма вывода 1.10 $ (или /cancel для отмены):</b>', parse_mode="HTML")
            return
        if amount > balance:
            await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств на балансе! (или /cancel для отмены)</b>', parse_mode="HTML")
            return
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Введите корректное число (или /cancel для отмены):</b>', parse_mode="HTML")
        return
    
    await state.clear()
    user_balances[user_id] -= amount
    await update_balance(user_id, -amount)
    withdraw_id = "w_" + "".join(random.choices(string.digits, k=6))
    withdraw_requests[withdraw_id] = {
        "user_id": user_id,
        "amount": amount,
        "user_name": message.from_user.full_name
    }
    await message.answer(
        f'<b><tg-emoji emoji-id="5451845260055450038">⏳</tg-emoji> Ваша заявка на вывод {amount:.2f} $ успешно отправлена администратору на обработку!</b>',
        parse_mode="HTML"
    )
    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_withdraw:{withdraw_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_withdraw:{withdraw_id}")
            ]
        ]
    )
    user_link = f'<a href="tg://user?id={user_id}">{html.quote(message.from_user.full_name)}</a>'
    admin_text = (
        f'<b><tg-emoji emoji-id="5255868234506213301">📤</tg-emoji> Новая заявка на вывод!</b>\n\n'
        f'<b>Игрок:</b> {user_link} (<code>{user_id}</code>)\n'
        f'<b>Сумма:</b> <code>{amount:.2f} $</code>'
    )
    for admin_id in ADMIN_IDS:
        if admin_id == user_id: continue
        try:
            await message.bot.send_message(admin_id, admin_text, parse_mode="HTML", reply_markup=admin_kb)
        except Exception:
            pass

@dp.callback_query(F.data.startswith("admin_approve_withdraw:"))
async def admin_approve_withdraw_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    withdraw_id = call.data.split(":")[1]
    req = withdraw_requests.get(withdraw_id)
    if not req:
        await call.answer("Заявка не найдена или уже обработана!", show_alert=True)
        return
    await state.update_data(target_withdraw_id=withdraw_id)
    await state.set_state(AdminState.waiting_for_withdraw_check_url)
    await call.message.edit_text(
        f'<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите ссылку на чек (или отправьте сам чек) для игрока <code>{req["user_id"]}</code> (Сумма: {req["amount"]:.2f} $):</b>\n\n'
        '<i>Для отмены введите /cancel</i>',
        parse_mode="HTML"
    )

@dp.message(AdminState.waiting_for_withdraw_check_url)
async def admin_approve_withdraw_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS: return
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML")
        return
    data = await state.get_data()
    withdraw_id = data.get("target_withdraw_id")
    req = withdraw_requests.get(withdraw_id)
    if not req:
        await message.answer("Ошибка: заявка не найдена!", parse_mode="HTML")
        await state.clear()
        return
    check_url = message.text.strip()
    user_id = req["user_id"]
    amount = req["amount"]
    user_name = req["user_name"]
    await state.clear()
    await update_global_stat('withdrawn', amount)
    user_text = (
        f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Ваша заявка на вывод одобрена!\n\n'
        f'Ваш чек: <a href="{check_url}">{check_url}</a></b>'
    )
    try:
        await message.bot.send_message(user_id, user_text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Failed to send withdraw notification to user: {e}")
    try:
        user_link = f'<a href="tg://user?id={user_id}">{html.quote(user_name)}</a>'
        channel_text = f'<tg-emoji emoji-id="5452031425412895584">🚀</tg-emoji> <b>Вывод {amount:.2f}$, {user_link}</b>'
        sent_msg = await message.bot.send_message(WITHDRAW_CHANNEL, channel_text, parse_mode="HTML")
        try:
            await sent_msg.pin()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to post withdraw to channel: {e}")
    await message.answer(
        f'<b><tg-emoji emoji-id="5452168761287152584">✅</tg-emoji> Вывод на {amount:.2f} $ пользователю <code>{user_id}</code> успешно подтвержден и отправлен!</b>',
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(message.from_user.id)
    )
    del withdraw_requests[withdraw_id]

@dp.callback_query(F.data.startswith("admin_reject_withdraw:"))
async def admin_reject_withdraw_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS: return
    withdraw_id = call.data.split(":")[1]
    req = withdraw_requests.get(withdraw_id)
    if not req:
        await call.answer("Заявка не найдена или уже обработана!", show_alert=True)
        return
    user_id = req["user_id"]
    amount = req["amount"]
    user_balances[user_id] = get_user_balance(user_id) + amount
    await update_balance(user_id, amount)
    try:
        await call.bot.send_message(
            user_id,
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Ваша заявка на вывод {amount:.2f} $ была отклонена администратором. Средства возвращены на баланс.</b>',
            parse_mode="HTML"
        )
    except Exception:
        pass
    await safe_edit_message(
        call,
        f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Заявка на вывод от <code>{user_id}</code> отклонена. Средства возвращены на счет.</b>',
        get_admin_keyboard(call.from_user.id)
    )
    del withdraw_requests[withdraw_id]

# --- ЧЕКИ ---
@dp.callback_query(F.data == "open_cheks_menu")
async def open_cheks_menu_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    await state.clear()
    text = (
        '<b><tg-emoji emoji-id="5307773751796996779">🎟</tg-emoji> </b>'
        '<b>Создайте чек для мгновенной отправки средств пользователю или группе пользователей - '
        'просто укажите количество активаций!</b>'
    )
    await safe_edit_message(call, text, get_cheks_main_keyboard())

@dp.callback_query(F.data == "chek_create_start")
async def chek_create_start_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    if call.message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await call.answer()
        await call.message.answer('<b>Перейдите в личные сообщения с ботом <tg-emoji emoji-id="5312140414982071786">❌</tg-emoji></b>', parse_mode="HTML")
        return
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    if balance <= 0:
        await call.answer("❌ У вас недостаточный баланс для создания чека!", show_alert=True)
        return
    await state.set_state(ChekState.waiting_for_amount)
    text = (
        '<b><tg-emoji emoji-id="5449526218233779946">👛</tg-emoji> Введите сумму ОДНОЙ активации (например: 0.50):</b>\n\n'
        '<i>Для отмены введите /cancel</i>'
    )
    await safe_edit_message(call, text, get_chek_amount_keyboard())

@dp.callback_query(F.data.startswith("chek_amount_"))
async def process_chek_quick_amount(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    choice = call.data.split("_")[2]
    if choice == "0.1":
        amount = 0.10
    else:
        amount = balance
    if amount > balance or amount <= 0:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
    await state.update_data(chek_amount=amount)
    await state.set_state(ChekState.waiting_for_activations)
    text = (
        '<b><tg-emoji emoji-id="5197514090108456970">👥</tg-emoji> Введите количество активаций для чека (целое число от 1 и выше):\n'
        'Каждый активировавший получит указанную сумму.</b>\n\n'
        '<i>Для отмены введите /cancel</i>'
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="open_cheks_menu")]])
    await safe_edit_message(call, text, kb)

@dp.message(ChekState.waiting_for_amount)
async def process_chek_amount_input(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)
        return
    if not await force_subscription_check(message, state): return
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await message.answer('Перейдите в личные сообщения с ботом <tg-emoji emoji-id="5312140414982071786">❌</tg-emoji>', parse_mode="HTML")
        return
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        amount = float(raw_text)
        if amount <= 0 or amount > balance:
            raise ValueError
        await state.update_data(chek_amount=amount)
        await state.set_state(ChekState.waiting_for_activations)
        text = (
            '<b><tg-emoji emoji-id="5197514090108456970">👥</tg-emoji> Введите количество активаций для чека (целое число от 1 и выше):\n'
            'Каждый активировавший получит указанную сумму.</b>\n\n'
            '<i>Для отмены введите /cancel</i>'
        )
        await message.answer(text, parse_mode="HTML")
    except ValueError:
        await message.answer(
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма! Введите число от 0.01 до {balance:.2f} (или /cancel для отмены):</b>',
            parse_mode="HTML"
        )

@dp.message(ChekState.waiting_for_activations)
async def process_chek_activations_input(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)
        return
    if not await force_subscription_check(message, state): return
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    try:
        activations = int(message.text.strip())
        if activations < 1:
            raise ValueError
        data = await state.get_data()
        amount = data["chek_amount"]
        total_cost = amount * activations
        if total_cost > balance:
            await message.answer(
                f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств! Общая сумма чека ({total_cost:.2f} $ = {amount} × {activations}) превышает ваш баланс ({balance:.2f} $). Введите меньшее количество активаций (или /cancel):</b>',
                parse_mode="HTML"
            )
            return
        user_balances[user_id] -= total_cost
        await update_balance(user_id, -total_cost)
        chek_id = generate_check_code()
        created_cheks[chek_id] = {
            "id": chek_id,
            "owner_id": user_id,
            "amount": amount,
            "activations": activations,
            "rem_activations": activations,
            "password": None,
            "only_premium": False,
            "activated_users": set(),
            "target_user": None,
        }
        await state.clear()
        bot_info = await message.bot.get_me()
        check_link = f"https://t.me/{bot_info.username}?start={chek_id}"
        if activations == 1:
            title_str = f"Чек на {amount:.2f}$"
        else:
            title_str = f"Многоразовый чек на {amount:.2f}$ ({activations} активаций)"
        text = (
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> {title_str} успешно создан и списан с баланса!</b>\n\n'
            f"Ссылка на чек: <code>{check_link}</code>"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_chek_manage_keyboard(chek_id))
    except ValueError:
        await message.answer(
            '<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Введите целое положительное число активаций (например: 5) или /cancel для отмены:</b>',
            parse_mode="HTML"
        )

@dp.callback_query(F.data.startswith("chek_copy_link:"))
async def chek_copy_link_handler(call: CallbackQuery) -> None:
    chek_id = call.data.split(":")[1]
    bot_info = await call.bot.get_me()
    check_link = f"https://t.me/{bot_info.username}?start={chek_id}"
    await call.answer(check_link, show_alert=False)

@dp.callback_query(F.data.startswith("chek_manage:"))
async def chek_manage_handler(call: CallbackQuery, state: FSMContext = None) -> None:
    if not await force_subscription_check(call, state): return
    if state:
        await state.clear()
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)
    if not chek:
        await call.answer("Чек не найден!", show_alert=True)
        return
    bot_info = await call.bot.get_me()
    check_link = f"https://t.me/{bot_info.username}?start={chek_id}"
    amount = chek["amount"]
    activations = chek["activations"]
    if activations == 1:
        title_str = f"Чек на {amount:.2f}$"
    else:
        title_str = f"Чек на {amount:.2f}$ ({activations} активаций)"
    target_info = f"\nЗакреплен за: {chek['target_user']}" if chek.get("target_user") else ""
    text = (
        f'<b><tg-emoji emoji-id="5451807640436903198">🎰</tg-emoji> Управление: {title_str}</b>\n\n'
        f"Ссылка на чек: <code>{check_link}</code>\n"
        f"Осталось активаций: {chek['rem_activations']}/{activations}{target_info}"
    )
    await safe_edit_message(call, text, get_chek_manage_keyboard(chek_id))

@dp.callback_query(F.data.startswith("chek_pin_user:"))
async def chek_pin_user_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    chek_id = call.data.split(":")[1]
    await state.update_data(target_chek_id=chek_id)
    await state.set_state(ChekState.waiting_for_target_user)
    text = (
        '<b><tg-emoji emoji-id="5197269100878907942">📌</tg-emoji> Введите @username или ID пользователя, '
        'за которым нужно закрепить чек:</b>\n\n'
        '<i>Для отмены введите /cancel</i>'
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data=f"chek_manage:{chek_id}")]])
    await safe_edit_message(call, text, kb)

@dp.message(ChekState.waiting_for_target_user)
async def chek_pin_user_process(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)
        return
    if not await force_subscription_check(message, state): return
    data = await state.get_data()
    chek_id = data.get("target_chek_id")
    chek = created_cheks.get(chek_id)
    if chek:
        target_val = message.text.strip()
        if not target_val.startswith("@") and not target_val.isdigit():
            target_val = f"@{target_val}"
        chek["target_user"] = target_val
        await state.clear()
        text = f'<b><tg-emoji emoji-id="5197269100878907942">📌</tg-emoji> Чек успешно закреплен за {target_val}!</b>'
        await message.answer(text, parse_mode="HTML", reply_markup=get_chek_manage_keyboard(chek_id))

@dp.callback_query(F.data.startswith("chek_unpin_user:"))
async def chek_unpin_user_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)
    if chek:
        chek["target_user"] = None
        await call.answer("Чек откреплен!", show_alert=True)
        await chek_manage_handler(call, state)

@dp.callback_query(F.data.startswith("chek_limits_menu:"))
async def chek_limits_menu_handler(call: CallbackQuery, state: FSMContext = None) -> None:
    if not await force_subscription_check(call, state): return
    if state:
        await state.clear()
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)
    if not chek:
        await call.answer("Чек не найден!", show_alert=True)
        return
    has_pass = chek["password"] if chek["password"] else "Не установлен"
    only_prem = "Да" if chek["only_premium"] else "Нет"
    target_info = chek["target_user"] if chek.get("target_user") else "Не закреплен"
    text = (
        f'<b><tg-emoji emoji-id="5451807640436903198">🎰</tg-emoji> Настройка ограничений чека <code>{chek_id}</code>:</b>\n\n'
        f"• Пароль: {has_pass}\n"
        f"• Только Telegram Premium: {only_prem}\n"
        f"• Закреплен за: {target_info}"
    )
    await safe_edit_message(call, text, get_chek_limits_keyboard(chek_id))

@dp.callback_query(F.data.startswith("chek_set_pass:"))
async def chek_set_pass_start(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    chek_id = call.data.split(":")[1]
    await state.update_data(target_chek_id=chek_id)
    await state.set_state(ChekState.waiting_for_password)
    text = (
        '<b><tg-emoji emoji-id="5188276641951948688">🃏</tg-emoji> Введите пароль для чека в чат:</b>\n\n'
        '<i>Для отмены введите /cancel</i>'
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data=f"chek_limits_menu:{chek_id}")]])
    await safe_edit_message(call, text, kb)

@dp.callback_query(F.data.startswith("chek_remove_pass:"))
async def chek_remove_pass_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)
    if chek:
        chek["password"] = None
        await call.answer("Пароль успешно удален!", show_alert=True)
        await chek_limits_menu_handler(call, state)

@dp.message(ChekState.waiting_for_password)
async def chek_set_pass_process(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)
        return
    if not await force_subscription_check(message, state): return
    data = await state.get_data()
    chek_id = data.get("target_chek_id")
    chek = created_cheks.get(chek_id)
    if chek:
        pwd = message.text.strip()
        chek["password"] = pwd
        await state.clear()
        text = f'<b><tg-emoji emoji-id="5463249656651747420">🎁</tg-emoji> Пароль «{pwd}» успешно установлен на чек!</b>'
        await message.answer(text, parse_mode="HTML", reply_markup=get_chek_limits_keyboard(chek_id))

@dp.callback_query(F.data.startswith("chek_toggle_premium:"))
async def chek_toggle_premium_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)
    if chek:
        chek["only_premium"] = not chek["only_premium"]
        await chek_limits_menu_handler(call, state)

@dp.callback_query(F.data.startswith("chek_delete:"))
async def chek_delete_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)
    if chek:
        rem_money = chek["amount"] * chek["rem_activations"]
        user_balances[chek["owner_id"]] = get_user_balance(chek["owner_id"]) + rem_money
        await update_balance(chek["owner_id"], rem_money)
        del created_cheks[chek_id]
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass

@dp.callback_query(F.data == "chek_active_list")
async def chek_active_list_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    user_id = call.from_user.id
    user_cheks = [c for c in created_cheks.values() if c["owner_id"] == user_id]
    if not user_cheks:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="open_cheks_menu")]])
        await safe_edit_message(call, '<b><tg-emoji emoji-id="5469638931605657197">🏦</tg-emoji> У вас нет активных чеков!</b>', kb)
        return
    keyboard = []
    for c in user_cheks:
        btn_text = f"Чек {c['amount']:.2f}$ ({c['rem_activations']}/{c['activations']})"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"chek_manage:{c['id']}")])
    keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="open_cheks_menu")])
    await safe_edit_message(call, '<b><tg-emoji emoji-id="5469638931605657197">🏦</tg-emoji> Ваши активные чеки:</b>', InlineKeyboardMarkup(inline_keyboard=keyboard))

# --- ИНЛАЙН ЧЕКОВ ---
@dp.inline_query()
async def inline_check_handler(query: InlineQuery) -> None:
    chek_id = query.query.strip()
    if chek_id.startswith("chek_"):
        pass
    elif chek_id.startswith("check_"):
        chek_id = "chek_" + chek_id[6:]
    chek = created_cheks.get(chek_id)
    if not chek or chek["rem_activations"] <= 0:
        await query.answer([], cache_time=1)
        return
    
    bot_info = await query.bot.get_me()
    amount_str = f"{chek['amount']:.2f}".rstrip("0").rstrip(".")
    if chek["amount"].is_integer():
        amount_str = str(int(chek["amount"]))
    acts = chek["activations"]
    target_str = f" для {chek['target_user']}" if chek.get("target_user") else ""
    
    if acts == 1:
        caption_text = f'<b><tg-emoji emoji-id="5452157517062770940">💸</tg-emoji> Чек на {amount_str}${target_str}</b>'
        desc_str = f"Чек на {amount_str}${target_str}"
    else:
        if 2 <= acts <= 4:
            act_str = f"{acts} активации"
        else:
            act_str = f"{acts} активаций"
        caption_text = f'<b><tg-emoji emoji-id="5452157517062770940">💸</tg-emoji> Чек на {amount_str}${target_str}\n👥 {act_str} ({chek["rem_activations"]} осталось)</b>'
        desc_str = f"На {act_str} ({chek['rem_activations']} доступно)"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Активировать ({chek['rem_activations']}/{acts})", url=f"https://t.me/{bot_info.username}?start={chek['id']}")]
        ]
    )
    item = InlineQueryResultArticle(
        id=chek_id,
        title=f"Отправить чек на {amount_str}$ ({acts} активаций)",
        description=desc_str,
        input_message_content=InputTextMessageContent(message_text=caption_text, parse_mode="HTML"),
        reply_markup=keyboard,
    )
    await query.answer([item], cache_time=1)

async def complete_chek_activation(message_or_call, user, chek: dict, state: FSMContext = None) -> None:
    user_id = user.id
    if chek.get("target_user"):
        target = str(chek["target_user"]).strip()
        user_uname = f"@{user.username}" if user.username else None
        user_id_str = str(user_id)
        is_matched = False
        if target.startswith("@") and user_uname and target.lower() == user_uname.lower():
            is_matched = True
        elif target == user_id_str or target == f"@{user_id_str}":
            is_matched = True
        
        if not is_matched:
            err_msg = '<tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Чек предназначен для другого игрока!'
            if isinstance(message_or_call, Message):
                await message_or_call.answer(f"<b>{err_msg}</b>", parse_mode="HTML")
            else:
                await message_or_call.answer("Чек предназначен для другого игрока!", show_alert=True)
            return
    
    chek["rem_activations"] -= 1
    if "activated_users" not in chek:
        chek["activated_users"] = set()
    chek["activated_users"].add(user_id)
    
    user_balances[user_id] = get_user_balance(user_id) + chek["amount"]
    await update_balance(user_id, chek["amount"])
    
    if chek["rem_activations"] <= 0:
        if chek["id"] in created_cheks:
            del created_cheks[chek["id"]]
    
    amount_str = f"{chek['amount']:.2f}".rstrip("0").rstrip(".")
    if chek["amount"].is_integer():
        amount_str = str(int(chek["amount"]))
    
    text = f'<b><tg-emoji emoji-id="5452157517062770940">💸</tg-emoji> Вы успешно активировали чек и получили {amount_str}$!</b>'
    if isinstance(message_or_call, Message):
        await message_or_call.answer(text, parse_mode="HTML")
    else:
        await message_or_call.message.answer(text, parse_mode="HTML")
    
    if state:
        await state.clear()
    
    user_name = html.quote(user.full_name)
    user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
    rem_info = f" (осталось активаций: {chek['rem_activations']})" if chek["rem_activations"] > 0 else " (чек полностью исчерпан)"
    owner_text = (
        f'<b><tg-emoji emoji-id="5307773751796996779">🎟</tg-emoji> {user_link} '
        f"активировал ваш чек на {amount_str}${rem_info}</b>"
    )
    try:
        await message_or_call.bot.send_message(chek["owner_id"], owner_text, parse_mode="HTML")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("activate_chek_btn:"))
async def activate_chek_btn_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)
    if not chek:
        await call.answer("Чек не найден или уже исчерпан!", show_alert=True)
        return
    user = call.from_user
    user_id = user.id
    if "activated_users" in chek and user_id in chek["activated_users"]:
        await call.answer("Вы уже активировали этот чек!", show_alert=True)
        return
    if chek["rem_activations"] <= 0:
        await call.answer("Этот чек уже полностью активирован!", show_alert=True)
        return
    if chek.get("only_premium") and not getattr(user, "is_premium", False):
        await call.answer("Этот чек доступен только для премиум-пользователей!", show_alert=True)
        return
    if chek.get("password"):
        await state.update_data(target_chek_id=chek_id)
        await state.set_state(ChekState.waiting_for_check_pass_input)
        text = '<b><tg-emoji emoji-id="5188276641951948688">🃏</tg-emoji> Введите пароль для использования чека:</b>'
        await call.message.answer(text, parse_mode="HTML")
        await call.answer()
        return
    await complete_chek_activation(call, user, chek, state)
    await call.answer()

@dp.message(ChekState.waiting_for_check_pass_input)
async def process_check_pass_input(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Действие отменено.</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)
        return
    if not await force_subscription_check(message, state): return
    data = await state.get_data()
    chek_id = data.get("target_chek_id")
    chek = created_cheks.get(chek_id)
    if not chek or chek["rem_activations"] <= 0:
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Чек недействителен или уже полностью активирован!</b>", parse_mode="HTML")
        await state.clear()
        return
    pwd = message.text.strip()
    if pwd != chek["password"]:
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Неверный пароль! Попробуйте еще раз или введите /cancel для отмены:</b>", parse_mode="HTML")
        return
    user = message.from_user
    if "activated_users" in chek and user.id in chek["activated_users"]:
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Вы уже активировали этот чек!</b>", parse_mode="HTML")
        await state.clear()
        return
    if chek.get("only_premium") and not getattr(user, "is_premium", False):
        await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Этот чек доступен только для премиум-пользователей!</b>", parse_mode="HTML")
        await state.clear()
        return
    await complete_chek_activation(message, user, chek, state)

# --- ИГРЫ ---
@dp.callback_query(F.data == "back_to_games")
async def back_to_games_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    text = '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру:</b>'
    await safe_edit_message(call, text, games_keyboard)

@dp.callback_query(F.data.startswith("back_to_games:"))
async def back_to_games_owner_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру:</b>'
    await safe_edit_message(call, text, games_keyboard)

# CUSTOM BET HANDLERS
@dp.callback_query(F.data.startswith("custom_bet_mines:"))
async def custom_bet_mines_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id): return
    await state.set_state(MinesState.waiting_for_custom_bet)
    await call.message.edit_text('<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите свою ставку:</b>', parse_mode="HTML")

@dp.message(MinesState.waiting_for_custom_bet)
async def process_custom_mines_bet(message: Message, state: FSMContext) -> None:
    if not await force_subscription_check(message, state): return
    try:
        bet = float(message.text.replace(",", ".").strip())
        if bet <= 0: raise ValueError
        st = get_game_settings(message.from_user.id)
        st["bet"] = bet
        await state.clear()
        await message.answer('<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины: Игровое поле</b>', parse_mode="HTML", reply_markup=get_preview_game_keyboard(message.from_user.id, message.from_user.id))
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма.</b>', parse_mode="HTML")

@dp.callback_query(F.data.startswith("custom_bet_tower:"))
async def custom_bet_tower_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id): return
    await state.set_state(TowerState.waiting_for_custom_bet)
    await call.message.edit_text('<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите свою ставку:</b>', parse_mode="HTML")

@dp.message(TowerState.waiting_for_custom_bet)
async def process_custom_tower_bet(message: Message, state: FSMContext) -> None:
    if not await force_subscription_check(message, state): return
    try:
        bet = float(message.text.replace(",", ".").strip())
        if bet <= 0: raise ValueError
        st = get_tower_settings(message.from_user.id)
        st["bet"] = bet
        await state.clear()
        await message.answer('<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня: Игровое поле</b>', parse_mode="HTML", reply_markup=get_preview_tower_keyboard(message.from_user.id, message.from_user.id))
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма.</b>', parse_mode="HTML")

@dp.callback_query(F.data.startswith("custom_bet_basketball:"))
async def custom_bet_basketball_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id): return
    await state.set_state(BasketballState.waiting_for_custom_bet)
    await call.message.edit_text('<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите свою ставку:</b>', parse_mode="HTML")

@dp.message(BasketballState.waiting_for_custom_bet)
async def process_custom_basketball_bet(message: Message, state: FSMContext) -> None:
    if not await force_subscription_check(message, state): return
    try:
        bet = float(message.text.replace(",", ".").strip())
        if bet <= 0: raise ValueError
        st = get_basketball_settings(message.from_user.id)
        st["bet"] = bet
        await state.clear()
        await message.answer(f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол | Ставка: {bet:.2f} $\n\nВыберите исход:</b>', parse_mode="HTML", reply_markup=get_basketball_type_keyboard(bet, message.from_user.id))
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма.</b>', parse_mode="HTML")

@dp.callback_query(F.data.startswith("custom_bet_football:"))
async def custom_bet_football_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id): return
    await state.set_state(FootballState.waiting_for_custom_bet)
    await call.message.edit_text('<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите свою ставку:</b>', parse_mode="HTML")

@dp.message(FootballState.waiting_for_custom_bet)
async def process_custom_football_bet(message: Message, state: FSMContext) -> None:
    if not await force_subscription_check(message, state): return
    try:
        bet = float(message.text.replace(",", ".").strip())
        if bet <= 0: raise ValueError
        st = get_football_settings(message.from_user.id)
        st["bet"] = bet
        await state.clear()
        await message.answer(f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол | Ставка: {bet:.2f} $\n\nВыберите исход:</b>', parse_mode="HTML", reply_markup=get_football_type_keyboard(bet, message.from_user.id))
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма.</b>', parse_mode="HTML")

@dp.callback_query(F.data.startswith("custom_bet_dice:"))
async def custom_bet_dice_handler(call: CallbackQuery, state: FSMContext) -> None:
    if not await force_subscription_check(call, state): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id): return
    await state.set_state(DiceState.waiting_for_custom_bet)
    await call.message.edit_text('<b><tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Введите свою ставку:</b>', parse_mode="HTML")

@dp.message(DiceState.waiting_for_custom_bet)
async def process_custom_dice_bet(message: Message, state: FSMContext) -> None:
    if not await force_subscription_check(message, state): return
    try:
        bet = float(message.text.replace(",", ".").strip())
        if bet <= 0: raise ValueError
        await state.clear()
        await message.answer(f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | Ставка: {bet:.2f} $\n\nВыберите режим:</b>', parse_mode="HTML", reply_markup=get_dice_type_keyboard(bet, message.from_user.id))
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма.</b>', parse_mode="HTML")

# --- МИНЫ ---
@dp.callback_query(F.data.startswith("mines_choose_bet"))
async def mines_choose_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины: Выберите размер ставки:</b>'
    await safe_edit_message(call, text, get_bet_selection_keyboard(owner_id))

@dp.callback_query(F.data.startswith("select_bet_"))
async def select_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("select_bet_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    st = get_game_settings(owner_id)
    st["bet"] = bet_val
    text = '<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины: Игровое поле</b>'
    await safe_edit_message(call, text, get_preview_game_keyboard(owner_id, owner_id))

@dp.callback_query(F.data.startswith("screen_game_confirm:"))
async def screen_game_confirm_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины: Игровое поле</b>'
    await safe_edit_message(call, text, get_preview_game_keyboard(owner_id, owner_id))

@dp.callback_query(F.data.startswith("screen_choose_mines:"))
async def screen_choose_mines_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Выберите количество мин:</b>'
    await safe_edit_message(call, text, get_mines_count_keyboard(owner_id))

@dp.callback_query(F.data.startswith("set_mines_cnt_"))
async def set_mines_cnt_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    cnt = int(parts[0].replace("set_mines_cnt_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    st = get_game_settings(owner_id)
    st["mines"] = cnt
    text = '<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины: Игровое поле</b>'
    await safe_edit_message(call, text, get_preview_game_keyboard(owner_id, owner_id))

@dp.callback_query(F.data.startswith("start_mines_game:"))
async def start_mines_game_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    user_id = call.from_user.id
    st = get_game_settings(user_id)
    bet = st["bet"]
    mines_count = st["mines"]
    balance = get_user_balance(user_id)
    if balance < bet:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
    
    user_balances[user_id] -= bet
    await update_balance(user_id, -bet)
    user_turnover[user_id] = get_user_turnover(user_id) + bet
    await update_global_stat('turnover_all', bet)
    await reduce_wager(user_id, bet)
    user_names[user_id] = call.from_user.full_name
    
    force_loss = False
    if user_id not in user_rigged_counters:
        user_rigged_counters[user_id] = {"wins": 0, "games": 0}
    user_rigged_counters[user_id]["games"] += 1
    if user_rigged_counters[user_id]["games"] >= 10:
        user_rigged_counters[user_id]["games"] = 0
        user_rigged_counters[user_id]["wins"] = 0
    
    if bet <= 0.15:
        if user_rigged_counters[user_id]["wins"] < 3:
            pass
        else:
            force_loss = True
    else:
        if random.random() < 0.90:
            force_loss = True
    
    mines_positions = set(random.sample(range(FIELD_SIZE), mines_count))
    game_id = str(user_id)
    active_games[game_id] = {
        "owner_id": user_id, "bet": bet, "mines_count": mines_count, "mines_positions": mines_positions,
        "opened": set(), "game_over": False, "current_win": 0.0, "game_id": game_id, "force_loss": force_loss
    }
    game_data = active_games[game_id]
    multiplier = calculate_multiplier(mines_count, 0)
    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины | Ставка: {bet:.2f} $ | Мин: {mines_count}</b>\n\n'
        f'<b>Множитель: x{multiplier:.2f} | Выигрыш: 0.00 $</b>'
    )
    await safe_edit_message(call, text, build_game_keyboard(game_data))

@dp.callback_query(F.data.startswith("open_cell_"))
async def open_cell_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    cell_idx = int(parts[0].replace("open_cell_", ""))
    game_id = parts[1]
    game_data = active_games.get(game_id)
    if not game_data:
        await call.answer("Игра не найдена или уже завершена!", show_alert=True)
        return
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    if game_data["game_over"] or cell_idx in game_data["opened"]:
        await call.answer()
        return
    
    is_mine = cell_idx in game_data["mines_positions"]
    if game_data.get("force_loss") and not is_mine:
        unopened_mines = [m for m in game_data["mines_positions"] if m not in game_data["opened"]]
        if unopened_mines:
            is_mine = True
            game_data["mines_positions"].add(cell_idx)
            swap_mine = random.choice(unopened_mines)
            game_data["mines_positions"].remove(swap_mine)
    
    if is_mine:
        game_data["game_over"] = True
        bet = game_data["bet"]
        await log_bet_to_channel(call.bot, call.from_user, "Мины", bet, "Проигрыш 💥")
        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины | Ставка: {bet:.2f} $ | Мин: {game_data["mines_count"]}</b>\n\n'
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Вы проиграли {bet:.2f} $!</b>'
        )
        await safe_edit_message(call, text, build_game_keyboard(game_data, finished=True))
        del active_games[game_id]
        return
    
    game_data["opened"].add(cell_idx)
    opened_count = len(game_data["opened"])
    multiplier = calculate_multiplier(game_data["mines_count"], opened_count)
    current_win = game_data["bet"] * multiplier
    game_data["current_win"] = current_win
    
    if game_data.get("force_loss") is False and game_data["bet"] <= 0.15:
        user_rigged_counters[game_data["owner_id"]]["wins"] += 1
    
    if opened_count == (FIELD_SIZE - game_data["mines_count"]):
        game_data["game_over"] = True
        user_id = game_data["owner_id"]
        user_balances[user_id] = get_user_balance(user_id) + current_win
        await update_balance(user_id, current_win)
        await log_bet_to_channel(call.bot, call.from_user, "Мины", game_data["bet"], f"Победа x{multiplier:.2f} 🏆", current_win)
        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины | Ставка: {game_data["bet"]:.2f} $ | Мин: {game_data["mines_count"]}</b>\n\n'
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Поздравляем! Вы выиграли {current_win:.2f} $ (x{multiplier:.2f})!</b>'
        )
        await safe_edit_message(call, text, build_game_keyboard(game_data, finished=True))
        del active_games[game_id]
        return
    
    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины | Ставка: {game_data["bet"]:.2f} $ | Мин: {game_data["mines_count"]}</b>\n\n'
        f'<b>Множитель: x{multiplier:.2f} | Выигрыш: {current_win:.2f} $</b>'
    )
    await safe_edit_message(call, text, build_game_keyboard(game_data))

@dp.callback_query(F.data.startswith("cashout_mines:"))
async def cashout_mines_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    game_id = call.data.split(":")[1]
    game_data = active_games.get(game_id)
    if not game_data or game_data["game_over"]:
        await call.answer("Игра не найдена или уже завершена!", show_alert=True)
        return
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    game_data["game_over"] = True
    user_id = game_data["owner_id"]
    win_amount = game_data["current_win"]
    user_balances[user_id] = get_user_balance(user_id) + win_amount
    await update_balance(user_id, win_amount)
    multiplier = calculate_multiplier(game_data["mines_count"], len(game_data["opened"]))
    await log_bet_to_channel(call.bot, call.from_user, "Мины", game_data["bet"], f"Кэшаут x{multiplier:.2f} 💰", win_amount)
    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины | Ставка: {game_data["bet"]:.2f} $ | Мин: {game_data["mines_count"]}</b>\n\n'
        f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы успешно забрали {win_amount:.2f} $ (x{multiplier:.2f})!</b>'
    )
    await safe_edit_message(call, text, build_game_keyboard(game_data, finished=True))
    del active_games[game_id]

# --- БАШНЯ ---
@dp.callback_query(F.data.startswith("tower_choose_bet"))
async def tower_choose_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня: Выберите размер ставки:</b>'
    await safe_edit_message(call, text, get_tower_bet_selection_keyboard(owner_id))

@dp.callback_query(F.data.startswith("select_tower_bet_"))
async def select_tower_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("select_tower_bet_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    st = get_tower_settings(owner_id)
    st["bet"] = bet_val
    text = '<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня: Игровое поле</b>'
    await safe_edit_message(call, text, get_preview_tower_keyboard(owner_id, owner_id))

@dp.callback_query(F.data.startswith("screen_tower_game_confirm:"))
async def screen_tower_game_confirm_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня: Игровое поле</b>'
    await safe_edit_message(call, text, get_preview_tower_keyboard(owner_id, owner_id))

@dp.callback_query(F.data.startswith("screen_choose_tower_traps:"))
async def screen_choose_tower_traps_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Выберите количество ловушек на ряду:</b>'
    await safe_edit_message(call, text, get_tower_traps_count_keyboard(owner_id))

@dp.callback_query(F.data.startswith("set_tower_traps_cnt_"))
async def set_tower_traps_cnt_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    cnt = int(parts[0].replace("set_tower_traps_cnt_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    st = get_tower_settings(owner_id)
    st["traps"] = cnt
    text = '<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня: Игровое поле</b>'
    await safe_edit_message(call, text, get_preview_tower_keyboard(owner_id, owner_id))

@dp.callback_query(F.data.startswith("start_tower_game:"))
async def start_tower_game_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    owner_id = int(call.data.split(":")[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    user_id = call.from_user.id
    st = get_tower_settings(user_id)
    bet = st["bet"]
    traps_count = st["traps"]
    balance = get_user_balance(user_id)
    if balance < bet:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
    
    user_balances[user_id] -= bet
    await update_balance(user_id, -bet)
    user_turnover[user_id] = get_user_turnover(user_id) + bet
    await update_global_stat('turnover_all', bet)
    await reduce_wager(user_id, bet)
    user_names[user_id] = call.from_user.full_name
    
    force_loss_floor = -1
    allow_wins = 0
    if user_id not in user_rigged_counters:
        user_rigged_counters[user_id] = {"wins": 0, "games": 0}
    user_rigged_counters[user_id]["games"] += 1
    if user_rigged_counters[user_id]["games"] >= 10:
        user_rigged_counters[user_id]["games"] = 0
        user_rigged_counters[user_id]["wins"] = 0
    
    if bet <= 0.15:
        if user_rigged_counters[user_id]["wins"] < 3:
            allow_wins = random.randint(2, 3)
        else:
            force_loss_floor = 0
    else:
        if random.random() < 0.90:
            force_loss_floor = random.randint(0, 2)
    
    trap_positions = {}
    for f_idx in range(TOWER_FLOORS):
        trap_positions[f_idx] = set(random.sample(range(5), traps_count))
    
    game_id = str(user_id)
    active_tower_games[game_id] = {
        "owner_id": user_id, "bet": bet, "traps_count": traps_count, "trap_positions": trap_positions,
        "current_floor": 0, "history": {}, "game_over": False, "current_win": 0.0, "game_id": game_id,
        "force_loss_floor": force_loss_floor, "allow_wins": allow_wins
    }
    game_data = active_tower_games[game_id]
    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня | Ставка: {bet:.2f} $ | Ловушек: {traps_count}</b>\n\n'
        f'<b>Этаж: 1 / {TOWER_FLOORS} | Выигрыш: 0.00 $</b>'
    )
    await safe_edit_message(call, text, build_tower_game_keyboard(game_data))

@dp.callback_query(F.data.startswith("open_tower_"))
async def open_tower_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    coords = parts[0].replace("open_tower_", "").split("_")
    floor_idx = int(coords[0])
    col_idx = int(coords[1])
    game_id = parts[1]
    game_data = active_tower_games.get(game_id)
    if not game_data:
        await call.answer("Игра не найдена или уже завершена!", show_alert=True)
        return
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    if game_data["game_over"] or floor_idx != game_data["current_floor"]:
        await call.answer()
        return
    
    traps = game_data["trap_positions"][floor_idx]
    is_trap = col_idx in traps
    
    if game_data["force_loss_floor"] != -1 and floor_idx >= game_data["force_loss_floor"]:
        if not is_trap:
            is_trap = True
            game_data["trap_positions"][floor_idx].add(col_idx)
            safe_cols = [c for c in range(5) if c not in game_data["trap_positions"][floor_idx]]
            if safe_cols:
                remove_safe = random.choice(safe_cols)
                game_data["trap_positions"][floor_idx].discard(remove_safe)
    elif game_data["allow_wins"] > 0 and floor_idx < game_data["allow_wins"]:
        if is_trap:
            is_trap = False
            game_data["trap_positions"][floor_idx].discard(col_idx)
            safe_cols = [c for c in range(5) if c not in game_data["trap_positions"][floor_idx] and c != col_idx]
            if safe_cols:
                add_trap = random.choice(safe_cols)
                game_data["trap_positions"][floor_idx].add(add_trap)
    
    if is_trap:
        game_data["game_over"] = True
        game_data["history"][floor_idx] = (col_idx, False)
        bet = game_data["bet"]
        await log_bet_to_channel(call.bot, call.from_user, "Башня", bet, f"Проигрыш на {floor_idx+1} этаже 💥")
        text = (
            f'<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня | Ставка: {bet:.2f} $ | Ловушек: {game_data["traps_count"]}</b>\n\n'
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Вы попали на ловушку на {floor_idx+1} этаже и проиграли {bet:.2f} $!</b>'
        )
        await safe_edit_message(call, text, build_tower_game_keyboard(game_data, finished=True))
        del active_tower_games[game_id]
        return
    
    game_data["history"][floor_idx] = (col_idx, True)
    multiplier = calculate_tower_multiplier(game_data["traps_count"], floor_idx + 1)
    current_win = game_data["bet"] * multiplier
    game_data["current_win"] = current_win
    
    if floor_idx == TOWER_FLOORS - 1:
        game_data["game_over"] = True
        user_id = game_data["owner_id"]
        user_balances[user_id] = get_user_balance(user_id) + current_win
        await update_balance(user_id, current_win)
        await log_bet_to_channel(call.bot, call.from_user, "Башня", game_data["bet"], f"Победа на вершине x{multiplier:.2f} 🏆", current_win)
        text = (
            f'<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня | Ставка: {game_data["bet"]:.2f} $ | Ловушек: {game_data["traps_count"]}</b>\n\n'
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Поздравляем! Вы покорили вершину Башни и выиграли {current_win:.2f} $ (x{multiplier:.2f})!</b>'
        )
        await safe_edit_message(call, text, build_tower_game_keyboard(game_data, finished=True))
        del active_tower_games[game_id]
        return
    
    game_data["current_floor"] += 1
    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня | Ставка: {game_data["bet"]:.2f} $ | Ловушек: {game_data["traps_count"]}</b>\n\n'
        f'<b>Этаж: {game_data["current_floor"]+1} / {TOWER_FLOORS} | Выигрыш: {current_win:.2f} $ (x{multiplier:.2f})</b>'
    )
    await safe_edit_message(call, text, build_tower_game_keyboard(game_data))

@dp.callback_query(F.data.startswith("cashout_tower:"))
async def cashout_tower_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    game_id = call.data.split(":")[1]
    game_data = active_tower_games.get(game_id)
    if not game_data or game_data["game_over"]:
        await call.answer("Игра не найдена или уже завершена!", show_alert=True)
        return
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    game_data["game_over"] = True
    user_id = game_data["owner_id"]
    win_amount = game_data["current_win"]
    user_balances[user_id] = get_user_balance(user_id) + win_amount
    await update_balance(user_id, win_amount)
    multiplier = calculate_tower_multiplier(game_data["traps_count"], game_data["current_floor"])
    await log_bet_to_channel(call.bot, call.from_user, "Башня", game_data["bet"], f"Кэшаут x{multiplier:.2f} 💰", win_amount)
    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня | Ставка: {game_data["bet"]:.2f} $ | Ловушек: {game_data["traps_count"]}</b>\n\n'
        f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы успешно забрали {win_amount:.2f} $ (x{multiplier:.2f}) на {game_data["current_floor"]} этаже!</b>'
    )
    await safe_edit_message(call, text, build_tower_game_keyboard(game_data, finished=True))
    del active_tower_games[game_id]

# --- БАСКЕТБОЛ ---
@dp.callback_query(F.data.startswith("basketball_choose_bet"))
async def basketball_choose_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол: Выберите размер ставки:</b>'
    await safe_edit_message(call, text, get_basketball_bet_selection_keyboard(owner_id))

@dp.callback_query(F.data.startswith("select_basketball_bet_"))
async def select_basketball_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("select_basketball_bet_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    st = get_basketball_settings(owner_id)
    st["bet"] = bet_val
    text = f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол | Ставка: {bet_val:.2f} $\n\nВыберите исход:</b>'
    await safe_edit_message(call, text, get_basketball_type_keyboard(bet_val, owner_id))

@dp.callback_query(F.data.startswith("basketball_bet_"))
async def basketball_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    data_part = parts[0].replace("basketball_bet_", "")
    sub_parts = data_part.rsplit("_", 1)
    bet_type = sub_parts[0]
    bet_val = float(sub_parts[1])
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    if balance < bet_val:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
    
    user_balances[user_id] -= bet_val
    await update_balance(user_id, -bet_val)
    user_turnover[user_id] = get_user_turnover(user_id) + bet_val
    await update_global_stat('turnover_all', bet_val)
    await reduce_wager(user_id, bet_val)
    user_names[user_id] = call.from_user.full_name
    
    await safe_edit_message(call, f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол | Ставка: {bet_val:.2f} $\n\nБросаем мяч... <tg-emoji emoji-id="5451845260055450038">⏳</tg-emoji></b>', InlineKeyboardMarkup(inline_keyboard=[]))
    msg = await call.message.answer_dice(emoji="🏀")
    await asyncio.sleep(4)
    dice_value = msg.dice.value
    res = calculate_basketball_result(dice_value, bet_type)
    bet_type_name = get_basketball_bet_type_name(bet_type)
    
    if res['win']:
        win_amount = bet_val * res['multiplier']
        user_balances[user_id] = get_user_balance(user_id) + win_amount
        await update_balance(user_id, win_amount)
        await log_bet_to_channel(call.bot, call.from_user, "Баскетбол", bet_val, f"Победа ({bet_type_name}) x{res['multiplier']} 🏆", win_amount)
        text = (
            f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол | Ставка: {bet_val:.2f} $ | Исход: {bet_type_name}</b>\n\n'
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Поздравляем! Вы выиграли {win_amount:.2f} $ (x{res["multiplier"]})!</b>'
        )
    else:
        await log_bet_to_channel(call.bot, call.from_user, "Баскетбол", bet_val, f"Проигрыш ({bet_type_name}) ❌")
        text = (
            f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол | Ставка: {bet_val:.2f} $ | Исход: {bet_type_name}</b>\n\n'
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> К сожалению, вы проиграли {bet_val:.2f} $!</b>'
        )
    await call.message.answer(text=text, parse_mode="HTML", reply_markup=get_basketball_result_keyboard(bet_val, owner_id))

@dp.callback_query(F.data.startswith("basketball_repeat_"))
async def basketball_repeat_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    sub_parts = parts[0].replace("basketball_repeat_", "").rsplit("_", 1)
    bet_val = float(sub_parts[0]) if len(sub_parts) > 0 else 0.1
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол | Ставка: {bet_val:.2f} $\n\nВыберите исход:</b>'
    await safe_edit_message(call, text, get_basketball_type_keyboard(bet_val, owner_id))

# --- ФУТБОЛ ---
@dp.callback_query(F.data.startswith("football_choose_bet"))
async def football_choose_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = '<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол: Выберите размер ставки:</b>'
    await safe_edit_message(call, text, get_football_bet_selection_keyboard(owner_id))

@dp.callback_query(F.data.startswith("select_football_bet_"))
async def select_football_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("select_football_bet_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    st = get_football_settings(owner_id)
    st["bet"] = bet_val
    text = f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол | Ставка: {bet_val:.2f} $\n\nВыберите исход:</b>'
    await safe_edit_message(call, text, get_football_type_keyboard(bet_val, owner_id))

@dp.callback_query(F.data.startswith("football_bet_"))
async def football_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    data_part = parts[0].replace("football_bet_", "")
    sub_parts = data_part.rsplit("_", 1)
    bet_type = sub_parts[0]
    bet_val = float(sub_parts[1])
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    if balance < bet_val:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
    
    user_balances[user_id] -= bet_val
    await update_balance(user_id, -bet_val)
    user_turnover[user_id] = get_user_turnover(user_id) + bet_val
    await update_global_stat('turnover_all', bet_val)
    await reduce_wager(user_id, bet_val)
    user_names[user_id] = call.from_user.full_name
    
    await safe_edit_message(call, f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол | Ставка: {bet_val:.2f} $\n\nБьем по мячу... <tg-emoji emoji-id="5451845260055450038">⏳</tg-emoji></b>', InlineKeyboardMarkup(inline_keyboard=[]))
    msg = await call.message.answer_dice(emoji="⚽")
    await asyncio.sleep(4)
    dice_value = msg.dice.value
    res = calculate_football_result(dice_value, bet_type)
    bet_type_name = get_football_bet_type_name(bet_type)
    
    if res['win']:
        win_amount = bet_val * res['multiplier']
        user_balances[user_id] = get_user_balance(user_id) + win_amount
        await update_balance(user_id, win_amount)
        await log_bet_to_channel(call.bot, call.from_user, "Футбол", bet_val, f"Победа ({bet_type_name}) x{res['multiplier']} 🏆", win_amount)
        text = (
            f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол | Ставка: {bet_val:.2f} $ | Исход: {bet_type_name}</b>\n\n'
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Поздравляем! Вы выиграли {win_amount:.2f} $ (x{res["multiplier"]})!</b>'
        )
    else:
        await log_bet_to_channel(call.bot, call.from_user, "Футбол", bet_val, f"Проигрыш ({bet_type_name}) ❌")
        text = (
            f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол | Ставка: {bet_val:.2f} $ | Исход: {bet_type_name}</b>\n\n'
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> К сожалению, вы проиграли {bet_val:.2f} $!</b>'
        )
    await call.message.answer(text=text, parse_mode="HTML", reply_markup=get_football_result_keyboard(bet_val, owner_id))

@dp.callback_query(F.data.startswith("football_repeat_"))
async def football_repeat_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    sub_parts = parts[0].replace("football_repeat_", "").rsplit("_", 1)
    bet_val = float(sub_parts[0]) if len(sub_parts) > 0 else 0.1
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол | Ставка: {bet_val:.2f} $\n\nВыберите исход:</b>'
    await safe_edit_message(call, text, get_football_type_keyboard(bet_val, owner_id))

# --- КУБ ---
@dp.callback_query(F.data.startswith("dice_choose_bet"))
async def dice_choose_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб: Выберите размер ставки:</b>'
    await safe_edit_message(call, text, get_dice_bet_selection_keyboard(owner_id))

@dp.callback_query(F.data.startswith("select_dice_bet_"))
async def select_dice_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("select_dice_bet_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    text = f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | Ставка: {bet_val:.2f} $\n\nВыберите режим:</b>'
    await safe_edit_message(call, text, get_dice_type_keyboard(bet_val, owner_id))

@dp.callback_query(F.data.startswith("dice_type_menu_"))
async def dice_type_menu_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("dice_type_menu_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id): return
    text = f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | Ставка: {bet_val:.2f} $\n\nВыберите режим:</b>'
    await safe_edit_message(call, text, get_dice_type_keyboard(bet_val, owner_id))

@dp.callback_query(F.data.startswith("dice_2_menu_"))
async def dice_2_menu_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("dice_2_menu_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id): return
    text = f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> 2 Куба | Ставка: {bet_val:.2f} $\n\nВыберите режим:</b>'
    await safe_edit_message(call, text, get_dice_2_menu_keyboard(bet_val, owner_id))

async def process_dice_game(call: CallbackQuery, bet_type: str, bet_val: float, owner_id: int, is_2_dice: bool = False):
    if not check_owner(call, owner_id):
        await call.answer("Это чужая игра!", show_alert=True)
        return
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    if balance < bet_val:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return
    
    user_balances[user_id] -= bet_val
    await update_balance(user_id, -bet_val)
    user_turnover[user_id] = get_user_turnover(user_id) + bet_val
    await update_global_stat('turnover_all', bet_val)
    await reduce_wager(user_id, bet_val)
    user_names[user_id] = call.from_user.full_name
    
    dice_emoji = "🎲"
    await safe_edit_message(call, f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | Ставка: {bet_val:.2f} $\n\nБросаем кубики... <tg-emoji emoji-id="5451845260055450038">⏳</tg-emoji></b>', InlineKeyboardMarkup(inline_keyboard=[]))
    
    if is_2_dice:
        msg1 = await call.message.answer_dice(emoji=dice_emoji)
        msg2 = await call.message.answer_dice(emoji=dice_emoji)
        await asyncio.sleep(4)
        val1 = msg1.dice.value
        val2 = msg2.dice.value
        total = val1 + val2
        coeff = DICE_COEFF_2
        if bet_type == 'seven':
            coeff = DICE_COEFF_SEVEN
        res = {'win': False, 'multiplier': coeff}
        if bet_type == 'even': res['win'] = (total % 2 == 0)
        elif bet_type == 'odd': res['win'] = (total % 2 != 0)
        elif bet_type == 'more': res['win'] = (total > 7)
        elif bet_type == 'less': res['win'] = (total < 7)
        elif bet_type == 'seven': res['win'] = (total == 7)
        type_names = {'even':'Чет', 'odd':'Нечет', 'more':'Больше 7', 'less':'Меньше 7', 'seven': 'Ровно 7'}
        t_name = type_names.get(bet_type, bet_type)
        outcome_text = f"Сумма: {total} ({t_name})"
    else:
        msg = await call.message.answer_dice(emoji=dice_emoji)
        await asyncio.sleep(4)
        val = msg.dice.value
        res = {'win': False, 'multiplier': DICE_COEFF_1}
        if bet_type == 'even': res['win'] = (val % 2 == 0)
        elif bet_type == 'odd': res['win'] = (val % 2 != 0)
        elif bet_type == 'more': res['win'] = (val > 3)
        elif bet_type == 'less': res['win'] = (val < 4)
        type_names = {'even':'Чет', 'odd':'Нечет', 'more':'Больше', 'less':'Меньше'}
        t_name = type_names.get(bet_type, bet_type)
        outcome_text = f"Значение: {val} ({t_name})"
    
    if res['win']:
        win_amount = bet_val * res['multiplier']
        user_balances[user_id] = get_user_balance(user_id) + win_amount
        await update_balance(user_id, win_amount)
        await log_bet_to_channel(call.bot, call.from_user, "Куб", bet_val, f"Победа ({t_name}) x{res['multiplier']} 🏆", win_amount)
        text = (
            f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | Ставка: {bet_val:.2f} $ | {outcome_text}</b>\n\n'
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Поздравляем! Вы выиграли {win_amount:.2f} $ (x{res["multiplier"]})!</b>'
        )
    else:
        await log_bet_to_channel(call.bot, call.from_user, "Куб", bet_val, f"Проигрыш ({t_name}) ❌")
        text = (
            f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | Ставка: {bet_val:.2f} $ | {outcome_text}</b>\n\n'
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> К сожалению, вы проиграли {bet_val:.2f} $!</b>'
        )
    await call.message.answer(text=text, parse_mode="HTML", reply_markup=get_dice_result_keyboard(bet_val, owner_id))

@dp.callback_query(F.data.startswith("dice_bet_"))
async def dice_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    data_part = parts[0].replace("dice_bet_", "")
    sub_parts = data_part.rsplit("_", 1)
    bet_type = sub_parts[0]
    bet_val = float(sub_parts[1])
    owner_id = int(parts[1])
    await process_dice_game(call, bet_type, bet_val, owner_id, False)

@dp.callback_query(F.data.startswith("dice2_bet_"))
async def dice2_bet_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    data_part = parts[0].replace("dice2_bet_", "")
    sub_parts = data_part.rsplit("_", 1)
    bet_type = sub_parts[0]
    bet_val = float(sub_parts[1])
    owner_id = int(parts[1])
    await process_dice_game(call, bet_type, bet_val, owner_id, True)

@dp.callback_query(F.data.startswith("dice_repeat_"))
async def dice_repeat_handler(call: CallbackQuery) -> None:
    if not await force_subscription_check(call): return
    parts = call.data.split(":")
    bet_val = float(parts[0].replace("dice_repeat_", ""))
    owner_id = int(parts[1])
    if not check_owner(call, owner_id): return
    text = f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | Ставка: {bet_val:.2f} $\n\nВыберите режим:</b>'
    await safe_edit_message(call, text, get_dice_type_keyboard(bet_val, owner_id))

# --- ОБЩИЕ КОМАНДЫ ---
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return
    await state.clear()
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        payload = args[1].strip()
        if payload == "deposit":
            if not await force_subscription_check(message, state): return
            if await check_subscription(message.bot, message.from_user.id):
                text = '<b><tg-emoji emoji-id="5449789954995559460">💎</tg-emoji> Выберите способ пополнения:</b>'
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="XRocket", icon_custom_emoji_id="5451692831666112994", callback_data="deposit_method_xrocket")],
                    [InlineKeyboardButton(text="CryptoBot", icon_custom_emoji_id="5452124248246096392", callback_data="deposit_method_cryptobot")],
                    [InlineKeyboardButton(text="◀ Назад", callback_data="open_wallet_inline")]
                ])
                await message.answer(text, parse_mode="HTML", reply_markup=kb)
                return
        elif payload == "withdraw":
            if await check_subscription(message.bot, message.from_user.id):
                text = (
                    '<b><tg-emoji emoji-id="5255868234506213301">📤</tg-emoji> Вывод средств</b>\n\n'
                    '<b>Введите сумму для вывода в USDT (минимум 1.5 $):</b>\n\n'
                    '<i><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Для отмены введите /cancel</i>'
                )
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="open_wallet_inline")]])
                await state.set_state(WithdrawState.waiting_for_amount)
                await message.answer(text, parse_mode="HTML", reply_markup=kb)
                return
        
        if payload.startswith("chek_") or payload.startswith("check_"):
            chek_id = payload if payload.startswith("chek_") else "chek_" + payload[6:]
            chek = created_cheks.get(chek_id)
            if not chek or chek["rem_activations"] <= 0:
                await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Этот чек недействителен или уже полностью активирован!</b>", parse_mode="HTML")
                return
            user = message.from_user
            is_subbed = await check_subscription(message.bot, user.id)
            if not is_subbed:
                kb = await get_subscription_keyboard(message.bot)
                await message.answer(
                    f'<b><tg-emoji emoji-id="5312140414982071786">⚠️</tg-emoji> Чтобы активировать чек, вы должны быть подписаны на все каналы!</b>',
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                return
            if "activated_users" in chek and user.id in chek["activated_users"]:
                await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Вы уже активировали этот чек!</b>", parse_mode="HTML")
                return
            if chek.get("only_premium") and not getattr(user, "is_premium", False):
                await message.answer("<b><tg-emoji emoji-id=\"5312140414982071786\">❌</tg-emoji> Этот чек доступен только для премиум-пользователей!</b>", parse_mode="HTML")
                return
            if chek.get("password"):
                await state.update_data(target_chek_id=chek_id)
                await state.set_state(ChekState.waiting_for_check_pass_input)
                await message.answer("<b><tg-emoji emoji-id=\"5188276641951948688\">🃏</tg-emoji> Введите пароль для использования чека:</b>", parse_mode="HTML")
                return
            await complete_chek_activation(message, user, chek, state)
            return
    
    user_id = message.from_user.id
    user_names[user_id] = message.from_user.full_name
    is_subbed = await check_subscription(message.bot, user_id)
    if not is_subbed:
        kb = await get_subscription_keyboard(message.bot)
        await message.answer(
            f'<b><tg-emoji emoji-id="5312140414982071786">⚠️</tg-emoji> Для использования бота вы должны быть подписаны на все каналы!</b>',
            parse_mode="HTML",
            reply_markup=kb,
        )
        return
    text = (
        '<b><tg-emoji emoji-id="5451807640436903198">👋</tg-emoji> Добро пожаловать в DuckBet!\n\n'
        'Выберите раздел в меню ниже:</b>'
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)
    await message.answer("Главное меню:", reply_markup=menu_inline_keyboard)

# --- ГРУППОВЫЕ КОМАНДЫ ---
def parse_bet_arg(arg: str, user_id: int) -> float:
    arg = arg.lower().strip().replace(",", ".")
    if arg in ["вб", "all", "все", "вабанк"]:
        return get_user_balance(user_id)
    arg = arg.replace("$", "")
    try:
        return float(arg)
    except:
        return -1

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().in_(["б", "баланс", "балик", "кошелек"]))
async def group_balance_handler(message: Message) -> None:
    user_id = message.from_user.id
    user_names[user_id] = message.from_user.full_name
    balance = get_user_balance(user_id)
    turnover = get_user_turnover(user_id)
    text = (
        f'<tg-emoji emoji-id="5449624985301717991">💳</tg-emoji> <b>Ваш ID: {user_id}</b>\n'
        f'<tg-emoji emoji-id="5452031425412895584">🚀</tg-emoji> <b>Имя: {html.quote(message.from_user.full_name)}</b>\n\n'
        f'<tg-emoji emoji-id="5452042536493288421">📊</tg-emoji> <b>Оборот: {turnover:.2f} $</b>\n'
        f'<tg-emoji emoji-id="5451845260055450038">💰</tg-emoji> <b>Баланс: {balance:.2f} $</b>'
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Пополнить", icon_custom_emoji_id="5255805270285653933", url=f"https://t.me/{(await message.bot.get_me()).username}?start=deposit"),
                InlineKeyboardButton(text="Вывести", icon_custom_emoji_id="5255868234506213301", url=f"https://t.me/{(await message.bot.get_me()).username}?start=withdraw")
            ]
        ]
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb, reply_to_message_id=message.message_id)

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().in_(["пополнить", "деп", "депозит"]))
async def group_deposit_handler(message: Message) -> None:
    bot_info = await message.bot.get_me()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Открыть меню пополнения", url=f"https://t.me/{bot_info.username}?start=deposit")]])
    await message.answer("<b>Нажмите кнопку ниже, чтобы открыть меню пополнения:</b>", parse_mode="HTML", reply_markup=kb, reply_to_message_id=message.message_id)

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().in_(["вывод", "вывести", "кэшаут"]))
async def group_withdraw_handler(message: Message) -> None:
    bot_info = await message.bot.get_me()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📤 Открыть меню вывода", url=f"https://t.me/{bot_info.username}?start=withdraw")]])
    await message.answer("<b>Нажмите кнопку ниже, чтобы открыть меню вывода:</b>", parse_mode="HTML", reply_markup=kb, reply_to_message_id=message.message_id)

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().in_(["топ", "лидеры", "топчик"]))
async def group_top_handler(message: Message) -> None:
    user_id = message.from_user.id
    if user_id not in top_modes: top_modes[user_id] = "turnover"
    text = generate_top_text(user_id)
    await message.answer(text, parse_mode="HTML", reply_markup=get_top_keyboard(top_modes[user_id]), reply_to_message_id=message.message_id)

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().in_(["играть", "игры", "меню"]))
async def group_menu_handler(message: Message) -> None:
    await message.answer("<b>Выберите игру:</b>", parse_mode="HTML", reply_markup=games_keyboard, reply_to_message_id=message.message_id)

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().startswith(("мины", "mines")))
async def group_mines_handler(message: Message) -> None:
    if not await force_subscription_check(message): return
    try:
        parts = message.text.split()
        mines = 3
        bet = 0.1
        if len(parts) >= 3:
            mines = int(parts[1])
            bet = parse_bet_arg(parts[2], message.from_user.id)
        elif len(parts) == 2:
            val = parts[1]
            try:
                b = parse_bet_arg(val, message.from_user.id)
                if b > 0: bet = b
            except:
                mines = int(val)
        if mines < 2: mines = 2
        if mines > 24: mines = 24
        if bet <= 0: raise ValueError("Bad bet")
        user_id = message.from_user.id
        balance = get_user_balance(user_id)
        if balance < bet:
            await message.reply(f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств! Баланс: {balance:.2f}$</b>', parse_mode="HTML")
            return
        
        st = get_game_settings(user_id)
        st["bet"] = bet
        st["mines"] = mines
        
        user_balances[user_id] -= bet
        await update_balance(user_id, -bet)
        user_turnover[user_id] = get_user_turnover(user_id) + bet
        await update_global_stat('turnover_all', bet)
        await reduce_wager(user_id, bet)
        user_names[user_id] = message.from_user.full_name
        
        force_loss = False
        if user_id not in user_rigged_counters: user_rigged_counters[user_id] = {"wins": 0, "games": 0}
        user_rigged_counters[user_id]["games"] += 1
        if user_rigged_counters[user_id]["games"] >= 10:
            user_rigged_counters[user_id]["games"] = 0
            user_rigged_counters[user_id]["wins"] = 0
        
        if bet <= 0.15:
            if user_rigged_counters[user_id]["wins"] >= 3: force_loss = True
        else:
            if random.random() < 0.90: force_loss = True
        
        mines_positions = set(random.sample(range(FIELD_SIZE), mines))
        game_id = str(user_id)
        active_games[game_id] = {
            "owner_id": user_id, "bet": bet, "mines_count": mines, "mines_positions": mines_positions,
            "opened": set(), "game_over": False, "current_win": 0.0, "game_id": game_id, "force_loss": force_loss
        }
        game_data = active_games[game_id]
        multiplier = calculate_multiplier(mines, 0)
        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины | Ставка: {bet:.2f} $ | Мин: {mines}</b>\n\n'
            f'<b>Множитель: x{multiplier:.2f} | Выигрыш: 0.00 $</b>'
        )
        await message.answer(text, parse_mode="HTML", reply_markup=build_game_keyboard(game_data), reply_to_message_id=message.message_id)
    except Exception:
        await message.reply('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Формат: мины [кол-во мин] [ставка]</b>', parse_mode="HTML")

# Исправлено: Триггер только на "башня" или строго "т"/"Т"
@dp.message(
    F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]),
    (F.text.lower().startswith("башня")) | (F.text.lower() == "т")
)
async def group_tower_handler(message: Message) -> None:
    if not await force_subscription_check(message): return
    try:
        parts = message.text.split()
        traps = 1
        bet = 0.1
        if len(parts) >= 3:
            traps = int(parts[1])
            bet = parse_bet_arg(parts[2], message.from_user.id)
        elif len(parts) == 2:
            val = parts[1]
            try:
                b = parse_bet_arg(val, message.from_user.id)
                if b > 0: bet = b
            except:
                traps = int(val)
        if traps < 1: traps = 1
        if traps > 4: traps = 4
        if bet <= 0: raise ValueError
        user_id = message.from_user.id
        balance = get_user_balance(user_id)
        if balance < bet:
            await message.reply(f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств! Баланс: {balance:.2f}$</b>', parse_mode="HTML")
            return
        
        st = get_tower_settings(user_id)
        st["bet"] = bet
        st["traps"] = traps
        
        user_balances[user_id] -= bet
        await update_balance(user_id, -bet)
        user_turnover[user_id] = get_user_turnover(user_id) + bet
        await update_global_stat('turnover_all', bet)
        await reduce_wager(user_id, bet)
        user_names[user_id] = message.from_user.full_name
        
        force_loss_floor = -1
        allow_wins = 0
        if user_id not in user_rigged_counters: user_rigged_counters[user_id] = {"wins": 0, "games": 0}
        user_rigged_counters[user_id]["games"] += 1
        if user_rigged_counters[user_id]["games"] >= 10:
            user_rigged_counters[user_id]["games"] = 0
            user_rigged_counters[user_id]["wins"] = 0
        
        if bet <= 0.15:
            if user_rigged_counters[user_id]["wins"] < 3: allow_wins = random.randint(2, 3)
            else: force_loss_floor = 0
        else:
            if random.random() < 0.90: force_loss_floor = random.randint(0, 2)
        
        trap_positions = {}
        for f_idx in range(TOWER_FLOORS):
            trap_positions[f_idx] = set(random.sample(range(5), traps))
        
        game_id = str(user_id)
        active_tower_games[game_id] = {
            "owner_id": user_id, "bet": bet, "traps_count": traps, "trap_positions": trap_positions,
            "current_floor": 0, "history": {}, "game_over": False, "current_win": 0.0, "game_id": game_id,
            "force_loss_floor": force_loss_floor, "allow_wins": allow_wins
        }
        game_data = active_tower_games[game_id]
        text = (
            f'<b><tg-emoji emoji-id="5449397725697187601">🗼</tg-emoji> Башня | Ставка: {bet:.2f} $ | Ловушек: {traps}</b>\n\n'
            f'<b>Этаж: 1 / {TOWER_FLOORS} | Выигрыш: 0.00 $</b>'
        )
        await message.answer(text, parse_mode="HTML", reply_markup=build_tower_game_keyboard(game_data), reply_to_message_id=message.message_id)
    except Exception:
        await message.reply('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Формат: башня [кол-во ловушек] [ставка]</b>', parse_mode="HTML")

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().startswith(("баскетбол", "баскет")))
async def group_basketball_handler(message: Message) -> None:
    if not await force_subscription_check(message): return
    try:
        parts = message.text.lower().split()
        if len(parts) < 3: raise ValueError
        bet = parse_bet_arg(parts[1], message.from_user.id)
        outcome = parts[2]
        if outcome not in ['гол', 'мимо', 'застрял'] or bet <= 0: raise ValueError
        user_id = message.from_user.id
        balance = get_user_balance(user_id)
        if balance < bet:
            await message.reply(f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств! Баланс: {balance:.2f}$</b>', parse_mode="HTML")
            return
        
        st = get_basketball_settings(user_id)
        st["bet"] = bet
        await message.answer(
            f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол | Ставка: {bet:.2f} $\n\nВыберите исход:</b>',
            parse_mode="HTML",
            reply_markup=get_basketball_type_keyboard(bet, user_id),
            reply_to_message_id=message.message_id
        )
    except (ValueError, IndexError):
        await message.reply('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Формат: баскет [ставка] [гол/мимо/застрял]</b>', parse_mode="HTML")

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().startswith("футбол"))
async def group_football_handler(message: Message) -> None:
    if not await force_subscription_check(message): return
    try:
        parts = message.text.lower().split()
        if len(parts) < 3: raise ValueError
        bet = parse_bet_arg(parts[1], message.from_user.id)
        outcome = parts[2]
        if outcome not in ['гол', 'мимо', 'штанга'] or bet <= 0: raise ValueError
        user_id = message.from_user.id
        balance = get_user_balance(user_id)
        if balance < bet:
            await message.reply(f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств! Баланс: {balance:.2f}$</b>', parse_mode="HTML")
            return
        
        st = get_football_settings(user_id)
        st["bet"] = bet
        await message.answer(
            f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол | Ставка: {bet:.2f} $\n\nВыберите исход:</b>',
            parse_mode="HTML",
            reply_markup=get_football_type_keyboard(bet, user_id),
            reply_to_message_id=message.message_id
        )
    except (ValueError, IndexError):
        await message.reply('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Формат: футбол [ставка] [гол/мимо/штанга]</b>', parse_mode="HTML")

@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), F.text.lower().startswith(("куб", "dice", "2куб")))
async def group_dice_handler(message: Message) -> None:
    if not await force_subscription_check(message): return
    try:
        txt = message.text.lower()
        parts = txt.split()
        is_2 = "2куб" in parts[0] or ("2" in parts and "куб" in txt)
        bet = 0.1
        btype = None
        keywords = ['чет', 'нечет', 'больше', 'меньше', 'семь']
        found_type = None
        found_bet = None
        for p in parts:
            if p in keywords: found_type = p
            elif p.replace('.','',1).replace(',','',1).isdigit() or p in ['вб', 'all']:
                found_bet = p
        if found_bet:
            bet = parse_bet_arg(found_bet, message.from_user.id)
        if found_type:
            btype = found_type
        if btype == 'семь': btype = 'seven'
        if not btype or bet <= 0: raise ValueError
        user_id = message.from_user.id
        balance = get_user_balance(user_id)
        if balance < bet:
            await message.reply(f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств! Баланс: {balance:.2f}$</b>', parse_mode="HTML")
            return
        
        user_balances[user_id] -= bet
        await update_balance(user_id, -bet)
        user_turnover[user_id] = get_user_turnover(user_id) + bet
        await update_global_stat('turnover_all', bet)
        await reduce_wager(user_id, bet)
        user_names[user_id] = message.from_user.full_name
        
        dice_emoji = "🎲"
        loading_msg = await message.reply(f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Бросаем кубики...</b>', parse_mode="HTML")
        
        if is_2:
            msg1 = await message.answer_dice(emoji=dice_emoji)
            msg2 = await message.answer_dice(emoji=dice_emoji)
            await asyncio.sleep(4)
            val1 = msg1.dice.value
            val2 = msg2.dice.value
            total = val1 + val2
            win = False
            coeff = DICE_COEFF_2
            if btype == 'чет': win = (total % 2 == 0)
            elif btype == 'нечет': win = (total % 2 != 0)
            elif btype == 'больше': win = (total > 7)
            elif btype == 'меньше': win = (total < 7)
            elif btype == 'seven':
                win = (total == 7)
                coeff = DICE_COEFF_SEVEN
            outcome_str = f"Сумма: {total}"
        else:
            msg = await message.answer_dice(emoji=dice_emoji)
            await asyncio.sleep(4)
            val = msg.dice.value
            win = False
            coeff = DICE_COEFF_1
            if btype == 'чет': win = (val % 2 == 0)
            elif btype == 'нечет': win = (val % 2 != 0)
            elif btype == 'больше': win = (val > 3)
            elif btype == 'меньше': win = (val < 4)
            outcome_str = f"Значение: {val}"
        
        if win:
            win_amt = bet * coeff
            user_balances[user_id] += win_amt
            await update_balance(user_id, win_amt)
            await log_bet_to_channel(message.bot, message.from_user, "Куб", bet, f"Победа ({btype}) 🏆", win_amt)
            res_text = f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Победа! {outcome_str}. Выигрыш: {win_amt:.2f}$</b>'
        else:
            await log_bet_to_channel(message.bot, message.from_user, "Куб", bet, f"Проигрыш ({btype}) ❌")
            res_text = f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Проигрыш. {outcome_str}.</b>'
        
        await loading_msg.edit_text(f'<b><tg-emoji emoji-id="{DICE_EMOJI_ID}">🎲</tg-emoji> Куб | {bet:.2f}$ | {btype}</b>\n\n{res_text}', parse_mode="HTML")
    except Exception:
        await message.reply('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Формат: куб [чет/нечет/больше/меньше/семь] [ставка]</b>', parse_mode="HTML")

# ИСПРАВЛЕННЫЙ /send
@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]), Command("send"))
async def group_send_handler(message: Message) -> None:
    reply_id = message.message_id
    if not await force_subscription_check(message): return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Укажите сумму! Например: /send 0.5</b>', parse_mode="HTML", reply_to_message_id=reply_id)
        return
    
    raw_amount = args[1].strip().replace("$", "").replace(",", ".")
    try:
        amount = float(raw_amount)
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма!</b>', parse_mode="HTML", reply_to_message_id=reply_id)
        return
    
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Ответьте на сообщение одного из игроков!</b>', parse_mode="HTML", reply_to_message_id=reply_id)
        return
    
    sender_id = message.from_user.id
    target_user = message.reply_to_message.from_user
    if sender_id == target_user.id:
        await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Нельзя отправить чек самому себе!</b>', parse_mode="HTML", reply_to_message_id=reply_id)
        return
    
    balance = get_user_balance(sender_id)
    if balance < amount:
        await message.answer(f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Недостаточно средств! Баланс: {balance:.2f}$</b>', parse_mode="HTML", reply_to_message_id=reply_id)
        return
    
    # Списываем баланс ОДИН раз
    user_balances[sender_id] -= amount
    await update_balance(sender_id, -amount)
    
    chek_id = generate_check_code()
    target_username = f"@{target_user.username}" if target_user.username else str(target_user.id)
    created_cheks[chek_id] = {
        "id": chek_id, "owner_id": sender_id, "amount": amount, "activations": 1, "rem_activations": 1,
        "password": None, "only_premium": False, "activated_users": set(), "target_user": target_username,
    }
    bot_info = await message.bot.get_me()
    check_link = f"https://t.me/{bot_info.username}?start={chek_id}"
    target_link = f'<a href="tg://user?id={target_user.id}">{html.quote(target_user.full_name)}</a>'
    text = (
        f'<b><tg-emoji emoji-id="5452157517062770940">💸</tg-emoji> Чек на {amount:.2f}$ для {target_link} успешно создан!</b>\n\n'
        f'<b>Ссылка:</b> <code>{check_link}</code>'
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 Активировать", url=check_link)]])
    await message.answer(text, parse_mode="HTML", reply_markup=kb, reply_to_message_id=reply_id)

@dp.message(F.text == "Меню")
async def menu_text_handler(message: Message, state: FSMContext) -> None:
    if message.chat.type != ChatType.PRIVATE: return
    await state.clear()
    if not await force_subscription_check(message, state): return
    await message.answer("<b>Главное меню:</b>", parse_mode="HTML", reply_markup=menu_inline_keyboard)

@dp.message(F.text == "Кошелек")
async def wallet_text_handler(message: Message, state: FSMContext) -> None:
    if message.chat.type != ChatType.PRIVATE: return
    await state.clear()
    if not await force_subscription_check(message, state): return
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    text = f'<b><tg-emoji emoji-id="5197686464325915345">💳</tg-emoji>Баланс: {balance:.2f} <tg-emoji emoji-id="5197422813463483902">💵</tg-emoji></b>'
    await message.answer(text, parse_mode="HTML", reply_markup=wallet_inline_keyboard)

@dp.message(F.text == "Играть")
async def play_text_handler(message: Message, state: FSMContext) -> None:
    if message.chat.type != ChatType.PRIVATE: return
    await state.clear()
    if not await force_subscription_check(message, state): return
    await message.answer('<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру:</b>', parse_mode="HTML", reply_markup=games_keyboard)

@dp.callback_query(F.data == "open_wallet_inline")
async def open_wallet_inline_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not await force_subscription_check(call, state): return
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    text = f'<b><tg-emoji emoji-id="5197686464325915345">👛</tg-emoji>Баланс: {balance:.2f} <tg-emoji emoji-id="5197422813463483902">💵</tg-emoji></b>'
    await safe_edit_message(call, text, wallet_inline_keyboard)

@dp.callback_query(F.data == "open_profile")
async def open_profile_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not await force_subscription_check(call, state): return
    user_id = call.from_user.id
    text = build_profile_text(user_id, call.from_user.full_name)
    await safe_edit_message(call, text, profile_inline_keyboard)

@dp.callback_query(F.data == "close_profile")
async def close_profile_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not await force_subscription_check(call, state): return
    await safe_edit_message(call, "<b>Главное меню:</b>", menu_inline_keyboard)

@dp.message(F.text == "/cancel")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer('<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Действие отменено.</b>', parse_mode="HTML", reply_markup=menu_inline_keyboard)

async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    await init_db()
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
