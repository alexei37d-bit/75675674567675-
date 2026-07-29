import asyncio
import random
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

# Балансы пользователей (по умолчанию 1.00)
user_balances = {}

# Оборот пользователей (по умолчанию 0.00)
user_turnover = {}

# Активные игры: user_id -> dict
active_games = {}

# Параметры ставок перед игрой: user_id -> dict
game_settings = {}

# Активные игры в Башню: user_id -> dict
active_tower_games = {}

# Параметры ставок для Башни: user_id -> dict
tower_game_settings = {}


class MinesState(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_custom_mines = State()


class TowerState(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_custom_traps = State()


FIELD_SIZE = 25  # Поле 5x5


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


# Главное меню внизу (Reply) - 3 кнопки: Кошелек, Играть, Меню
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

# Инлайн-кнопки внутри Меню (Профиль, Играть, Кошелек)
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
    ]
)

# Кнопки под инлайн-кошельком
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

# Кнопки под инлайн-профилем (Пополнить, Вывести + Назад)
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
        ]
    ]
)


# ЭКРАН 1: Выбор ставки
def get_bet_selection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="0.1$", callback_data="select_bet_0.1"
                ),
                InlineKeyboardButton(
                    text="0.5$", callback_data="select_bet_0.5"
                ),
                InlineKeyboardButton(
                    text="1$", callback_data="select_bet_1.0"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data="back_to_games"
                )
            ],
        ]
    )


# ЭКРАН 2: Поле с лунами 🌑 до начала игры
def get_preview_game_keyboard(user_id: int) -> InlineKeyboardMarkup:
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
                callback_data="start_mines_game",
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"💣 Мин: {mines}", callback_data="screen_choose_mines"
            ),
            InlineKeyboardButton(
                text="◀ Ставка", callback_data="mines_choose_bet"
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ЭКРАН 3: Выбор количества мин
def get_mines_count_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="2", callback_data="set_mines_cnt_2"
                ),
                InlineKeyboardButton(
                    text="3", callback_data="set_mines_cnt_3"
                ),
                InlineKeyboardButton(
                    text="5", callback_data="set_mines_cnt_5"
                ),
                InlineKeyboardButton(
                    text="10", callback_data="set_mines_cnt_10"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="15", callback_data="set_mines_cnt_15"
                ),
                InlineKeyboardButton(
                    text="20", callback_data="set_mines_cnt_20"
                ),
                InlineKeyboardButton(
                    text="24", callback_data="set_mines_cnt_24"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="◀ Назад", callback_data="screen_game_confirm"
                )
            ],
        ]
    )


# Поле во время активной игры (с подарками 🎁)
def build_game_keyboard(
    game_data: dict, finished: bool = False
) -> InlineKeyboardMarkup:
    keyboard = []
    opened = game_data["opened"]
    game_over = game_data["game_over"]
    mines_positions = game_data["mines_positions"]

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
                    text=text, callback_data=f"open_cell_{idx}"
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
                    callback_data="cashout_mines",
                )
            ]
        )

    if finished:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🔄 Сыграть снова", callback_data="screen_game_confirm"
                ),
                InlineKeyboardButton(
                    text="◀ Меню", callback_data="mines_choose_bet"
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


# --- ЛОГИКА ИГРЫ БАШНЯ ---

TOWER_FLOORS = 8

def calculate_tower_multiplier(traps_count: int, floor: int) -> float:
    safe_count = 5 - traps_count
    mult = (5 / safe_count) ** floor
    return max(round(mult, 2), 1.01)

def get_tower_bet_selection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.1$", callback_data="select_tower_bet_0.1"),
                InlineKeyboardButton(text="0.5$", callback_data="select_tower_bet_0.5"),
                InlineKeyboardButton(text="1$", callback_data="select_tower_bet_1.0"),
            ],
            [
                InlineKeyboardButton(text="◀ Назад", callback_data="back_to_games")
            ],
        ]
    )

def get_preview_tower_keyboard(user_id: int) -> InlineKeyboardMarkup:
    st = get_tower_settings(user_id)
    bet = st["bet"]
    traps = st["traps"]

    keyboard = []
    # Сверху вниз (от 0 до 7 этажа)
    for floor_idx in range(TOWER_FLOORS):
        x_mult = calculate_tower_multiplier(traps, floor_idx + 1)
        row = [InlineKeyboardButton(text=f"x{x_mult:.2f}", callback_data="locked_cell")]
        row.extend([InlineKeyboardButton(text="🌑", callback_data="locked_cell") for _ in range(5)])
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"Играть {bet:.2f}",
                icon_custom_emoji_id="5305445793623218874",
                callback_data="start_tower_game",
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"💣 Мин: {traps}", callback_data="screen_choose_tower_traps"
            ),
            InlineKeyboardButton(
                text="◀ Ставка", callback_data="tower_choose_bet"
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_tower_traps_count_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="set_tower_traps_cnt_1"),
                InlineKeyboardButton(text="2", callback_data="set_tower_traps_cnt_2"),
                InlineKeyboardButton(text="3", callback_data="set_tower_traps_cnt_3"),
                InlineKeyboardButton(text="4", callback_data="set_tower_traps_cnt_4"),
            ],
            [
                InlineKeyboardButton(text="◀ Назад", callback_data="screen_tower_game_confirm")
            ],
        ]
    )

def build_tower_game_keyboard(game_data: dict, finished: bool = False) -> InlineKeyboardMarkup:
    keyboard = []
    current_floor = game_data["current_floor"]
    history = game_data["history"]
    game_over = game_data["game_over"]
    trap_positions = game_data["trap_positions"]
    traps_count = game_data["traps_count"]

    # Идет СВЕРХУ ВНИЗ (0 - верхний ряд, 7 - нижний ряд)
    for floor_idx in range(TOWER_FLOORS):
        row_buttons = []
        
        # Кнопка Икса (множителя) слева
        x_mult = calculate_tower_multiplier(traps_count, floor_idx + 1)
        row_buttons.append(InlineKeyboardButton(text=f"x{x_mult:.2f}", callback_data="locked_cell"))

        is_active_row = (floor_idx == current_floor) and not game_over
        is_passed = floor_idx < current_floor

        for col in range(5):
            if floor_idx in history:
                chosen_col, is_win = history[floor_idx]
                if col == chosen_col:
                    text = "🎁" if is_win else "💥"
                elif col in trap_positions[floor_idx]:
                    # Показываем мины после того как прошёл ряд
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
                cbd = f"open_tower_{floor_idx}_{col}"
            else:
                text = "🌑"
                cbd = "locked_cell"

            row_buttons.append(InlineKeyboardButton(text=text, callback_data=cbd))
        keyboard.append(row_buttons)

    if not game_over and current_floor > 0:
        current_win = game_data["current_win"]
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"Забрать {current_win:.2f}",
                    icon_custom_emoji_id="5305445793623218874",
                    callback_data="cashout_tower",
                )
            ]
        )

    if finished:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🔄 Сыграть снова", callback_data="screen_tower_game_confirm"
                ),
                InlineKeyboardButton(
                    text="◀ Меню", callback_data="tower_choose_bet"
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def safe_edit_message(call: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    """Вспомогательная функция для безопасного редактирования сообщений без ошибок TelegramBadRequest"""
    try:
        await call.message.edit_text(text=text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer()
        else:
            raise e


@dp.callback_query(F.data == "locked_cell")
async def locked_cell_handler(call: CallbackQuery) -> None:
    await call.answer()


@dp.callback_query(F.data == "mines_choose_bet")
async def mines_choose_bet_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MinesState.waiting_for_custom_bet)
    text = (
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку:\n'
        'Или напишите сумму ставки в чат</b>'
    )
    await safe_edit_message(call, text, get_bet_selection_keyboard())


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    get_user_balance(user_id)
    get_user_turnover(user_id)

    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)


# Нажатие на кнопку "Меню"
@dp.message(F.text.in_(["Меню", "/menu"]))
async def menu_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5278702045883292456">🛍</tg-emoji> Выберите действие!\n'
        f'<tg-emoji emoji-id="5242253527480311898">🪙</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await message.answer(
        text=text, parse_mode="HTML", reply_markup=menu_inline_keyboard
    )


# Нажатие на инлайн-кнопку "Профиль" из меню
@dp.callback_query(F.data == "open_profile")
async def open_profile_callback(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    full_name = call.from_user.full_name if call.from_user else "Игрок"

    text = build_profile_text(user_id, full_name)
    await safe_edit_message(call, text, profile_inline_keyboard)


# Закрытие профиля по кнопке "◀ Назад" - возвращает в Главное Меню
@dp.callback_query(F.data == "close_profile")
async def close_profile_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5278702045883292456">🛍</tg-emoji> Выберите действие!\n'
        f'<tg-emoji emoji-id="5242253527480311898">🪙</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, menu_inline_keyboard)


# Кошелек через инлайн-кнопку
@dp.callback_query(F.data == "open_wallet_inline")
async def open_wallet_inline_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    text = (
        f'<b><tg-emoji emoji-id="5470019396988606408">💵</tg-emoji> '
        f'Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, wallet_inline_keyboard)


@dp.message(F.text.in_(["Кошелек", "Баланс", "/wallet", "/balance"]))
async def wallet_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = get_user_balance(user_id)

    text = (
        f'<b><tg-emoji emoji-id="5470019396988606408">💵</tg-emoji> '
        f'Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await message.answer(
        text=text, parse_mode="HTML", reply_markup=wallet_inline_keyboard
    )


@dp.message(F.text.in_(["Играть", "/play"]))
async def play_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки !\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await message.answer(text=text, parse_mode="HTML", reply_markup=games_keyboard)


@dp.callback_query(F.data == "back_to_games")
async def back_to_games_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки !\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, games_keyboard)

@dp.callback_query(F.data.startswith("select_bet_"))
async def select_bet_quick(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = call.from_user.id
    bet = float(call.data.split("_")[2])
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
            reply_markup=get_preview_game_keyboard(user_id),
        )
    except ValueError:
        await message.answer("❌ Введите корректную сумму (например: 0.4 или 1):")


@dp.callback_query(F.data == "screen_game_confirm")
async def screen_game_confirm(call: CallbackQuery, state: FSMContext = None) -> None:
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
    await safe_edit_message(call, text, get_preview_game_keyboard(user_id))


@dp.callback_query(F.data == "screen_choose_mines")
async def screen_choose_mines(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MinesState.waiting_for_custom_mines)
    text = (
        '<b>💣 Выберите количество мин на поле (от 2 до 24):\n'
        'Или напишите количество мин числом в чат</b>'
    )
    await safe_edit_message(call, text, get_mines_count_keyboard())


@dp.callback_query(F.data.startswith("set_mines_cnt_"))
async def set_mines_count(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = call.from_user.id
    cnt = int(call.data.split("_")[3])
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
            reply_markup=get_preview_game_keyboard(user_id),
        )
    except ValueError:
        await message.answer("<b>❌ Пожалуйста, введите целое число от 2 до 24:</b>")


@dp.callback_query(F.data == "start_mines_game")
async def start_mines_game(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    st = get_game_settings(user_id)
    bet = st["bet"]
    mines_count = st["mines"]

    if balance < bet:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return

    user_balances[user_id] -= bet
    user_turnover[user_id] = get_user_turnover(user_id) + bet

    mines_positions = set(random.sample(range(FIELD_SIZE), mines_count))

    active_games[user_id] = {
        "bet": bet,
        "mines_count": mines_count,
        "mines_positions": mines_positions,
        "opened": set(),
        "game_over": False,
        "current_win": 0.00,
    }

    text = (
        f"<b>💣 Игра началась!\n\n"
        f"Ставка: {bet:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji> | Мин: {mines_count}\n"
        f"Выберите клетку:</b>"
    )

    await safe_edit_message(call, text, build_game_keyboard(active_games[user_id]))


@dp.callback_query(F.data.startswith("open_cell_"))
async def open_cell_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    if user_id not in active_games or active_games[user_id]["game_over"]:
        await call.answer("Игра завершена.", show_alert=True)
        return

    cell_idx = int(call.data.split("_")[2])
    game = active_games[user_id]

    if cell_idx in game["opened"]:
        await call.answer()
        return

    game["opened"].add(cell_idx)

    if cell_idx in game["mines_positions"]:
        game["game_over"] = True
        text = (
            f"<b>💥 Вы подорвались на мине!\n\n"
            f"Ваша ставка {game['bet']:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji> сгорела.</b>"
        )
        await safe_edit_message(call, text, build_game_keyboard(game, finished=True))
        del active_games[user_id]
        return

    opened_count = len(game["opened"])
    mult = calculate_multiplier(game["mines_count"], opened_count)
    current_win = game["bet"] * mult
    game["current_win"] = current_win

    if opened_count == (FIELD_SIZE - game["mines_count"]):
        game["game_over"] = True
        user_balances[user_id] = get_user_balance(user_id) + current_win
        text = (
            f"<b>🎉 Поздравляем! Вы открыли все безопасные клетки!\n\n"
            f"Ваш выигрыш: {current_win:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji></b>"
        )
        await safe_edit_message(call, text, build_game_keyboard(game, finished=True))
        del active_games[user_id]
        return

    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины\n\n'
        f'Множитель: x{mult:.2f}\n'
        f'Текущий выигрыш: {current_win:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, build_game_keyboard(game))


@dp.callback_query(F.data == "cashout_mines")
async def cashout_mines_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    if user_id not in active_games or active_games[user_id]["game_over"]:
        await call.answer("Игра не найдена.", show_alert=True)
        return

    game = active_games[user_id]
    win_amount = game["current_win"]
    game["game_over"] = True

    user_balances[user_id] = get_user_balance(user_id) + win_amount

    text = (
        f"<b>💰 Вы успешно забрали выигрыш!\n\n"
        f"Сумма: {win_amount:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji>\n"
        f"Ваш баланс: {user_balances[user_id]:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji></b>"
    )

    await safe_edit_message(call, text, build_game_keyboard(game, finished=True))
    del active_games[user_id]


# --- ХЕНДЛЕРЫ ДЛЯ ИГРЫ БАШНЯ ---

@dp.callback_query(F.data == "tower_choose_bet")
async def tower_choose_bet_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TowerState.waiting_for_custom_bet)
    text = (
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку:\n'
        'Или напишите сумму ставки в чат</b>'
    )
    await safe_edit_message(call, text, get_tower_bet_selection_keyboard())


@dp.callback_query(F.data.startswith("select_tower_bet_"))
async def select_tower_bet_quick(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = call.from_user.id
    bet = float(call.data.split("_")[3])
    st = get_tower_settings(user_id)
    st["bet"] = bet

    await screen_tower_game_confirm(call)


@dp.message(TowerState.waiting_for_custom_bet)
async def process_custom_tower_bet(message: Message, state: FSMContext) -> None:
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
            reply_markup=get_preview_tower_keyboard(user_id),
        )
    except ValueError:
        await message.answer("❌ Введите корректную сумму (например: 0.4 или 1):")


@dp.callback_query(F.data == "screen_tower_game_confirm")
async def screen_tower_game_confirm(call: CallbackQuery, state: FSMContext = None) -> None:
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
    await safe_edit_message(call, text, get_preview_tower_keyboard(user_id))


@dp.callback_query(F.data == "screen_choose_tower_traps")
async def screen_choose_tower_traps(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TowerState.waiting_for_custom_traps)
    text = (
        '<b>💣 Выберите количество мин на ряд (от 1 до 4):\n'
        'Или напишите количество мин числом в чат</b>'
    )
    await safe_edit_message(call, text, get_tower_traps_count_keyboard())


@dp.callback_query(F.data.startswith("set_tower_traps_cnt_"))
async def set_tower_traps_count(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = call.from_user.id
    cnt = int(call.data.split("_")[4])
    st = get_tower_settings(user_id)
    st["traps"] = cnt

    await screen_tower_game_confirm(call)


@dp.message(TowerState.waiting_for_custom_traps)
async def process_custom_tower_traps(message: Message, state: FSMContext) -> None:
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
            reply_markup=get_preview_tower_keyboard(user_id),
        )
    except ValueError:
        await message.answer("<b>❌ Пожалуйста, введите целое число от 1 до 4:</b>")


@dp.callback_query(F.data == "start_tower_game")
async def start_tower_game(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    balance = get_user_balance(user_id)
    st = get_tower_settings(user_id)
    bet = st["bet"]
    traps_count = st["traps"]

    if balance < bet:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return

    user_balances[user_id] -= bet
    user_turnover[user_id] = get_user_turnover(user_id) + bet

    trap_positions = {}
    for floor in range(TOWER_FLOORS):
        trap_positions[floor] = set(random.sample(range(5), traps_count))

    active_tower_games[user_id] = {
        "bet": bet,
        "traps_count": traps_count,
        "trap_positions": trap_positions,
        "current_floor": 0,
        "history": {},
        "game_over": False,
        "current_win": 0.00,
    }

    text = (
        f"<b><tg-emoji emoji-id=\"5449397725697187601\">🏰</tg-emoji> Игра началась!\n\n"
        f"Ставка: {bet:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji> | Мин в ряду: {traps_count}\n"
        f"Выберите клетку на 1 этаже (в самом верху):</b>"
    )

    await safe_edit_message(call, text, build_tower_game_keyboard(active_tower_games[user_id]))


@dp.callback_query(F.data.startswith("open_tower_"))
async def open_tower_cell_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    if user_id not in active_tower_games or active_tower_games[user_id]["game_over"]:
        await call.answer("Игра завершена.", show_alert=True)
        return

    parts = call.data.split("_")
    floor = int(parts[2])
    col = int(parts[3])

    game = active_tower_games[user_id]

    if floor != game["current_floor"]:
        await call.answer("Открывайте этажи по порядку сверху вниз!", show_alert=True)
        return

    traps = game["trap_positions"][floor]

    if col in traps:
        game["game_over"] = True
        game["history"][floor] = (col, False)
        text = (
            f"<b>💥 Вы подорвались на мине!\n\n"
            f"Ваша ставка {game['bet']:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji> сгорела.</b>"
        )
        await safe_edit_message(call, text, build_tower_game_keyboard(game, finished=True))
        del active_tower_games[user_id]
        return

    game["history"][floor] = (col, True)
    game["current_floor"] += 1
    opened_floors = game["current_floor"]

    mult = calculate_tower_multiplier(game["traps_count"], opened_floors)
    current_win = game["bet"] * mult
    game["current_win"] = current_win

    if opened_floors == TOWER_FLOORS:
        game["game_over"] = True
        user_balances[user_id] = get_user_balance(user_id) + current_win
        text = (
            f"<b>🎉 Поздравляем! Вы прошли всю башню!\n\n"
            f"Ваш выигрыш: {current_win:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji></b>"
        )
        await safe_edit_message(call, text, build_tower_game_keyboard(game, finished=True))
        del active_tower_games[user_id]
        return

    text = (
        f'<b><tg-emoji emoji-id="5449397725697187601">🏰</tg-emoji> Башня\n\n'
        f'Множитель: x{mult:.2f}\n'
        f'Текущий выигрыш: {current_win:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await safe_edit_message(call, text, build_tower_game_keyboard(game))


@dp.callback_query(F.data == "cashout_tower")
async def cashout_tower_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    if user_id not in active_tower_games or active_tower_games[user_id]["game_over"]:
        await call.answer("Игра не найдена.", show_alert=True)
        return

    game = active_tower_games[user_id]
    win_amount = game["current_win"]
    game["game_over"] = True

    user_balances[user_id] = get_user_balance(user_id) + win_amount

    text = (
        f"<b>💰 Вы успешно забрали выигрыш!\n\n"
        f"Сумма: {win_amount:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji>\n"
        f"Ваш баланс: {user_balances[user_id]:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji></b>"
    )

    await safe_edit_message(call, text, build_tower_game_keyboard(game, finished=True))
    del active_tower_games[user_id]


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
    await safe_edit_message(
        call,
        "<b>➕ Введите Telegram ID пользователя, которого хотите сделать админом:</b>",
        None
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
            f"<b>✅ Пользователь <code>{new_admin_id}</code> успешно добавлен в список администраторов!</b>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard(),
        )
    except ValueError:
        await message.answer("<b>❌ Некорректный ID. Введите число:</b>")


@dp.callback_query(F.data == "admin_add_balance")
async def admin_add_balance_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_add_balance_user)
    await safe_edit_message(
        call,
        "<b>💵 Введите ID игрока, которому нужно НАЧИСЛИТЬ баланс:</b>",
        None
    )


@dp.message(AdminState.waiting_for_add_balance_user)
async def admin_add_balance_user_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(message.text.strip())
        await state.update_data(target_id=target_id)
        await state.set_state(AdminState.waiting_for_add_balance_amount)
        await message.answer("<b>💵 Введите сумму для начисления:</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("<b>❌ Некорректный ID. Введите число:</b>")


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
    await safe_edit_message(
        call,
        "<b>📉 Введите ID игрока, у которого нужно ОТНЯТЬ баланс:</b>",
        None
    )


@dp.message(AdminState.waiting_for_sub_balance_user)
async def admin_sub_balance_user_process(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        target_id = int(message.text.strip())
        await state.update_data(target_id=target_id)
        await state.set_state(AdminState.waiting_for_sub_balance_amount)
        await message.answer("<b>📉 Введите сумму для списания:</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("<b>❌ Некорректный ID. Введите число:</b>")


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
        await safe_edit_message(
            call,
            "<b>👥 Список пользователей пуст.</b>",
            get_admin_keyboard()
        )
        return

    text = "<b>👥 Список пользователей и их балансов:</b>\n\n"
    for uid, bal in user_balances.items():
        text += f"• ID: <code>{uid}</code> | Баланс: <code>{bal:.2f} $</code>\n"

    if len(text) > 4000:
        text = text[:4000] + "\n..."

    await safe_edit_message(call, text, get_admin_keyboard())


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

    await safe_edit_message(call, text, get_admin_keyboard())


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext) -> None:
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_broadcast_text)
    await safe_edit_message(
        call,
        "<b>📢 Введите текст для рассылки всем пользователям:</b>",
        None
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


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
