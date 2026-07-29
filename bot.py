import asyncio
import random
import string
from aiogram import Bot, Dispatcher, F, html
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

TOKEN = "8740242990:AAF2I7c7x_SD6-Dww3WQJKQYbk3WsXYP5BI"

dp = Dispatcher()

ADMIN_IDS = {7921743592}

user_balances = {}
user_turnover = {}
active_games = {}
game_settings = {}
active_tower_games = {}
tower_game_settings = {}
user_bets_counter = {}

# Хранилище чеков: check_id -> dict
created_cheks = {}


class MinesState(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_custom_mines = State()


class TowerState(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_custom_traps = State()


class ChekState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_activations = State()
    waiting_for_password = State()


FIELD_SIZE = 25


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
                text="Меню", icon_custom_emoji_id="5469969339144773395"
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
            )
        ],
        [
            InlineKeyboardButton(
                text="Башня",
                icon_custom_emoji_id="5449397725697187601",
                callback_data="tower_choose_bet",
            )
        ],
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
    has_pass = "Да" if chek.get("password") else "Нет"
    only_premium = "Да" if chek.get("only_premium") else "Нет"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Поделиться",
                    switch_inline_query=f"check_{chek_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Установить ограничения",
                    callback_data=f"chek_limits_menu:{chek_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить чек",
                    callback_data=f"chek_delete:{chek_id}",
                )
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
    pass_text = (
        "🔐 Изменить пароль"
        if chek.get("password")
        else "🔑 Поставить пароль"
    )
    prem_text = (
        "⭐ Для всех игроков"
        if chek.get("only_premium")
        else "⭐ Только для TG Premium"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=pass_text, callback_data=f"chek_set_pass:{chek_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=prem_text,
                    callback_data=f"chek_toggle_premium:{chek_id}",
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
    mult = base**opened_count
    return max(round(mult, 2), 1.01)


def build_profile_text(user_id: int, full_name: str) -> str:
    balance = get_user_balance(user_id)
    turnover = get_user_turnover(user_id)
    return (
        f'<b><tg-emoji emoji-id="5308004189677330658">👤</tg-emoji> {html.quote(full_name)}</b>\n'
        f'<b><tg-emoji emoji-id="5449624985301717991">💳</tg-emoji> Ваш ID : {user_id}</b>\n'
        f'<b><tg-emoji emoji-id="5310262449121827356">💰</tg-emoji> Баланс: {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
        f'<b><tg-emoji emoji-id="5452042536493288421">📊</tg-emoji> Оборот : {turnover:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
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
        # Иксы сжаты чуть меньше
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


# --- РАЗДЕЛ ЧЕКИ ---


@dp.callback_query(F.data == "open_cheks_menu")
async def open_cheks_menu_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = (
        '<b><tg-emoji emoji-id="5307773751796996779">🎟</tg-emoji> '
        'Создайте чек для мгновенной отправки средств пользователю или группе пользователей - '
        'просто укажите количество активаций!</b>'
    )
    await safe_edit_message(call, text, get_cheks_main_keyboard())


@dp.callback_query(F.data == "chek_create_start")
async def chek_create_start_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    if balance <= 0:
        await call.answer(
            "❌ У вас недостаточный баланс для создания чека!", show_alert=True
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

    await state.update_data(chek_amount=amount)
    await state.set_state(ChekState.waiting_for_activations)

    max_acts = int(balance // amount)
    text = (
        f"<b><tg-emoji emoji-id=\"5307773751796996779\">🎟</tg-emoji> Введите количество активаций чека:\n\n"
        f"Сумма 1 активации: {amount:.2f} $\n"
        f"Максимально доступно активаций: {max_acts}</b>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data="chek_create_start"
                )
            ]
        ]
    )
    await safe_edit_message(call, text, kb)


@dp.message(ChekState.waiting_for_amount)
async def process_chek_amount_input(
    message: Message, state: FSMContext
) -> None:
    user_id = message.from_user.id
    balance = get_user_balance(user_id)

    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        amount = float(raw_text)
        if amount <= 0 or amount > balance:
            raise ValueError

        await state.update_data(chek_amount=amount)
        await state.set_state(ChekState.waiting_for_activations)

        max_acts = int(balance // amount)
        text = (
            f"<b><tg-emoji emoji-id=\"5307773751796996779\">🎟</tg-emoji> Введите количество активаций чека:\n\n"
            f"Сумма 1 активации: {amount:.2f} $\n"
            f"Максимально доступно активаций: {max_acts}</b>"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀ Назад", callback_data="chek_create_start"
                    )
                ]
            ]
        )
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
    except ValueError:
        await message.answer(
            f"❌ Некорректная сумма! Введите число от 0.01 до {balance:.2f}:"
        )


@dp.message(ChekState.waiting_for_activations)
async def process_chek_activations_input(
    message: Message, state: FSMContext
) -> None:
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    data = await state.get_data()
    amount = data.get("chek_amount", 0.1)

    try:
        activations = int(message.text.strip())
        total_cost = amount * activations

        if activations <= 0 or total_cost > balance:
            raise ValueError

        user_balances[user_id] -= total_cost

        chek_id = generate_check_code()
        created_cheks[chek_id] = {
            "id": chek_id,
            "owner_id": user_id,
            "amount": amount,
            "activations": activations,
            "rem_activations": activations,
            "password": None,
            "only_premium": False,
        }

        await state.clear()

        if activations == 1:
            title_str = f"Чек на {amount:.2f}$"
        else:
            title_str = f"Чек на {amount:.2f}$ на {activations} активаций"

        text = (
            f"<b>🎉 {title_str} успешно создан!\n\n"
            f"Код чека: <code>{chek_id}</code></b>"
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_chek_manage_keyboard(chek_id),
        )
    except ValueError:
        await message.answer(
            "❌ Некорректное количество активаций или недостаточно средств!"
        )


@dp.callback_query(F.data.startswith("chek_manage:"))
async def chek_manage_handler(call: CallbackQuery) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if not chek:
        await call.answer("Чек не найден!", show_alert=True)
        return

    amount = chek["amount"]
    activations = chek["activations"]
    if activations == 1:
        title_str = f"Чек на {amount:.2f}$"
    else:
        title_str = f"Чек на {amount:.2f}$ на {activations} активаций"

    text = (
        f"<b>⚙️ Управление: {title_str}\n\n"
        f"Код чека: <code>{chek_id}</code>\n"
        f"Осталось активаций: {chek['rem_activations']}/{activations}</b>"
    )
    await safe_edit_message(call, text, get_chek_manage_keyboard(chek_id))


@dp.callback_query(F.data.startswith("chek_limits_menu:"))
async def chek_limits_menu_handler(call: CallbackQuery) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if not chek:
        await call.answer("Чек не найден!", show_alert=True)
        return

    has_pass = chek["password"] if chek["password"] else "Не установлен"
    only_prem = "Да" if chek["only_premium"] else "Нет"

    text = (
        f"<b>⚙️ Настройка ограничений чека <code>{chek_id}</code>:\n\n"
        f"• Пароль: {has_pass}\n"
        f"• Только Telegram Premium: {only_prem}</b>"
    )
    await safe_edit_message(call, text, get_chek_limits_keyboard(chek_id))


@dp.callback_query(F.data.startswith("chek_set_pass:"))
async def chek_set_pass_start(call: CallbackQuery, state: FSMContext) -> None:
    chek_id = call.data.split(":")[1]
    await state.update_data(target_chek_id=chek_id)
    await state.set_state(ChekState.waiting_for_password)

    text = "<b>🔑 Введите пароль для чека в чат:</b>"
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


@dp.message(ChekState.waiting_for_password)
async def chek_set_pass_process(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    chek_id = data.get("target_chek_id")
    chek = created_cheks.get(chek_id)

    if chek:
        pwd = message.text.strip()
        chek["password"] = pwd
        await state.clear()

        text = f"<b>✅ Пароль «{pwd}» успешно установлен на чек!</b>"
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_chek_limits_keyboard(chek_id),
        )


@dp.callback_query(F.data.startswith("chek_toggle_premium:"))
async def chek_toggle_premium_handler(call: CallbackQuery) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if chek:
        chek["only_premium"] = not chek["only_premium"]
        await chek_limits_menu_handler(call)


@dp.callback_query(F.data.startswith("chek_delete:"))
async def chek_delete_handler(call: CallbackQuery) -> None:
    chek_id = call.data.split(":")[1]
    chek = created_cheks.get(chek_id)

    if chek:
        # Возврат средств за неиспользованные активации
        rem_money = chek["amount"] * chek["rem_activations"]
        user_balances[chek["owner_id"]] = (
            get_user_balance(chek["owner_id"]) + rem_money
        )

        del created_cheks[chek_id]
        await call.answer(
            "🗑 Чек успешно удален, средства возвращены на баланс!",
            show_alert=True,
        )
        await open_cheks_menu_handler(call, None)


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
            call, "<b>🎟 У вас нет активных чеков!</b>", kb
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
        "<b>📋 Ваши активные чеки:</b>",
        InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


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
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    get_user_balance(user_id)
    get_user_turnover(user_id)

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
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки !\n\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
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
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки !\n\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
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
        if bet <= 0:
            raise ValueError

        st = get_game_settings(user_id)
        st["bet"] = bet
        await state.clear()

        balance = get_user_balance(user_id)
        text = (
            f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины</b>\n'
            f'<b>Баланс : {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
            f'<b>Выбрано - {st["mines"]} 💣</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_preview_game_keyboard(user_id, owner_id=user_id),
        )
    except ValueError:
        await message.answer(
            "❌ Введите корректную сумму (например: 0.4 или 1):"
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
        f'<b>Баланс : {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
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
            f'<b>Баланс : {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
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

    text = (
        f"<b>💣 Игра началась!\n\n"
        f"Игрок: {html.quote(call.from_user.full_name)}\n"
        f'Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji> | Мин: {mines_count}\n'
        f"Выберите клетку:</b>"
    )

    await safe_edit_message(
        call, text, build_game_keyboard(active_games[game_id])
    )


@dp.callback_query(F.data.startswith("open_cell_"))
async def open_cell_handler(call: CallbackQuery) -> None:
    data_parts = call.data.split(":")
    game_id = data_parts[1] if len(data_parts) > 1 else call.from_user.id

    if game_id not in active_games:
        await call.answer("Игра завершена.", show_alert=True)
        return

    game = active_games[game_id]
    if not check_owner(call, game["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    if game["game_over"]:
        await call.answer("Игра завершена.", show_alert=True)
        return

    cell_idx = int(data_parts[0].split("_")[2])

    if cell_idx in game["opened"]:
        await call.answer()
        return

    if game.get("rigged") and len(game["opened"]) == 0:
        if cell_idx not in game["mines_positions"]:
            game["mines_positions"].pop()
            game["mines_positions"].add(cell_idx)

    game["opened"].add(cell_idx)

    if cell_idx in game["mines_positions"]:
        game["game_over"] = True
        text = (
            f"<b>💥 Вы подорвались на мине!\n\n"
            f'Ваша ставка {game["bet"]:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji> сгорела.</b>'
        )
        await safe_edit_message(
            call, text, build_game_keyboard(game, finished=True)
        )
        del active_games[game_id]
        return

    opened_count = len(game["opened"])
    mult = calculate_multiplier(game["mines_count"], opened_count)
    current_win = game["bet"] * mult
    game["current_win"] = current_win

    if opened_count == (FIELD_SIZE - game["mines_count"]):
        game["game_over"] = True
        user_id = game["owner_id"]
        user_balances[user_id] = get_user_balance(user_id) + current_win
        text = (
            f"<b>🎉 Поздравляем! Вы открыли все безопасные клетки!\n\n"
            f'Ваш выигрыш: {current_win:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
        )
        await safe_edit_message(
            call, text, build_game_keyboard(game, finished=True)
        )
        del active_games[game_id]
        return

    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины\n\n'
        f"Множитель: x{mult:.2f}\n"
        f'Текущий выигрыш: {current_win:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, build_game_keyboard(game))


@dp.callback_query(F.data.startswith("cashout_mines"))
async def cashout_mines_handler(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    game_id = parts[1] if len(parts) > 1 else call.from_user.id

    if game_id not in active_games or active_games[game_id]["game_over"]:
        await call.answer("Игра не найдена.", show_alert=True)
        return

    game = active_games[game_id]
    if not check_owner(call, game["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    win_amount = game["current_win"]
    game["game_over"] = True
    user_id = game["owner_id"]

    user_balances[user_id] = get_user_balance(user_id) + win_amount

    text = (
        f"<b>💰 Вы успешно забрали выигрыш!\n\n"
        f'Сумма: {win_amount:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji>\n'
        f'Ваш баланс: {user_balances[user_id]:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )

    await safe_edit_message(
        call, text, build_game_keyboard(game, finished=True)
    )
    del active_games[game_id]


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
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку:\n'
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
async def process_custom_tower_bet(
    message: Message, state: FSMContext
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        raw_text = message.text.replace("$", "").replace(",", ".").strip()
        bet = float(raw_text)
        if bet <= 0:
            raise ValueError

        st = get_tower_settings(user_id)
        st["bet"] = bet
        await state.clear()

        balance = get_user_balance(user_id)
        text = (
            f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Башня</b>\n'
            f'<b>Баланс : {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
            f'<b>Выбрано - {st["traps"]} 💣</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_preview_tower_keyboard(user_id, owner_id=user_id),
        )
    except ValueError:
        await message.answer(
            "❌ Введите корректную сумму (например: 0.4 или 1):"
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
        f'<b>Баланс : {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
        f'<b>Выбрано - {st["traps"]} 💣</b>'
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
        "<b>💣 Выберите количество мин на ряд (от 1 до 4):\n"
        "Или напишите количество мин числом в чат</b>"
    )
    await safe_edit_message(
        call, text, get_tower_traps_count_keyboard(owner_id)
    )


@dp.callback_query(F.data.startswith("set_tower_traps_cnt_"))
async def set_tower_traps_count(call: CallbackQuery, state: FSMContext) -> None:
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
async def process_custom_tower_traps(
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
            f'<b>Баланс : {balance:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>\n'
            f'<b>Выбрано - {st["traps"]} 💣</b>'
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
    for floor in range(TOWER_FLOORS):
        trap_positions[floor] = set(random.sample(range(5), traps_count))

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

    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Игра началась!\n\n'
        f"Игрок: {html.quote(call.from_user.full_name)}\n"
        f'Ставка: {bet:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji> | Мин в ряду: {traps_count}\n'
        f"Выберите клетку на 1 этаже (в самом верху):</b>"
    )

    await safe_edit_message(
        call, text, build_tower_game_keyboard(active_tower_games[game_id])
    )


@dp.callback_query(F.data.startswith("open_tower_"))
async def open_tower_cell_handler(call: CallbackQuery) -> None:
    data_parts = call.data.split(":")
    game_id = data_parts[1] if len(data_parts) > 1 else call.from_user.id

    if game_id not in active_tower_games:
        await call.answer("Игра завершена.", show_alert=True)
        return

    game = active_tower_games[game_id]
    if not check_owner(call, game["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    if game["game_over"]:
        await call.answer("Игра завершена.", show_alert=True)
        return

    sub_parts = data_parts[0].split("_")
    floor = int(sub_parts[2])
    col = int(sub_parts[3])

    if floor != game["current_floor"]:
        await call.answer(
            "Открывайте этажи по порядку сверху вниз!", show_alert=True
        )
        return

    if game.get("rigged"):
        if col not in game["trap_positions"][floor]:
            game["trap_positions"][floor].pop()
            game["trap_positions"][floor].add(col)

    traps = game["trap_positions"][floor]

    if col in traps:
        game["game_over"] = True
        game["history"][floor] = (col, False)
        text = (
            f"<b>💥 Вы подорвались на мине!\n\n"
            f'Ваша ставка {game["bet"]:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji> сгорела.</b>'
        )
        await safe_edit_message(
            call, text, build_tower_game_keyboard(game, finished=True)
        )
        del active_tower_games[game_id]
        return

    game["history"][floor] = (col, True)
    game["current_floor"] += 1
    opened_floors = game["current_floor"]

    mult = calculate_tower_multiplier(game["traps_count"], opened_floors)
    current_win = game["bet"] * mult
    game["current_win"] = current_win

    if opened_floors == TOWER_FLOORS:
        game["game_over"] = True
        user_id = game["owner_id"]
        user_balances[user_id] = get_user_balance(user_id) + current_win
        text = (
            f"<b>🎉 Поздравляем! Вы прошли всю башню!\n\n"
            f'Ваш выигрыш: {current_win:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
        )
        await safe_edit_message(
            call, text, build_tower_game_keyboard(game, finished=True)
        )
        del active_tower_games[game_id]
        return

    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Башня\n\n'
        f"Множитель: x{mult:.2f}\n"
        f'Текущий выигрыш: {current_win:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, build_tower_game_keyboard(game))


@dp.callback_query(F.data.startswith("cashout_tower"))
async def cashout_tower_handler(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    game_id = parts[1] if len(parts) > 1 else call.from_user.id

    if (
        game_id not in active_tower_games
        or active_tower_games[game_id]["game_over"]
    ):
        await call.answer("Игра не найдена.", show_alert=True)
        return

    game = active_tower_games[game_id]
    if not check_owner(call, game["owner_id"]):
        await call.answer("Это не ваша игра!", show_alert=True)
        return

    win_amount = game["current_win"]
    game["game_over"] = True
    user_id = game["owner_id"]

    user_balances[user_id] = get_user_balance(user_id) + win_amount

    text = (
        f"<b>💰 Вы успешно забрали выигрыш!\n\n"
        f'Сумма: {win_amount:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji>\n'
        f'Ваш баланс: {user_balances[user_id]:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )

    await safe_edit_message(
        call, text, build_tower_game_keyboard(game, finished=True)
    )
    del active_tower_games[game_id]


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
