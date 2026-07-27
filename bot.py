import asyncio
from aiogram import Bot, Dispatcher, F, html
from aiogram.filters import CommandStart
from aiogram.types import (
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


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    # Инициализируем баланс 0.00 для нового пользователя
    if user_id not in user_balances:
        user_balances[user_id] = 0.00

    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'

    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)


@dp.message(F.text.in_(["Кошелек", "Баланс", "/wallet", "/balance"]))
async def wallet_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0

    balance = user_balances.get(user_id, 0.00)

    text = (
        f'<b><tg-emoji emoji-id="5470019396988606408">💵</tg-emoji> '
        f'Баланс: </b><code>{balance:.2f}</code><b>$</b>'
    )

    await message.answer(
        text=text,
        parse_mode="HTML",
        reply_markup=wallet_inline_keyboard,
    )


# Новый обработчик для кнопки "Играть"
@dp.message(F.text.in_(["Играть", "/play"]))
async def play_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    balance = user_balances.get(user_id, 0.00)

    # Весь текст полностью жирный с твоими кастомными эмодзи
    text = (
        '<b><tg-emoji emoji-id="5463225256942539355">🚀</tg-emoji> Выберите игру для ставки !\n\n\n'
        f'<tg-emoji emoji-id="5197422813463483902">💵</tg-emoji> Баланс : </b><code>{balance:.2f}</code><b>$</b>'
    )

    await message.answer(
        text=text,
        parse_mode="HTML",
    )


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
