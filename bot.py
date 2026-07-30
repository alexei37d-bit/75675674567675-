import random
import asyncio
import string
import aiohttp
import logging
from aiogram import Bot, Dispatcher, F, html
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

logger = logging.getLogger(__name__)

TOKEN = "8740242990:AAF2I7c7x_SD6-Dww3WQJKQYbk3WsXYP5BI"
CRYPTO_PAY_TOKEN = "548204:AAZOXSPMBWOj3XO29UyRcrxpgxlzujtetPO"

dp = Dispatcher()

# --- АДМИН-ПАНЕЛЬ ---
ADMIN_IDS = {7921743592}

class AdminState(StatesGroup):
    waiting_for_add_admin = State()
    waiting_for_add_balance_user = State()
    waiting_for_add_balance_amount = State()
    waiting_for_sub_balance_user = State()
    waiting_for_sub_balance_amount = State()
    waiting_for_broadcast_text = State()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить админа", callback_data="admin_add_admin"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💵 Начислить баланс", callback_data="admin_add_balance"
                ),
                InlineKeyboardButton(
                    text="📉 Отнять баланс", callback_data="admin_sub_balance"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Список пользователей", callback_data="admin_users_list"
                ),
                InlineKeyboardButton(
                    text="📊 Статистика", callback_data="admin_stats"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка", callback_data="admin_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть", callback_data="admin_close"
                )
            ],
        ]
    )

@dp.message(F.text == "/admin")
async def admin_panel_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in ADMIN_IDS:
        return

    await message.answer(
        "<b>⚙️ Панель администратора:</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )

@dp.callback_query(F.data == "admin_close")
async def admin_close_handler(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await call.message.delete()

@dp.callback_query(F.data == "admin_add_admin")
async def admin_add_admin_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_add_admin)
    await call.message.edit_text(
        "➕ Введите Telegram ID пользователя, которого хотите сделать админом:",
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_add_admin)
async def admin_add_admin_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        new_admin_id = int(message.text.strip())
        ADMIN_IDS.add(new_admin_id)
        await state.clear()
        await message.answer(
            f"✅ Пользователь {new_admin_id} успешно добавлен в список администраторов!",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(),
        )
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число:")

@dp.callback_query(F.data == "admin_add_balance")
async def admin_add_balance_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_add_balance_user)
    await call.message.edit_text(
        "💵 Введите ID игрока, которому нужно НАЧИСЛИТЬ баланс:",
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_add_balance_user)
async def admin_add_balance_user_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(message.text.strip())
        await state.update_data(target_id=target_id)
        await state.set_state(AdminState.waiting_for_add_balance_amount)
        await message.answer("💵 Введите сумму для начисления:", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число:")

@dp.message(AdminState.waiting_for_add_balance_amount)
async def admin_add_balance_amount_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0:
            raise ValueError
        data = await state.get_data()
        target_id = data["target_id"]

        user_balances[target_id] = get_user_balance(target_id) + amount
        await state.clear()
        await message.answer(
            f"<b>✅ Успешно начислено {amount:.2f} $ игроку <code>{target_id}</code>!\n"
            f"Новый баланс: {user_balances[target_id]:.2f} $</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(),
        )
    except ValueError:
        await message.answer("<b>❌ Некорректная сумма. Введите положительное число:</b>")

@dp.callback_query(F.data == "admin_sub_balance")
async def admin_sub_balance_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_sub_balance_user)
    await call.message.edit_text(
        "📉 Введите ID игрока, у которого нужно ОТНЯТЬ баланс:",
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_sub_balance_user)
async def admin_sub_balance_user_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(message.text.strip())
        await state.update_data(target_id=target_id)
        await state.set_state(AdminState.waiting_for_sub_balance_amount)
        await message.answer("📉 Введите сумму для списания:", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число:")

@dp.message(AdminState.waiting_for_sub_balance_amount)
async def admin_sub_balance_amount_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0:
            raise ValueError
        data = await state.get_data()
        target_id = data["target_id"]

        current_bal = get_user_balance(target_id)
        user_balances[target_id] = max(0.0, current_bal - amount)
        await state.clear()
        await message.answer(
            f"<b>✅ Успешно списано {amount:.2f} $ у игрока <code>{target_id}</code>!\n"
            f"Новый баланс: {user_balances[target_id]:.2f} $</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(),
        )
    except ValueError:
        await message.answer("<b>❌ Некорректная сумма. Введите положительное число:</b>")

@dp.callback_query(F.data == "admin_users_list")
async def admin_users_list_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return

    if not user_balances:
        await call.message.edit_text(
            "<b>👥 Список пользователей пуст.</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(),
        )
        return

    text = "<b>👥 Список пользователей и их балансов:</b>\n\n"
    for uid, bal in user_balances.items():
        text += f"• ID: <code>{uid}</code> | Баланс: <code>{bal:.2f} $</code>\n"

    if len(text) > 4000:
        text = text[:4000] + "\n..."

    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(call: CallbackQuery) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return

    total_users = len(user_balances)
    total_balance = sum(user_balances.values())
    active_games_cnt = len(active_games) + len(active_tower_games)

    text = (
        "<b>📊 Статистика бота:</b>\n\n"
        f"<b>• Всего пользователей:</b> <code>{total_users}</code>\n"
        f"<b>• Общая сумма балансов:</b> <code>{total_balance:.2f} $</code>\n"
        f"<b>• Активных игр сейчас:</b> <code>{active_games_cnt}</code>\n"
        f"<b>• Администраторов:</b> <code>{len(ADMIN_IDS)}</code>"
    )

    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_broadcast_text)
    await call.message.edit_text(
        "📢 Введите текст для рассылки всем пользователям:",
        parse_mode="HTML",
    )

@dp.message(AdminState.waiting_for_broadcast_text)
async def admin_broadcast_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.clear()
    broadcast_text = message.text
    success = 0
    failed = 0

    status_msg = await message.answer("<b>⏳ Рассылка выполняется...</b>", parse_mode="HTML")

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
        f"<b>📢 Рассылка завершена!</b>\n\n"
        f"<b>✅ Успешно доставлено:</b> {success}\n"
        f"<b>❌ Не доставлено:</b> {failed}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )
# --- КОНЕЦ АДМИН-ПАНЕЛИ ---

user_balances = {}
user_turnover = {}
active_games = {}
game_settings = {}
active_tower_games = {}
tower_game_settings = {}
user_bets_counter = {}

# Настройки и состояние для баскетбола
basketball_settings = {}
basketball_coeffs = {
    'гол': 1.9,
    'мимо': 1.4,
    'застрял': 2.75
}

# Настройки и состояние для футбола
football_settings = {}
football_coeffs = {
    'гол': 1.4,
    'мимо': 1.85,
    'штанга': 2.75
}

# Хранилище чеков: check_id -> dict
created_cheks = {}

# Хранилище активных сообщений/игр пользователя
user_active_game_msg = {}

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

class ChekState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_activations = State()
    waiting_for_password = State()
    waiting_for_check_pass_input = State()
    waiting_for_target_user = State()

class DepositState(StatesGroup):
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
    return user_balances.setdefault(user_id, 1.00)

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

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Кошелек", icon_custom_emoji_id="5197686464325915345"
            ),
            KeyboardButton(
                text="Играть", icon_custom_emoji_id="5471895876790161593"
            ),
            KeyboardButton(
                text="Меню", icon_custom_emoji_id="5278413853577734640"
            ),
        ]
    ],
    resize_keyboard=True,
)

menu_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Профиль",
                icon_custom_emoji_id="5308004189677330658",
                callback_data="open_profile",
            )
        ],
        [
            InlineKeyboardButton(
                text="Играть",
                icon_custom_emoji_id="5471895876790161593",
                callback_data="back_to_games",
            ),
            InlineKeyboardButton(
                text="Кошелек",
                icon_custom_emoji_id="5197686464325915345",
                callback_data="open_wallet_inline",
            ),
        ],
        [
            InlineKeyboardButton(
                text="Чеки",
                icon_custom_emoji_id="5452157517062770940",
                callback_data="open_cheks_menu",
            )
        ],
    ]
)

wallet_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Пополнить",
                icon_custom_emoji_id="5255805270285653933",
                callback_data="deposit",
            ),
            InlineKeyboardButton(
                text="Вывести",
                icon_custom_emoji_id="5255868234506213301",
                callback_data="withdraw",
            ),
        ]
    ]
)

profile_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Пополнить",
                icon_custom_emoji_id="5255805270285653933",
                callback_data="deposit",
            ),
            InlineKeyboardButton(
                text="Вывести",
                icon_custom_emoji_id="5255868234506213301",
                callback_data="withdraw",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀ Назад",
                callback_data="close_profile",
            )
        ],
    ]
)

games_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Мины",
                icon_custom_emoji_id="5452018153963948977",
                callback_data="mines_choose_bet",
            ),
            InlineKeyboardButton(
                text="Башня",
                icon_custom_emoji_id="5449397725697187601",
                callback_data="tower_choose_bet",
            )
        ],
        [
            InlineKeyboardButton(
                text="Баскетбол",
                icon_custom_emoji_id="5465317563145686803",
                callback_data="basketball_choose_bet",
            )
        ],
        [
            InlineKeyboardButton(
                text="Футбол",
                icon_custom_emoji_id="5319298377412812014",
                callback_data="football_choose_bet",
            )
        ]
    ]
)

def get_cheks_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Создать чек", callback_data="chek_create_start"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Активные чеки", callback_data="chek_active_list"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data="close_profile"
                )
            ],
        ]
    )

def get_chek_amount_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="0.1$", callback_data="chek_amount_0.1"
                ),
                InlineKeyboardButton(
                    text="Весь баланс", callback_data="chek_amount_all"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data="open_cheks_menu"
                )
            ],
        ]
    )

def get_chek_manage_keyboard(chek_id: str) -> InlineKeyboardMarkup:
    chek = created_cheks.get(chek_id, {})
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Поделиться",
                    switch_inline_query=f"{chek_id}",
                ),
                InlineKeyboardButton(
                    text="Скопировать",
                    icon_custom_emoji_id="5377535110289576661",
                    callback_data=f"chek_copy_link:{chek_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Ограничения",
                    icon_custom_emoji_id="5312462735097764089",
                    callback_data=f"chek_limits_menu:{chek_id}",
                ),
                InlineKeyboardButton(
                    text="Удалить чек",
                    icon_custom_emoji_id="5296410453742753454",
                    callback_data=f"chek_delete:{chek_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data="open_cheks_menu"
                )
            ],
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

    prem_text = (
        "Для всех игроков"
        if chek.get("only_premium")
        else "Только для TG Premium"
    )

    if chek.get("target_user"):
        pin_limit_text = "Открепить чек"
        pin_limit_cbd = f"chek_unpin_user:{chek_id}"
    else:
        pin_limit_text = "Закрепить за пользователем"
        pin_limit_cbd = f"chek_pin_user:{chek_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=pass_text,
                    icon_custom_emoji_id=pass_emoji,
                    callback_data=pass_cbd,
                )
            ],
            [
                InlineKeyboardButton(
                    text=prem_text,
                    icon_custom_emoji_id="5303170015007119865",
                    callback_data=f"chek_toggle_premium:{chek_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=pin_limit_text,
                    icon_custom_emoji_id="5197269100878907942",
                    callback_data=pin_limit_cbd,
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data=f"chek_manage:{chek_id}"
                )
            ],
        ]
    )

def get_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="0.1$", callback_data=f"select_bet_0.1:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="0.5$", callback_data=f"select_bet_0.5:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="1$", callback_data=f"select_bet_1.0:{owner_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data=f"back_to_games:{owner_id}"
                )
            ],
        ]
    )

def get_preview_game_keyboard(
    user_id: int, owner_id: int = None
) -> InlineKeyboardMarkup:
    if owner_id is None:
        owner_id = user_id
    st = get_game_settings(user_id)
    bet = st["bet"]
    mines = st["mines"]

    keyboard = []
    for _ in range(5):
        row = [
            InlineKeyboardButton(text="🌑", callback_data="locked_cell")
            for _ in range(5)
        ]
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"Играть {bet:.2f}",
                icon_custom_emoji_id="5305445793623218874",
                callback_data=f"start_mines_game:{owner_id}",
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"💣 Мин: {mines}",
                callback_data=f"screen_choose_mines:{owner_id}",
            ),
            InlineKeyboardButton(
                text="◀ Ставка", callback_data=f"mines_choose_bet:{owner_id}"
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_mines_count_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="2", callback_data=f"set_mines_cnt_2:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="3", callback_data=f"set_mines_cnt_3:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="5", callback_data=f"set_mines_cnt_5:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="10", callback_data=f"set_mines_cnt_10:{owner_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="15", callback_data=f"set_mines_cnt_15:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="20", callback_data=f"set_mines_cnt_20:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="24", callback_data=f"set_mines_cnt_24:{owner_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад",
                    callback_data=f"screen_game_confirm:{owner_id}",
                )
            ],
        ]
    )

def build_game_keyboard(
    game_data: dict, finished: bool = False
) -> InlineKeyboardMarkup:
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

            row_buttons.append(
                InlineKeyboardButton(
                    text=text, callback_data=f"open_cell_{idx}:{game_id}"
                )
            )
        keyboard.append(row_buttons)

    if not game_over and len(opened) > 0:
        current_win = game_data["current_win"]
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"Забрать {current_win:.2f}",
                    icon_custom_emoji_id="5305445793623218874",
                    callback_data=f"cashout_mines:{game_id}",
                )
            ]
        )

    if finished:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🔄 Сыграть снова",
                    callback_data=f"screen_game_confirm:{owner_id}",
                ),
                InlineKeyboardButton(
                    text="◀ Меню", callback_data=f"mines_choose_bet:{owner_id}"
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def calculate_multiplier(mines_count: int, opened_count: int) -> float:
    base = 1.0 + (mines_count * 0.05)
    mult = base ** opened_count
    return max(round(mult, 2), 1.01)

def build_profile_text(user_id: int, full_name: str) -> str:
    balance = get_user_balance(user_id)
    turnover = get_user_turnover(user_id)
    return (
        f'<b><tg-emoji emoji-id=\"5197514090108456970\">👤</tg-emoji> Имя: {html.quote(full_name)}\n</b>'
        f'<b><tg-emoji emoji-id=\"5449624985301717991\">💳</tg-emoji> Ваш ID : {user_id}\n</b>'
        f'<b><tg-emoji emoji-id=\"5451845260055450038\">💰</tg-emoji> Баланс: {balance:.2f} <tg-emoji emoji-id=\"5197422813463483902\">💵</tg-emoji>\n</b>'
        f'<b><tg-emoji emoji-id=\"5452042536493288421\">📊</tg-emoji> Оборот : {turnover:.2f} <tg-emoji emoji-id=\"5197422813463483902\">💵</tg-emoji></b>'
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
                InlineKeyboardButton(
                    text="0.1$",
                    callback_data=f"select_tower_bet_0.1:{owner_id}",
                ),
                InlineKeyboardButton(
                    text="0.5$",
                    callback_data=f"select_tower_bet_0.5:{owner_id}",
                ),
                InlineKeyboardButton(
                    text="1$", callback_data=f"select_tower_bet_1.0:{owner_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data=f"back_to_games:{owner_id}"
                )
            ],
        ]
    )

def get_preview_tower_keyboard(
    user_id: int, owner_id: int = None
) -> InlineKeyboardMarkup:
    if owner_id is None:
        owner_id = user_id
    st = get_tower_settings(user_id)
    bet = st["bet"]
    traps = st["traps"]

    keyboard = []
    for floor_idx in range(TOWER_FLOORS):
        x_mult = calculate_tower_multiplier(traps, floor_idx + 1)
        row = [
            InlineKeyboardButton(
                text=f"x{x_mult:.1f}", callback_data="locked_cell"
            )
        ]
        row.extend(
            [
                InlineKeyboardButton(text="🌑", callback_data="locked_cell")
                for _ in range(5)
            ]
        )
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"Играть {bet:.2f}",
                icon_custom_emoji_id="5305445793623218874",
                callback_data=f"start_tower_game:{owner_id}",
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"💣 Мин: {traps}",
                callback_data=f"screen_choose_tower_traps:{owner_id}",
            ),
            InlineKeyboardButton(
                text="◀ Ставка", callback_data=f"tower_choose_bet:{owner_id}"
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_tower_traps_count_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1", callback_data=f"set_tower_traps_cnt_1:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="2", callback_data=f"set_tower_traps_cnt_2:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="3", callback_data=f"set_tower_traps_cnt_3:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="4", callback_data=f"set_tower_traps_cnt_4:{owner_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад",
                    callback_data=f"screen_tower_game_confirm:{owner_id}",
                )
            ],
        ]
    )

def build_tower_game_keyboard(
    game_data: dict, finished: bool = False
) -> InlineKeyboardMarkup:
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
        row_buttons.append(
            InlineKeyboardButton(
                text=f"x{x_mult:.1f}", callback_data="locked_cell"
            )
        )

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

            row_buttons.append(
                InlineKeyboardButton(text=text, callback_data=cbd)
            )
        keyboard.append(row_buttons)

    if not game_over and current_floor > 0:
        current_win = game_data["current_win"]
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"Забрать {current_win:.2f}",
                    icon_custom_emoji_id="5305445793623218874",
                    callback_data=f"cashout_tower:{game_id}",
                )
            ]
        )

    if finished:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🔄 Сыграть снова",
                    callback_data=f"screen_tower_game_confirm:{owner_id}",
                ),
                InlineKeyboardButton(
                    text="◀ Меню", callback_data=f"tower_choose_bet:{owner_id}"
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ И ФУНКЦИИ ДЛЯ БАСКЕТБОЛА ---
def get_basketball_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="0.1$", callback_data=f"select_basketball_bet_0.1:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="0.5$", callback_data=f"select_basketball_bet_0.5:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="1$", callback_data=f"select_basketball_bet_1.0:{owner_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data=f"back_to_games:{owner_id}"
                )
            ],
        ]
    )

def get_basketball_type_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Гол (x{basketball_coeffs['гол']})",
                    callback_data=f"basketball_bet_гол_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Мимо (x{basketball_coeffs['мимо']})",
                    callback_data=f"basketball_bet_мимо_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Застрял (x{basketball_coeffs['застрял']})",
                    callback_data=f"basketball_bet_застрял_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀ Изменить ставку",
                    callback_data=f"basketball_choose_bet:{owner_id}",
                )
            ],
        ]
    )

def get_basketball_result_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏀 Сыграть ещё",
                    callback_data=f"basketball_repeat_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад к играм",
                    callback_data=f"back_to_games:{owner_id}",
                )
            ],
        ]
    )

def get_basketball_bet_type_name(bet_type: str) -> str:
    names = {
        'гол': 'Гол',
        'мимо': 'Мимо',
        'застрял': 'Застрял'
    }
    return names.get(bet_type, bet_type)

def calculate_basketball_result(basketball_value: int, bet_type: str):
    result = {
        'win': False,
        'multiplier': 0
    }
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

# --- ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ И ФУНКЦИИ ДЛЯ ФУТБОЛА ---
def get_football_bet_selection_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="0.1$", callback_data=f"select_football_bet_0.1:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="0.5$", callback_data=f"select_football_bet_0.5:{owner_id}"
                ),
                InlineKeyboardButton(
                    text="1$", callback_data=f"select_football_bet_1.0:{owner_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data=f"back_to_games:{owner_id}"
                )
            ],
        ]
    )

def get_football_type_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Гол (x{football_coeffs['гол']})",
                    callback_data=f"football_bet_гол_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Мимо (x{football_coeffs['мимо']})",
                    callback_data=f"football_bet_мимо_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Штанга (x{football_coeffs['штанга']})",
                    callback_data=f"football_bet_штанга_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀ Изменить ставку",
                    callback_data=f"football_choose_bet:{owner_id}",
                )
            ],
        ]
    )

def get_football_result_keyboard(bet: float, owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚽ Сыграть ещё",
                    callback_data=f"football_repeat_{bet}:{owner_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад к играм",
                    callback_data=f"back_to_games:{owner_id}",
                )
            ],
        ]
    )

def get_football_bet_type_name(bet_type: str) -> str:
    names = {
        'гол': 'Гол',
        'мимо': 'Мимо',
        'штанга': 'Штанга'
    }
    return names.get(bet_type, bet_type)

def calculate_football_result(football_value: int, bet_type: str):
    result = {
        'win': False,
        'multiplier': 0
    }
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

async def safe_edit_message(
    call: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup
):
    try:
        await call.message.edit_text(
            text=text, parse_mode="HTML", reply_markup=reply_markup
        )
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

# --- ПОПОЛНЕНИЕ СЧЕТА CRYPTO BOT ---
@dp.callback_query(F.data == "deposit")
async def deposit_start_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DepositState.waiting_for_amount)
    text = '<tg-emoji emoji-id="5449789954995559460">💎</tg-emoji> Введите сумму для пополнения баланса в USDT (например: 0,10$):'
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data="open_wallet_inline")]
        ]
    )
    await safe_edit_message(call, text, kb)

@dp.message(DepositState.waiting_for_amount)
async def deposit_amount_process(message: Message, state: FSMContext) -> None:
    try:
        amount = float(message.text.replace("$", "").replace(",", ".").strip())
        if amount < 0.1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную сумму больше 0.1 USDT:", parse_mode="HTML")
        return

    await state.clear()
    invoice = await create_crypto_invoice(amount)
    if not invoice:
        await message.answer("<b>❌ Ошибка создания счета. Попробуйте позже.</b>", parse_mode="HTML")
        return

    invoice_id = invoice["invoice_id"]
    pay_url = invoice["pay_url"]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💵 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_pay:{invoice_id}:{amount}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="open_wallet_inline")]
        ]
    )

    await message.answer(
        f"<b><tg-emoji emoji-id=\"5452168761287152584\">🎁</tg-emoji> Счет на пополнение {amount:.2f} USDT создан!</b>\n\nОплатите его по кнопке ниже и нажмите «Проверить оплату»:",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("check_pay:"))
async def check_pay_handler(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    invoice_id = int(parts[1])
    amount = float(parts[2])

    status = await get_crypto_invoice_status(invoice_id)
    if status == "paid":
        user_id = call.from_user.id
        user_balances[user_id] = get_user_balance(user_id) + amount
        await call.answer("✅ Оплата успешно подтверждена!", show_alert=True)
        text = f"<b>🎉 Баланс успешно пополнен на {amount:.2f} $!</b>"
        await safe_edit_message(call, text, wallet_inline_keyboard)
    else:
        await call.answer("❌ Счет еще не оплачен!", show_alert=True)

@dp.callback_query(F.data == "withdraw")
async def withdraw_handler(call: CallbackQuery) -> None:
    await call.answer("Для вывода средств обратитесь к администратору.", show_alert=True)

# --- РАЗДЕЛ ЧЕКИ ---
@dp.callback_query(F.data == "open_cheks_menu")
async def open_cheks_menu_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = (
        '<b><tg-emoji emoji-id=\"5307773751796996779\">🎟</tg-emoji></b>'
        '<b>Создайте чек для мгновенной отправки средств пользователю или группе пользователей - </b>'
        '<b>просто укажите количество активаций!</b>'
    )
    await safe_edit_message(call, text, get_cheks_main_keyboard())

@dp.callback_query(F.data == "chek_create_start")
async def chek_create_start_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    if call.message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await call.answer()
        await call.message.answer(
            '<b>Перейдите в личные сообщения с ботом <tg-emoji emoji-id="5312140414982071786">❌</tg-emoji></b>',
            parse_mode="HTML"
        )
        return

    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    if balance <= 0:
        await call.answer(
            "<b>❌ У вас недостаточный баланс для создания чека!</b>", show_alert=True
        )
        return

    await state.set_state(ChekState.waiting_for_amount)
    text = (
        '<b><tg-emoji emoji-id="5449526218233779946">👛</tg-emoji> Отправьте сумму 1 активации :</b>'
    )
    await safe_edit_message(call, text, get_chek_amount_keyboard())

@dp.callback_query(F.data.startswith("chek_amount_"))
async def process_chek_quick_amount(
    call: CallbackQuery, state: FSMContext
) -> None:
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

    user_balances[user_id] -= amount
    chek_id = generate_check_code()
    created_cheks[chek_id] = {
        "id": chek_id,
        "owner_id": user_id,
        "amount": amount,
        "activations": 1,
        "rem_activations": 1,
        "password": None,
        "only_premium": False,
        "activated_users": set(),
        "target_user": None,
    }
    await state.clear()

    bot_info = await call.bot.get_me()
    check_link = f"https://t.me/{bot_info.username}?start={chek_id}"
    title_str = f"Чек на {amount:.2f}$"

    text = (
        f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> {title_str} успешно создан!\n\n'
        f"Ссылка на чек: <code>{check_link}</code></b>"
    )
    await safe_edit_message(call, text, get_chek_manage_keyboard(chek_id))

@dp.message(ChekState.waiting_for_amount)
async def process_chek_amount_input(
    message: Message, state: FSMContext
) -> None:
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await message.answer(
            'Перейдите в личные сообщения с ботом <tg-emoji emoji-id="5312140414982071786">❌</tg-emoji>',
            parse_mode="HTML"
        )
        return

    user_id = message.from_user.id
    balance = get_user_balance(user_id)

    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        amount = float(raw_text)
        if amount <= 0 or amount > balance:
            raise ValueError

        user_balances[user_id] -= amount
        chek_id = generate_check_code()
        created_cheks[chek_id] = {
            "id": chek_id,
            "owner_id": user_id,
            "amount": amount,
            "activations": 1,
            "rem_activations": 1,
            "password": None,
            "only_premium": False,
            "activated_users": set(),
            "target_user": None,
        }
        await state.clear()

        bot_info = await message.bot.get_me()
        check_link = f"https://t.me/{bot_info.username}?start={chek_id}"
        title_str = f"Чек на {amount:.2f}$"

        text = (
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> {title_str} успешно создан!\n\n'
            f"Ссылка на чек: <code>{check_link}</code></b>"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_chek_manage_keyboard(chek_id))
    except ValueError:
        await message.answer(
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Некорректная сумма! Введите число от 0.01 до {balance:.2f}:</b>',
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
        title_str = f"Чек на {amount:.2f}$ на {activations} активаций"

    target_info = f"\nЗакреплен за: {chek['target_user']}" if chek.get("target_user") else ""

    text = (
        f'<b><tg-emoji emoji-id="5451807640436903198">🎰</tg-emoji> Управление: {title_str}\n\n'
        f"Ссылка на чек: <code>{check_link}</code>\n"
        f"Осталось активаций: {chek['rem_activations']}/{activations}{target_info}</b>"
    )
    await safe_edit_message(call, text, get_chek_manage_keyboard(chek_id))

@dp.callback_query(F.data.startswith("chek_pin_user:"))
async def chek_pin_user_start(call: CallbackQuery, state: FSMContext) -> None:
    chek_id = call.data.split(":")[1]
    await state.update_data(target_chek_id=chek_id)
    await state.set_state(ChekState.waiting_for_target_user)

    text = (
        '<b><tg-emoji emoji-id="5197269100878907942">📌</tg-emoji> Введите @username или ID пользователя, '
        'за которым нужно закрепить чек:</b>'
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀ Назад",
                    callback_data=f"chek_manage:{chek_id}",
                )
            ]
        ]
    )
    await safe_edit_message(call, text, kb)

@dp.message(ChekState.waiting_for_target_user)
async def chek_pin_user_process(message: Message, state: FSMContext) -> None:
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
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_chek_manage_keyboard(chek_id),
        )

@dp.callback_query(F.data.startswith("chek_unpin_user:"))
async def chek_unpin_user_handler(call: CallbackQuery, state: FSMContext) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if chek:
        chek["target_user"] = None
        await call.answer("Чек откреплен!", show_alert=True)
        await chek_manage_handler(call, state)

@dp.callback_query(F.data.startswith("chek_limits_menu:"))
async def chek_limits_menu_handler(call: CallbackQuery, state: FSMContext = None) -> None:
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
        f'<b><tg-emoji emoji-id="5451807640436903198">🎰</tg-emoji> Настройка ограничений чека <code>{chek_id}</code>:\n\n'
        f"• Пароль: {has_pass}\n"
        f"• Только Telegram Premium: {only_prem}\n"
        f"• Закреплен за: {target_info}</b>"
    )
    await safe_edit_message(call, text, get_chek_limits_keyboard(chek_id))

@dp.callback_query(F.data.startswith("chek_set_pass:"))
async def chek_set_pass_start(call: CallbackQuery, state: FSMContext) -> None:
    chek_id = call.data.split(":")[1]
    await state.update_data(target_chek_id=chek_id)
    await state.set_state(ChekState.waiting_for_password)

    text = "<b><tg-emoji emoji-id=\"5188276641951948688\">🃏</tg-emoji> Введите пароль для чека в чат:</b>"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀ Назад",
                    callback_data=f"chek_limits_menu:{chek_id}",
                )
            ]
        ]
    )
    await safe_edit_message(call, text, kb)

@dp.callback_query(F.data.startswith("chek_remove_pass:"))
async def chek_remove_pass_handler(call: CallbackQuery, state: FSMContext) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if chek:
        chek["password"] = None
        await call.answer("Пароль успешно удален!", show_alert=True)
        await chek_limits_menu_handler(call, state)

@dp.message(ChekState.waiting_for_password)
async def chek_set_pass_process(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    chek_id = data.get("target_chek_id")
    chek = created_cheks.get(chek_id)

    if chek:
        pwd = message.text.strip()
        chek["password"] = pwd
        await state.clear()

        text = f"<b><tg-emoji emoji-id=\"5463249656651747420\">🎁</tg-emoji> Пароль «{pwd}» успешно установлен на чек!</b>"
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_chek_limits_keyboard(chek_id),
        )

@dp.callback_query(F.data.startswith("chek_toggle_premium:"))
async def chek_toggle_premium_handler(call: CallbackQuery, state: FSMContext) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if chek:
        chek["only_premium"] = not chek["only_premium"]
        await chek_limits_menu_handler(call, state)

@dp.callback_query(F.data.startswith("chek_delete:"))
async def chek_delete_handler(call: CallbackQuery) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if chek:
        rem_money = chek["amount"] * chek["rem_activations"]
        user_balances[chek["owner_id"]] = (
            get_user_balance(chek["owner_id"]) + rem_money
        )

        del created_cheks[chek_id]

        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass

@dp.callback_query(F.data == "chek_active_list")
async def chek_active_list_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    user_cheks = [
        c for c in created_cheks.values() if c["owner_id"] == user_id
    ]

    if not user_cheks:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀ Назад", callback_data="open_cheks_menu"
                    )
                ]
            ]
        )
        await safe_edit_message(
            call, "<b><tg-emoji emoji-id=\"5469638931605657197\">🏦</tg-emoji> У вас нет активных чеков!</b>", kb
        )
        return

    keyboard = []
    for c in user_cheks:
        btn_text = f"Чек {c['amount']:.2f}$ ({c['rem_activations']}/{c['activations']})"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=btn_text, callback_data=f"chek_manage:{c['id']}"
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                text="◀ Назад", callback_data="open_cheks_menu"
            )
        ]
    )

    await safe_edit_message(
        call,
        "<b><tg-emoji emoji-id=\"5469638931605657197\">🏦</tg-emoji> Ваши активные чеки:</b>",
        InlineKeyboardMarkup(inline_keyboard=keyboard),
    )

# --- ЛОГИКА ИНЛАЙН И АКТИВАЦИИ ЧЕКОВ ---
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
        caption_text = f"<b>💸 Чек на {amount_str}${target_str}</b>"
        desc_str = f"Чек на {amount_str}${target_str}"
    else:
        if 2 <= acts <= 4:
            act_str = f"{acts} активации"
        else:
            act_str = f"{acts} активаций"
        caption_text = f"<b>💸 Чек на {amount_str}${target_str}\n{act_str}</b>"
        desc_str = f"На {act_str}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Получить",
                    url=f"https://t.me/{bot_info.username}?start={chek['id']}",
                )
            ]
        ]
    )

    item = InlineQueryResultArticle(
        id=chek_id,
        title=f"Отправить чек на {amount_str}$",
        description=desc_str,
        input_message_content=InputTextMessageContent(
            message_text=caption_text, parse_mode="HTML"
        ),
        reply_markup=keyboard,
    )
    await query.answer([item], cache_time=1)

async def complete_chek_activation(
    message_or_call, user, chek: dict, state: FSMContext = None
) -> None:
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
            err_msg = "Чек предназначен для другого игрока!"
            if isinstance(message_or_call, Message):
                await message_or_call.answer(f"<b>{err_msg}</b>", parse_mode="HTML")
            else:
                await message_or_call.answer(err_msg, show_alert=True)
            return

    chek["rem_activations"] -= 1
    if "activated_users" not in chek:
        chek["activated_users"] = set()
    chek["activated_users"].add(user_id)

    user_balances[user_id] = get_user_balance(user_id) + chek["amount"]

    if chek["rem_activations"] <= 0:
        if chek["id"] in created_cheks:
            del created_cheks[chek["id"]]

    amount_str = f"{chek['amount']:.2f}".rstrip("0").rstrip(".")
    if chek["amount"].is_integer():
        amount_str = str(int(chek["amount"]))

    text = (
        f'<b><tg-emoji emoji-id="5452157517062770940">💸</tg-emoji> Вы получили {amount_str}$</b>'
    )

    if isinstance(message_or_call, Message):
        await message_or_call.answer(text, parse_mode="HTML")
    else:
        await message_or_call.message.answer(text, parse_mode="HTML")

    if state:
        await state.clear()

    user_name = html.quote(user.full_name)
    user_link = f'<a href="tg://user?id={user_id}">{user_name}</a>'
    owner_text = (
        f'<b><tg-emoji emoji-id="5307773751796996779">🎟</tg-emoji> {user_link} '
        f"активировал ваш чек на {amount_str}$</b>"
    )
    try:
        await message_or_call.bot.send_message(
            chek["owner_id"], owner_text, parse_mode="HTML"
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("activate_chek_btn:"))
async def activate_chek_btn_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if not chek:
        await call.answer("Чек не найден!", show_alert=True)
        return

    user = call.from_user
    user_id = user.id

    if "activated_users" in chek and user_id in chek["activated_users"]:
        await call.answer("Этот чек уже активирован!", show_alert=True)
        return

    if chek["rem_activations"] <= 0:
        await call.answer("Этот чек уже активирован!", show_alert=True)
        return

    if chek.get("only_premium") and not getattr(user, "is_premium", False):
        await call.answer(
            "Этот чек доступен только для премиум-пользователей!",
            show_alert=True,
        )
        return

    if chek.get("password"):
        await state.update_data(target_chek_id=chek_id)
        await state.set_state(ChekState.waiting_for_check_pass_input)
        text = "<b>Введите пароль для использования чека:</b>"
        await call.message.answer(text, parse_mode="HTML")
        await call.answer()
        return

    await complete_chek_activation(call, user, chek, state)
    await call.answer()

@dp.message(ChekState.waiting_for_check_pass_input)
async def process_check_pass_input(
    message: Message, state: FSMContext
) -> None:
    data = await state.get_data()
    chek_id = data.get("target_chek_id")
    chek = created_cheks.get(chek_id)

    if not chek:
        await message.answer("<b>Чек не найден!</b>", parse_mode="HTML")
        await state.clear()
        return

    user = message.from_user
    user_id = user.id

    if "activated_users" in chek and user_id in chek["activated_users"]:
        await message.answer(
            "<b>Этот чек уже активирован!</b>", parse_mode="HTML"
        )
        await state.clear()
        return

    if chek["rem_activations"] <= 0:
        await message.answer(
            "<b>Этот чек уже активирован!</b>", parse_mode="HTML"
        )
        await state.clear()
        return

    if chek.get("only_premium") and not getattr(user, "is_premium", False):
        await message.answer(
            "<b>Этот чек доступен только для премиум-пользователей!</b>",
            parse_mode="HTML",
        )
        await state.clear()
        return

    pwd_input = message.text.strip()
    if pwd_input != chek["password"]:
        await message.answer("<b>❌ Неверный пароль! Попробуйте снова:</b>")
        return

    await complete_chek_activation(message, user, chek, state)

# --- ОСНОВНЫЕ ИГРОВЫЕ И СИСТЕМНЫЕ ХЕНДЛЕРЫ ---
@dp.callback_query(F.data.startswith("mines_choose_bet"))
async def mines_choose_bet_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.set_state(MinesState.waiting_for_custom_bet)
    text = (
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку:\n'
        "Или напишите сумму ставки в чат</b>"
    )
    await safe_edit_message(call, text, get_bet_selection_keyboard(owner_id))

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    user = message.from_user
    user_id = user.id if user else 0
    user_name = user.first_name if user else "Игрок"

    get_user_balance(user_id)
    get_user_turnover(user_id)

    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        chek_id = args[1].strip()
        if chek_id.startswith("check_"):
            chek_id = "chek_" + chek_id[6:]

        chek = created_cheks.get(chek_id)

        if not chek:
            await message.answer("<b>Чек не найден!</b>", parse_mode="HTML")
            return

        if "activated_users" in chek and user_id in chek["activated_users"]:
            await message.answer(
                "<b>Этот чек уже активирован!</b>", parse_mode="HTML"
            )
            return

        if chek["rem_activations"] <= 0:
            await message.answer(
                "<b>Этот чек уже активирован!</b>", parse_mode="HTML"
            )
            return

        if chek.get("only_premium") and not getattr(user, "is_premium", False):
            await message.answer(
                "<b>Этот чек доступен только для премиум-пользователей!</b>",
                parse_mode="HTML",
            )
            return

        if chek.get("password"):
            await state.update_data(target_chek_id=chek_id)
            await state.set_state(ChekState.waiting_for_check_pass_input)
            await message.answer(
                "<b>Введите пароль для использования чека в чат:</b>",
                parse_mode="HTML",
            )
            return

        await complete_chek_activation(message, user, chek, state)
        return

    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)

@dp.message(F.text.in_(["Меню", "/menu"]))
async def menu_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5278702045883292456">🛍</tg-emoji> Выберите действие!\n\n'
        f'<tg-emoji emoji-id="5242253527480311898">🪙</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await message.answer(
        text=text, parse_mode="HTML", reply_markup=menu_inline_keyboard
    )

@dp.callback_query(F.data == "open_profile")
async def open_profile_callback(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    full_name = call.from_user.full_name if call.from_user else "Игрок"

    text = build_profile_text(user_id, full_name)
    await safe_edit_message(call, text, profile_inline_keyboard)

@dp.callback_query(F.data == "close_profile")
async def close_profile_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5278702045883292456">🛍</tg-emoji> Выберите действие!\n\n'
        f'<tg-emoji emoji-id="5242253527480311898">🪙</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, menu_inline_keyboard)

@dp.callback_query(F.data == "open_wallet_inline")
async def open_wallet_inline_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    text = (
        f'<b><tg-emoji emoji-id="5470019396988606408">💵</tg-emoji> '
        f"Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji></b>"
    )
    await safe_edit_message(call, text, wallet_inline_keyboard)

@dp.message(F.text.in_(["Кошелек", "Баланс", "/wallet", "/balance"]))
async def wallet_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = get_user_balance(user_id)

    text = (
        f'<b><tg-emoji emoji-id="5470019396988606408">💵</tg-emoji> '
        f"Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji></b>"
    )
    await message.answer(
        text=text, parse_mode="HTML", reply_markup=wallet_inline_keyboard
    )

@dp.message(F.text.in_(["Играть", "/play"]))
async def play_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки!\n\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await message.answer(
        text=text, parse_mode="HTML", reply_markup=games_keyboard
    )

@dp.callback_query(F.data.startswith("back_to_games"))
async def back_to_games_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.clear()
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки!\n\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, games_keyboard)

@dp.callback_query(F.data.startswith("select_bet_"))
async def select_bet_quick(call: CallbackQuery, state: FSMContext) -> None:
    data_parts = call.data.split(":")
    owner_id = int(data_parts[1]) if len(data_parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.clear()
    user_id = call.from_user.id
    bet = float(data_parts[0].split("_")[2])
    st = get_game_settings(user_id)
    st["bet"] = bet

    await screen_game_confirm(call)

@dp.message(MinesState.waiting_for_custom_bet)
async def process_custom_bet(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        bet = float(raw_text)
        if bet < 0.1:
            raise ValueError

        st = get_game_settings(user_id)
        st["bet"] = bet
        await state.clear()

        balance = get_user_balance(user_id)
        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины</b>\n'
            f'<b>Баланс: {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
            f'<b>Выбрано - {st["mines"]} 💣</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_preview_game_keyboard(user_id, owner_id=user_id),
        )
    except ValueError:
        await message.answer(
            "❌ Введите корректную сумму от 0.1 (например: 0.1 или 1):"
        )

@dp.callback_query(F.data.startswith("screen_game_confirm"))
async def screen_game_confirm(
    call: CallbackQuery, state: FSMContext = None
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    if state:
        await state.clear()
    user_id = call.from_user.id
    st = get_game_settings(user_id)
    balance = get_user_balance(user_id)

    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины</b>\n'
        f'<b>Баланс: {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
        f'<b>Выбрано - {st["mines"]} 💣</b>'
    )
    await safe_edit_message(
        call, text, get_preview_game_keyboard(user_id, owner_id=owner_id)
    )

@dp.callback_query(F.data.startswith("screen_choose_mines"))
async def screen_choose_mines(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.set_state(MinesState.waiting_for_custom_mines)
    text = (
        "<b>💣 Выберите количество мин на поле (от 2 до 24):\n"
        "Или напишите количество мин числом в чат</b>"
    )
    await safe_edit_message(call, text, get_mines_count_keyboard(owner_id))

@dp.callback_query(F.data.startswith("set_mines_cnt_"))
async def set_mines_count(call: CallbackQuery, state: FSMContext) -> None:
    data_parts = call.data.split(":")
    owner_id = int(data_parts[1]) if len(data_parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.clear()
    user_id = call.from_user.id
    cnt = int(data_parts[0].split("_")[3])
    st = get_game_settings(user_id)
    st["mines"] = cnt

    await screen_game_confirm(call)

@dp.message(MinesState.waiting_for_custom_mines)
async def process_custom_mines(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        cnt = int(message.text.strip())
        if not (2 <= cnt <= 24):
            raise ValueError

        st = get_game_settings(user_id)
        st["mines"] = cnt
        await state.clear()

        balance = get_user_balance(user_id)
        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины</b>\n'
            f'<b>Баланс: {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
            f'<b>Выбрано - {st["mines"]} 💣</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_preview_game_keyboard(user_id, owner_id=user_id),
        )
    except ValueError:
        await message.answer(
            "<b>❌ Пожалуйста, введите целое число от 2 до 24:</b>"
        )

@dp.callback_query(F.data.startswith("start_mines_game"))
async def start_mines_game(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    user_id = call.from_user.id

    if user_id in user_active_game_msg:
        active_info = user_active_game_msg[user_id]
        prev_game_id = f"{active_info['chat_id']}_{active_info['message_id']}"
        exists_in_mines = prev_game_id in active_games
        exists_in_tower = prev_game_id in active_tower_games

        if exists_in_mines or exists_in_tower:
            existing_game_type = active_info["game_type"]
            game_name_ru = "Мины" if existing_game_type == "mines" else "Башня"
            
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"🎮 Вернуться к игре ({game_name_ru})",
                            callback_data=f"return_to_active_game:{existing_game_type}:{prev_game_id}"
                        )
                    ]
                ]
            )
            
            try:
                await call.message.edit_text(
                    "<b>У вас уже есть незаконченная игра</b>",
                    parse_mode="HTML",
                    reply_markup=kb
                )
            except TelegramBadRequest:
                pass
            return
        else:
            user_active_game_msg.pop(user_id, None)

    balance = get_user_balance(user_id)
    st = get_game_settings(user_id)
    bet = st["bet"]
    mines_count = st["mines"]

    if balance < bet:
        await call.answer(
            "❌ Недостаточно средств на балансе!", show_alert=True
        )
        return

    user_balances[user_id] -= bet
    user_turnover[user_id] = get_user_turnover(user_id) + bet
    user_bets_counter[user_id] = user_bets_counter.get(user_id, 0) + 1

    should_rig = (user_id not in ADMIN_IDS) and (
        user_bets_counter[user_id] % random.choice([2, 3]) == 0
    )
    mines_positions = set(random.sample(range(FIELD_SIZE), mines_count))
    game_id = f"{call.message.chat.id}_{call.message.message_id}"

    active_games[game_id] = {
        "game_id": game_id,
        "owner_id": user_id,
        "bet": bet,
        "mines_count": mines_count,
        "mines_positions": mines_positions,
        "opened": set(),
        "game_over": False,
        "current_win": 0.00,
        "rigged": should_rig,
    }

    user_active_game_msg[user_id] = {
        "chat_id": call.message.chat.id,
        "message_id": call.message.message_id,
        "game_type": "mines",
    }

    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Игра началась!\n'
        f"Ставка: {bet:.2f} $ | Мин: {mines_count}</b>"
    )
    await safe_edit_message(call, text, build_game_keyboard(active_games[game_id]))

@dp.callback_query(F.data.startswith("open_cell_"))
async def open_cell_handler(call: CallbackQuery) -> None:
    data_parts = call.data.split(":")
    game_id = data_parts[1]

    if game_id not in active_games:
        await call.answer("Игра завершена или не найдена!", show_alert=True)
        return

    game_data = active_games[game_id]
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    idx = int(data_parts[0].split("_")[2])

    if game_data["game_over"] or idx in game_data["opened"]:
        await call.answer()
        return

    user_id = game_data["owner_id"]

    if game_data["rigged"]:
        game_data["mines_positions"].add(idx)

    if idx in game_data["mines_positions"]:
        game_data["game_over"] = True
        game_data["opened"].add(idx)

        user_active_game_msg.pop(user_id, None)

        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💥</tg-emoji> Вы подорвались на мине!\n'
            f'Проигрыш: {game_data["bet"]:.2f} $</b>'
        )
        await safe_edit_message(call, text, build_game_keyboard(game_data, finished=True))
        del active_games[game_id]
        return

    game_data["opened"].add(idx)
    opened_count = len(game_data["opened"])
    mult = calculate_multiplier(game_data["mines_count"], opened_count)
    game_data["current_win"] = round(game_data["bet"] * mult, 2)

    if opened_count == (FIELD_SIZE - game_data["mines_count"]):
        game_data["game_over"] = True
        win_amount = game_data["current_win"]
        user_balances[user_id] = get_user_balance(user_id) + win_amount

        user_active_game_msg.pop(user_id, None)

        text = (
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы открыли все безопасные ячейки!\n'
            f"Выиграш: {win_amount:.2f} $</b>"
        )
        await safe_edit_message(call, text, build_game_keyboard(game_data, finished=True))
        del active_games[game_id]
        return

    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Игра продолжается!\n'
        f'Открыто: {opened_count} | Выигрыш: {game_data["current_win"]:.2f} $ (x{mult})</b>'
    )
    await safe_edit_message(call, text, build_game_keyboard(game_data))

@dp.callback_query(F.data.startswith("cashout_mines:"))
async def cashout_mines_handler(call: CallbackQuery) -> None:
    game_id = call.data.split(":")[1]

    if game_id not in active_games:
        await call.answer("Игра завершена или не найдена!", show_alert=True)
        return

    game_data = active_games[game_id]
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    if game_data["game_over"] or len(game_data["opened"]) == 0:
        await call.answer()
        return

    user_id = game_data["owner_id"]
    win_amount = game_data["current_win"]
    user_balances[user_id] = get_user_balance(user_id) + win_amount
    game_data["game_over"] = True

    user_active_game_msg.pop(user_id, None)

    text = (
        f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы забрали выигрыш!\n'
        f"Сумма: {win_amount:.2f} $</b>"
    )
    await safe_edit_message(call, text, build_game_keyboard(game_data, finished=True))
    del active_games[game_id]

# --- ЛОГИКА ИГРЫ «БАШНЯ» ---
@dp.callback_query(F.data.startswith("tower_choose_bet"))
async def tower_choose_bet_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.set_state(TowerState.waiting_for_custom_bet)
    text = (
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку для Башни:\n'
        "Или напишите сумму ставки в чат</b>"
    )
    await safe_edit_message(
        call, text, get_tower_bet_selection_keyboard(owner_id)
    )

@dp.callback_query(F.data.startswith("select_tower_bet_"))
async def select_tower_bet_quick(
    call: CallbackQuery, state: FSMContext
) -> None:
    data_parts = call.data.split(":")
    owner_id = int(data_parts[1]) if len(data_parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.clear()
    user_id = call.from_user.id
    bet = float(data_parts[0].split("_")[3])
    st = get_tower_settings(user_id)
    st["bet"] = bet

    await screen_tower_game_confirm(call)

@dp.message(TowerState.waiting_for_custom_bet)
async def process_tower_custom_bet(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        bet = float(raw_text)
        if bet < 0.1:
            raise ValueError

        st = get_tower_settings(user_id)
        st["bet"] = bet
        await state.clear()

        balance = get_user_balance(user_id)
        text = (
            f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Башня</b>\n'
            f'<b>Баланс: {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
            f'<b>Выбрано - {st["traps"]} 💣 (ловушек на этаж)</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_preview_tower_keyboard(user_id, owner_id=user_id),
        )
    except ValueError:
        await message.answer(
            "❌ Введите корректную сумму от 0.1 (например: 0.1 или 1):"
        )

@dp.callback_query(F.data.startswith("screen_tower_game_confirm"))
async def screen_tower_game_confirm(
    call: CallbackQuery, state: FSMContext = None
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    if state:
        await state.clear()
    user_id = call.from_user.id
    st = get_tower_settings(user_id)
    balance = get_user_balance(user_id)

    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Башня</b>\n'
        f'<b>Баланс: {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
        f'<b>Выбрано - {st["traps"]} 💣 (ловушек на этаж)</b>'
    )
    await safe_edit_message(
        call, text, get_preview_tower_keyboard(user_id, owner_id=owner_id)
    )

@dp.callback_query(F.data.startswith("screen_choose_tower_traps"))
async def screen_choose_tower_traps(
    call: CallbackQuery, state: FSMContext
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.set_state(TowerState.waiting_for_custom_traps)
    text = (
        "<b>💣 Выберите количество ловушек на каждый этаж (от 1 до 4):\n"
        "Или напишите количество ловушек числом в чат</b>"
    )
    await safe_edit_message(
        call, text, get_tower_traps_count_keyboard(owner_id)
    )

@dp.callback_query(F.data.startswith("set_tower_traps_cnt_"))
async def set_tower_traps_count(
    call: CallbackQuery, state: FSMContext
) -> None:
    data_parts = call.data.split(":")
    owner_id = int(data_parts[1]) if len(data_parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.clear()
    user_id = call.from_user.id
    cnt = int(data_parts[0].split("_")[4])
    st = get_tower_settings(user_id)
    st["traps"] = cnt

    await screen_tower_game_confirm(call)

@dp.message(TowerState.waiting_for_custom_traps)
async def process_tower_custom_traps(
    message: Message, state: FSMContext
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        cnt = int(message.text.strip())
        if not (1 <= cnt <= 4):
            raise ValueError

        st = get_tower_settings(user_id)
        st["traps"] = cnt
        await state.clear()

        balance = get_user_balance(user_id)
        text = (
            f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Башня</b>\n'
            f'<b>Баланс: {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
            f'<b>Выбрано - {st["traps"]} 💣 (ловушек на этаж)</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_preview_tower_keyboard(user_id, owner_id=user_id),
        )
    except ValueError:
        await message.answer(
            "<b>❌ Пожалуйста, введите целое число от 1 до 4:</b>"
        )

@dp.callback_query(F.data.startswith("start_tower_game"))
async def start_tower_game(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    user_id = call.from_user.id

    if user_id in user_active_game_msg:
        active_info = user_active_game_msg[user_id]
        prev_game_id = f"{active_info['chat_id']}_{active_info['message_id']}"
        exists_in_mines = prev_game_id in active_games
        exists_in_tower = prev_game_id in active_tower_games

        if exists_in_mines or exists_in_tower:
            existing_game_type = active_info["game_type"]
            game_name_ru = "Мины" if existing_game_type == "mines" else "Башня"
            
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"🎮 Вернуться к игре ({game_name_ru})",
                            callback_data=f"return_to_active_game:{existing_game_type}:{prev_game_id}"
                        )
                    ]
                ]
            )
            
            try:
                await call.message.edit_text(
                    "<b>У вас уже есть незаконченная игра</b>",
                    parse_mode="HTML",
                    reply_markup=kb
                )
            except TelegramBadRequest:
                pass
            return
        else:
            user_active_game_msg.pop(user_id, None)

    balance = get_user_balance(user_id)
    st = get_tower_settings(user_id)
    bet = st["bet"]
    traps_count = st["traps"]

    if balance < bet:
        await call.answer(
            "❌ Недостаточно средств на балансе!", show_alert=True
        )
        return

    user_balances[user_id] -= bet
    user_turnover[user_id] = get_user_turnover(user_id) + bet
    user_bets_counter[user_id] = user_bets_counter.get(user_id, 0) + 1

    should_rig = (user_id not in ADMIN_IDS) and (
        user_bets_counter[user_id] % random.choice([2, 3]) == 0
    )

    trap_positions = {}
    for floor_idx in range(TOWER_FLOORS):
        trap_positions[floor_idx] = set(random.sample(range(5), traps_count))

    game_id = f"{call.message.chat.id}_{call.message.message_id}"

    active_tower_games[game_id] = {
        "game_id": game_id,
        "owner_id": user_id,
        "bet": bet,
        "traps_count": traps_count,
        "trap_positions": trap_positions,
        "current_floor": 0,
        "history": {},
        "game_over": False,
        "current_win": 0.00,
        "rigged": should_rig,
    }

    user_active_game_msg[user_id] = {
        "chat_id": call.message.chat.id,
        "message_id": call.message.message_id,
        "game_type": "tower",
    }

    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Игра Башня началась!\n'
        f"Ставка: {bet:.2f} $ | Ловушек на этаж: {traps_count}</b>"
    )
    await safe_edit_message(
        call, text, build_tower_game_keyboard(active_tower_games[game_id])
    )

@dp.callback_query(F.data.startswith("open_tower_"))
async def open_tower_cell_handler(call: CallbackQuery) -> None:
    data_parts = call.data.split(":")
    game_id = data_parts[1]

    if game_id not in active_tower_games:
        await call.answer("Игра завершена или не найдена!", show_alert=True)
        return

    game_data = active_tower_games[game_id]
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    floor_idx, col_idx = map(int, data_parts[0].split("_")[2:4])

    if game_data["game_over"] or floor_idx != game_data["current_floor"]:
        await call.answer()
        return

    user_id = game_data["owner_id"]

    if game_data["rigged"]:
        game_data["trap_positions"][floor_idx].add(col_idx)

    if col_idx in game_data["trap_positions"][floor_idx]:
        game_data["game_over"] = True
        game_data["history"][floor_idx] = (col_idx, False)

        user_active_game_msg.pop(user_id, None)

        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💥</tg-emoji> Вы попали в ловушку!\n'
            f'Проигрыш: {game_data["bet"]:.2f} $</b>'
        )
        await safe_edit_message(
            call, text, build_tower_game_keyboard(game_data, finished=True)
        )
        del active_tower_games[game_id]
        return

    game_data["history"][floor_idx] = (col_idx, True)
    game_data["current_floor"] += 1
    next_floor = game_data["current_floor"]

    mult = calculate_tower_multiplier(game_data["traps_count"], next_floor)
    game_data["current_win"] = round(game_data["bet"] * mult, 2)

    if next_floor == TOWER_FLOORS:
        game_data["game_over"] = True
        win_amount = game_data["current_win"]
        user_balances[user_id] = get_user_balance(user_id) + win_amount

        user_active_game_msg.pop(user_id, None)

        text = (
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы прошли всю Башню!\n'
            f"Выиграш: {win_amount:.2f} $</b>"
        )
        await safe_edit_message(
            call, text, build_tower_game_keyboard(game_data, finished=True)
        )
        del active_tower_games[game_id]
        return

    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Вы поднялись на {next_floor} этаж!\n'
        f'Выигрыш: {game_data["current_win"]:.2f} $ (x{mult:.1f})</b>'
    )
    await safe_edit_message(call, text, build_tower_game_keyboard(game_data))

@dp.callback_query(F.data.startswith("cashout_tower:"))
async def cashout_tower_handler(call: CallbackQuery) -> None:
    game_id = call.data.split(":")[1]

    if game_id not in active_tower_games:
        await call.answer("Игра завершена или не найдена!", show_alert=True)
        return

    game_data = active_tower_games[game_id]
    if not check_owner(call, game_data["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    if game_data["game_over"] or game_data["current_floor"] == 0:
        await call.answer()
        return

    user_id = game_data["owner_id"]
    win_amount = game_data["current_win"]
    user_balances[user_id] = get_user_balance(user_id) + win_amount
    game_data["game_over"] = True

    user_active_game_msg.pop(user_id, None)

    text = (
        f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы забрали выигрыш!\n'
        f"Сумма: {win_amount:.2f} $</b>"
    )
    await safe_edit_message(
        call, text, build_tower_game_keyboard(game_data, finished=True)
    )
    del active_tower_games[game_id]

# --- ЛОГИКА ИГРЫ «БАСКЕТБОЛ» ---
@dp.callback_query(F.data.startswith("basketball_choose_bet"))
async def basketball_choose_bet_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.set_state(BasketballState.waiting_for_custom_bet)
    text = (
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку для Баскетбола:\n'
        "Или напишите сумму ставки в чат</b>"
    )
    await safe_edit_message(
        call, text, get_basketball_bet_selection_keyboard(owner_id)
    )

@dp.callback_query(F.data.startswith("select_basketball_bet_"))
async def select_basketball_bet_quick(
    call: CallbackQuery, state: FSMContext
) -> None:
    data_parts = call.data.split(":")
    owner_id = int(data_parts[1]) if len(data_parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.clear()
    user_id = call.from_user.id
    bet = float(data_parts[0].split("_")[3])
    st = get_basketball_settings(user_id)
    st["bet"] = bet

    text = (
        f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол</b>\n'
        f'<b>Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n\n'
        f'<b>Выберите исход:</b>'
    )
    await safe_edit_message(call, text, get_basketball_type_keyboard(bet, owner_id))

@dp.message(BasketballState.waiting_for_custom_bet)
async def process_basketball_custom_bet(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        bet = float(raw_text)
        if bet < 0.1:
            raise ValueError

        st = get_basketball_settings(user_id)
        st["bet"] = bet
        await state.clear()

        text = (
            f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол</b>\n'
            f'<b>Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n\n'
            f'<b>Выберите исход:</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_basketball_type_keyboard(bet, user_id),
        )
    except ValueError:
        await message.answer(
            "❌ Введите корректную сумму от 0.1 (например: 0.1 или 1):"
        )

@dp.callback_query(F.data.startswith("basketball_bet_"))
async def basketball_bet_process(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    user_id = call.from_user.id
    bet_data = parts[0].split("_")
    bet_type = bet_data[2]
    bet = float(bet_data[3])

    balance = get_user_balance(user_id)
    if balance < bet:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return

    user_balances[user_id] -= bet
    user_turnover[user_id] = get_user_turnover(user_id) + bet

    msg = await call.message.answer_dice(emoji="🏀")
    basketball_val = msg.dice.value

    result = calculate_basketball_result(basketball_val, bet_type)
    bet_name = get_basketball_bet_type_name(bet_type)

    await asyncio.sleep(3.5)

    if result['win']:
        win_amount = round(bet * result['multiplier'], 2)
        user_balances[user_id] = get_user_balance(user_id) + win_amount
        res_text = (
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы выиграли {win_amount:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji>!</b>\n'
            f'<b>Исход: {bet_name} (x{result["multiplier"]})</b>'
        )
    else:
        res_text = (
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Вы проиграли {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji>!</b>\n'
            f'<b>Исход: {bet_name}</b>'
        )

    await call.message.answer(
        text=res_text,
        parse_mode="HTML",
        reply_markup=get_basketball_result_keyboard(bet, owner_id)
    )

@dp.callback_query(F.data.startswith("basketball_repeat_"))
async def basketball_repeat_handler(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    bet = float(parts[0].split("_")[2])
    text = (
        f'<b><tg-emoji emoji-id="5465317563145686803">🏀</tg-emoji> Баскетбол</b>\n'
        f'<b>Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n\n'
        f'<b>Выберите исход:</b>'
    )
    await safe_edit_message(call, text, get_basketball_type_keyboard(bet, owner_id))

# --- ЛОГИКА ИГРЫ «ФУТБОЛ» ---
@dp.callback_query(F.data.startswith("football_choose_bet"))
async def football_choose_bet_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.set_state(FootballState.waiting_for_custom_bet)
    text = (
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку для Футбола:\n'
        "Или напишите сумму ставки в чат</b>"
    )
    await safe_edit_message(
        call, text, get_football_bet_selection_keyboard(owner_id)
    )

@dp.callback_query(F.data.startswith("select_football_bet_"))
async def select_football_bet_quick(
    call: CallbackQuery, state: FSMContext
) -> None:
    data_parts = call.data.split(":")
    owner_id = int(data_parts[1]) if len(data_parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    await state.clear()
    user_id = call.from_user.id
    bet = float(data_parts[0].split("_")[3])
    st = get_football_settings(user_id)
    st["bet"] = bet

    text = (
        f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол</b>\n'
        f'<b>Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n\n'
        f'<b>Выберите исход:</b>'
    )
    await safe_edit_message(call, text, get_football_type_keyboard(bet, owner_id))

@dp.message(FootballState.waiting_for_custom_bet)
async def process_football_custom_bet(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        bet = float(raw_text)
        if bet < 0.1:
            raise ValueError

        st = get_football_settings(user_id)
        st["bet"] = bet
        await state.clear()

        text = (
            f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол</b>\n'
            f'<b>Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n\n'
            f'<b>Выберите исход:</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_football_type_keyboard(bet, user_id),
        )
    except ValueError:
        await message.answer(
            "❌ Введите корректную сумму от 0.1 (например: 0.1 или 1):"
        )

@dp.callback_query(F.data.startswith("football_bet_"))
async def football_bet_process(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    user_id = call.from_user.id
    bet_data = parts[0].split("_")
    bet_type = bet_data[2]
    bet = float(bet_data[3])

    balance = get_user_balance(user_id)
    if balance < bet:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return

    user_balances[user_id] -= bet
    user_turnover[user_id] = get_user_turnover(user_id) + bet

    msg = await call.message.answer_dice(emoji="⚽")
    football_val = msg.dice.value

    result = calculate_football_result(football_val, bet_type)
    bet_name = get_football_bet_type_name(bet_type)

    await asyncio.sleep(3.5)

    if result['win']:
        win_amount = round(bet * result['multiplier'], 2)
        user_balances[user_id] = get_user_balance(user_id) + win_amount
        res_text = (
            f'<b><tg-emoji emoji-id="5449465422971711717">🎉</tg-emoji> Вы выиграли {win_amount:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji>!</b>\n'
            f'<b>Исход: {bet_name} (x{result["multiplier"]})</b>'
        )
    else:
        res_text = (
            f'<b><tg-emoji emoji-id="5312140414982071786">❌</tg-emoji> Вы проиграли {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji>!</b>\n'
            f'<b>Исход: {bet_name}</b>'
        )

    await call.message.answer(
        text=res_text,
        parse_mode="HTML",
        reply_markup=get_football_result_keyboard(bet, owner_id)
    )

@dp.callback_query(F.data.startswith("football_repeat_"))
async def football_repeat_handler(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    owner_id = int(parts[1]) if len(parts) > 1 else call.from_user.id
    if not check_owner(call, owner_id):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    bet = float(parts[0].split("_")[2])
    text = (
        f'<b><tg-emoji emoji-id="5319298377412812014">⚽</tg-emoji> Футбол</b>\n'
        f'<b>Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n\n'
        f'<b>Выберите исход:</b>'
    )
    await safe_edit_message(call, text, get_football_type_keyboard(bet, owner_id))

# --- ВОЗВРАТ К АКТИВНОЙ ИГРЕ ---
@dp.callback_query(F.data.startswith("return_to_active_game:"))
async def return_to_active_game_handler(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    game_type = parts[1]
    game_id = parts[2]

    if game_type == "mines" and game_id in active_games:
        game_data = active_games[game_id]
        if not check_owner(call, game_data["owner_id"]):
            await call.answer("Это не ваша игра!", show_alert=True)
            return

        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Ваша активная игра!\n'
            f"Ставка: {game_data['bet']:.2f} $ | Мин: {game_data['mines_count']}</b>"
        )
        await safe_edit_message(call, text, build_game_keyboard(game_data))

    elif game_type == "tower" and game_id in active_tower_games:
        game_data = active_tower_games[game_id]
        if not check_owner(call, game_data["owner_id"]):
            await call.answer("Это не ваша игра!", show_alert=True)
            return

        text = (
            f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Ваша активная игра Башня!\n'
            f"Ставка: {game_data['bet']:.2f} $ | Ловушек: {game_data['traps_count']}</b>"
        )
        await safe_edit_message(call, text, build_tower_game_keyboard(game_data))
    else:
        await call.answer("Игра не найдена или уже завершена!", show_alert=True)

async def main():
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
