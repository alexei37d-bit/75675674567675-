import asyncio
import random
from aiogram import Bot, Dispatcher, F, html
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

# Активные игры: user_id -> dict
active_games = {}

# Параметры ставок перед игрой: user_id -> dict
game_settings = {}


class MinesState(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_custom_mines = State()


FIELD_SIZE = 25  # Поле 5x5


def get_user_balance(user_id: int) -> float:
    return user_balances.setdefault(user_id, 1.00)


def get_game_settings(user_id: int):
    if user_id not in game_settings:
        game_settings[user_id] = {"bet": 0.10, "mines": 3}
    return game_settings[user_id]


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

games_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Мины",
                icon_custom_emoji_id="5452018153963948977",
                callback_data="mines_choose_bet",
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
                    text="0.1", callback_data="select_bet_0.1"
                ),
                InlineKeyboardButton(
                    text="0.5", callback_data="select_bet_0.5"
                ),
                InlineKeyboardButton(
                    text="1", callback_data="select_bet_1.0"
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
    # Поле 5х5 из лун
    for _ in range(5):
        row = [
            InlineKeyboardButton(text="🌑", callback_data="locked_cell")
            for _ in range(5)
        ]
        keyboard.append(row)

    # Управление под полем
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

    # Забрать выигрыш
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

    # По окончанию игры
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


# Небольшие множители (иксы)
def calculate_multiplier(mines_count: int, opened_count: int) -> float:
    base = 1.0 + (mines_count * 0.03)
    mult = base**opened_count
    return max(round(mult, 2), 1.01)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    get_user_balance(user_id)

    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)


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
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки !\n\n\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await message.answer(text=text, parse_mode="HTML", reply_markup=games_keyboard)


@dp.message(F.text.in_(["Меню", "/menu"]))
async def menu_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5278702045883292456">🛍</tg-emoji> Выберите действие!\n\n'
        f'<tg-emoji emoji-id="5242253527480311898">🪙</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await message.answer(text=text, parse_mode="HTML")


@dp.callback_query(F.data == "back_to_games")
async def back_to_games_handler(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user_id = call.from_user.id
    balance = get_user_balance(user_id)

    text = (
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки !\n\n\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=games_keyboard
    )


# Нажатие на луны до старта
@dp.callback_query(F.data == "locked_cell")
async def locked_cell_handler(call: CallbackQuery) -> None:
    await call.answer("Сначала нажмите «Играть», чтобы начать!", show_alert=True)


# Выбор ставки
@dp.callback_query(F.data == "mines_choose_bet")
async def mines_choose_bet_handler(
    call: CallbackQuery, state: FSMContext
) -> None:
    await state.set_state(MinesState.waiting_for_custom_bet)
    text = (
        '<b><tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку:\n'
        'Или напишите сумму ставки в чат</b>'
    )
    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=get_bet_selection_keyboard()
    )


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
        await message.answer("<b>❌ Введите корректную сумму (например: 0.4 или 1):</b>")


# Экран предпросмотра
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
    await call.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_preview_game_keyboard(user_id),
    )


# Экран выбора / ввода мин
@dp.callback_query(F.data == "screen_choose_mines")
async def screen_choose_mines(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MinesState.waiting_for_custom_mines)
    text = (
        '<b>💣 Выберите количество мин на поле (от 2 до 24):\n'
        'Или напишите количество мин числом в чат</b>'
    )
    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=get_mines_count_keyboard()
    )


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


# Старт игры
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

    await call.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=build_game_keyboard(active_games[user_id]),
    )


# Открытие клеток
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

    # Взрыв
    if cell_idx in game["mines_positions"]:
        game["game_over"] = True
        text = (
            f"<b>💥 Вы подорвались на мине!\n\n"
            f"Ваша ставка {game['bet']:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji> сгорела.</b>"
        )
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=build_game_keyboard(game, finished=True),
        )
        del active_games[user_id]
        return

    # Успешный ход
    opened_count = len(game["opened"])
    mult = calculate_multiplier(game["mines_count"], opened_count)
    current_win = game["bet"] * mult
    game["current_win"] = current_win

    # Выиграл все безопасные клетки
    if opened_count == (FIELD_SIZE - game["mines_count"]):
        game["game_over"] = True
        user_balances[user_id] = get_user_balance(user_id) + current_win
        text = (
            f"<b>🎉 Поздравляем! Вы открыли все безопасные клетки!\n\n"
            f"Ваш выигрыш: {current_win:.2f} <tg-emoji emoji-id=\"5305445793623218874\">💲</tg-emoji></b>"
        )
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=build_game_keyboard(game, finished=True),
        )
        del active_games[user_id]
        return

    # Продолжение
    text = (
        f'<b><tg-emoji emoji-id="5452018153963948977">💣</tg-emoji> Мины\n\n'
        f'Множитель: x{mult:.2f}\n'
        f'Текущий выигрыш: {current_win:.2f} <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )
    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=build_game_keyboard(game)
    )


# Забрать деньги
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

    await call.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=build_game_keyboard(game, finished=True),
    )
    del active_games[user_id]


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
if __name__ == "__main__":
    asyncio.run(main())
