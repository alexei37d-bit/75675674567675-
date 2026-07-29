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

# Словарь для хранения балансов пользователей (по умолчанию 0.00)
user_balances = {}

# Хранилище активных игр: user_id -> dict
active_games = {}


# Состояния FSM для ввода произвольной ставки
class MinesState(StatesGroup):
    waiting_for_custom_bet = State()


# Настройки игры Мины
DEFAULT_BET = 0.10
MIN_MINES = 2
MAX_MINES = 24
FIELD_SIZE = 25  # Поле 5x5


# Временный выбор параметров перед стартом игры (user_id -> dict)
game_settings = {}


def get_game_settings(user_id: int):
    if user_id not in game_settings:
        game_settings[user_id] = {"bet": DEFAULT_BET, "mines": 3}
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

# Клавиатура выбора игр
games_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Мины",
                icon_custom_emoji_id="5452018153963948977",
                callback_data="mines_select",
            )
        ]
    ]
)


# Генерация клавиатуры настроек перед игрой
def get_mines_setup_keyboard(user_id: int) -> InlineKeyboardMarkup:
    st = get_game_settings(user_id)
    bet = st["bet"]
    mines = st["mines"]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="0.1$", callback_data="set_bet_0.1"
                ),
                InlineKeyboardButton(
                    text="0.5$", callback_data="set_bet_0.5"
                ),
                InlineKeyboardButton(text="1$", callback_data="set_bet_1.0"),
            ],
            [
                InlineKeyboardButton(
                    text=f"💣 Мин: {mines}", callback_data="change_mines_count"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"▶ Играть ({bet:.2f}$)", callback_data="start_mines_game"
                )
            ],
        ]
    )


# Генерация игрового поля 5x5
def build_game_keyboard(game_data: dict) -> InlineKeyboardMarkup:
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
                    text = "💎"
            elif game_over and idx in mines_positions:
                text = "💣"
            else:
                text = "❓"

            row_buttons.append(
                InlineKeyboardButton(
                    text=text, callback_data=f"open_cell_{idx}"
                )
            )
        keyboard.append(row_buttons)

    # Если игра активна и угадан хотя бы 1 кристалл — добавляем кнопку забрать выигрыш
    if not game_over and len(opened) > 0:
        current_win = game_data["current_win"]
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"💰 Забрать {current_win:.2f}$",
                    callback_data="cashout_mines",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Расчет коэффициента выигрыша
def calculate_multiplier(mines_count: int, opened_count: int) -> float:
    mult = 1.0
    safe_cells = FIELD_SIZE - mines_count
    for i in range(opened_count):
        mult *= safe_cells / (FIELD_SIZE - i)
        safe_cells -= 1
    return max(round(1 / mult, 2), 1.01)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    if user_id not in user_balances:
        user_balances[user_id] = 10.00  # Для теста дадим начальный баланс

    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'

    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)


@dp.message(F.text.in_(["Кошелек", "Баланс", "/wallet", "/balance"]))
async def wallet_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = user_balances.get(user_id, 0.00)

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
    balance = user_balances.get(user_id, 0.00)

    text = (
        '<b><tg-emoji emoji-id="5309815458990433715">🎮</tg-emoji> Выберите игру для ставки !\n\n\n'
        f'<tg-emoji emoji-id="5307942883314147223">🏆</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )

    await message.answer(text=text, parse_mode="HTML", reply_markup=games_keyboard)


@dp.message(F.text.in_(["Меню", "/menu"]))
async def menu_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = user_balances.get(user_id, 0.00)

    text = (
        '<b><tg-emoji emoji-id="5278702045883292456">🛍</tg-emoji> Выберите действие!\n\n'
        f'<tg-emoji emoji-id="5242253527480311898">🪙</tg-emoji> Баланс: </b><code>{balance:.2f}</code><b> <tg-emoji emoji-id="5305445793623218874">💲</tg-emoji></b>'
    )

    await message.answer(text=text, parse_mode="HTML")


# Меню настроек игры "Мины"
@dp.callback_query(F.data == "mines_select")
async def mines_select_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    st = get_game_settings(user_id)

    text = (
        f'<tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку:\n'
        f'<i>(нажмите на одну из кнопок ниже или напишите сумму ставки в чат)</i>\n\n'
        f'Текущая ставка: <b>{st["bet"]:.2f}$</b>\n'
        f'Количество мин: <b>{st["mines"]}</b>'
    )

    await call.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_mines_setup_keyboard(user_id),
    )


# Обработчики быстрого выбора ставки
@dp.callback_query(F.data.startswith("set_bet_"))
async def set_bet_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    bet = float(call.data.split("_")[2])
    game_settings[user_id] = get_game_settings(user_id)
    game_settings[user_id]["bet"] = bet

    await mines_select_handler(call)


# Обработчик переключения количества мин
@dp.callback_query(F.data == "change_mines_count")
async def change_mines_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    st = get_game_settings(user_id)

    # Увеличиваем мин, если больше 24 — сбрасываем до 2
    st["mines"] += 1
    if st["mines"] > MAX_MINES:
        st["mines"] = MIN_MINES

    await mines_select_handler(call)


# Прием ставки текстом от пользователя
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

        text = (
            f'<tg-emoji emoji-id="5451754391432366821">💰</tg-emoji> Выберите ставку:\n'
            f'<i>(нажмите на одну из кнопок ниже или напишите сумму ставки в чат)</i>\n\n'
            f'Текущая ставка: <b>{st["bet"]:.2f}$</b>\n'
            f'Количество мин: <b>{st["mines"]}</b>'
        )
        await message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_mines_setup_keyboard(user_id),
        )

    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число (например: 0.4 или 1.5):")


# Старт игры "Мины"
@dp.callback_query(F.data == "start_mines_game")
async def start_mines_game(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    balance = user_balances.get(user_id, 0.00)
    st = get_game_settings(user_id)
    bet = st["bet"]
    mines_count = st["mines"]

    if balance < bet:
        await call.answer("❌ Недостаточно средств на балансе!", show_alert=True)
        return

    # Списываем ставку
    user_balances[user_id] -= bet

    # Генерация случайного расположения мин
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
        f'💣 <b>Игра началась!</b>\n\n'
        f'Ставка: <b>{bet:.2f}$</b> | Мин: <b>{mines_count}</b>\n'
        f'Выберите клетку:'
    )

    await call.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=build_game_keyboard(active_games[user_id]),
    )


# Нажатие на клетку
@dp.callback_query(F.data.startswith("open_cell_"))
async def open_cell_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    if user_id not in active_games or active_games[user_id]["game_over"]:
        await call.answer("Игра завершена или не найдена.", show_alert=True)
        return

    cell_idx = int(call.data.split("_")[2])
    game = active_games[user_id]

    if cell_idx in game["opened"]:
        await call.answer()
        return

    game["opened"].add(cell_idx)

    # Если наступили на мину
    if cell_idx in game["mines_positions"]:
        game["game_over"] = True
        text = (
            f'💥 <b>Вы подорвались на мине!</b>\n\n'
            f'Ваша ставка <b>{game["bet"]:.2f}$</b> сгорела.'
        )
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=build_game_keyboard(game),
        )
        del active_games[user_id]
        return

    # Если открыли безопасную клетку
    opened_count = len(game["opened"])
    mult = calculate_multiplier(game["mines_count"], opened_count)
    current_win = game["bet"] * mult
    game["current_win"] = current_win

    # Если открыли все безопасные клетки
    if opened_count == (FIELD_SIZE - game["mines_count"]):
        game["game_over"] = True
        user_balances[user_id] += current_win
        text = (
            f'🎉 <b>Поздравляем! Вы открыли все безопасные клетки!</b>\n\n'
            f'Ваш выигрыш: <b>{current_win:.2f}$</b>'
        )
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=build_game_keyboard(game),
        )
        del active_games[user_id]
        return

    # Продолжение игры
    text = (
        f'💎 <b>Отлично!</b> Клетка безопасна.\n\n'
        f'Множитель: <b>x{mult:.2f}</b>\n'
        f'Текущий выигрыш: <b>{current_win:.2f}$</b>'
    )
    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=build_game_keyboard(game)
    )


# Кнопка "Забрать деньги"
@dp.callback_query(F.data == "cashout_mines")
async def cashout_mines_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    if user_id not in active_games or active_games[user_id]["game_over"]:
        await call.answer("Игра не найдена.", show_alert=True)
        return

    game = active_games[user_id]
    win_amount = game["current_win"]
    game["game_over"] = True

    # Зачисляем выигрыш
    user_balances[user_id] += win_amount

    text = (
        f'💰 <b>Вы успешно забрали выигрыш!</b>\n\n'
        f'Сумма: <b>{win_amount:.2f}$</b>\n'
        f'Ваш баланс: <b>{user_balances[user_id]:.2f}$</b>'
    )

    await call.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=build_game_keyboard(game)
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
