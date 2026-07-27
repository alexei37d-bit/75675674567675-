import asyncio
from aiogram import Bot, Dispatcher, html
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message

# Твой рабочий токен
TOKEN = "8740242990:AAF2I7c7x_SD6-Dww3WQJKQYbk3WsXYP5BI"

dp = Dispatcher()

# Создаём обычную клавиатуру под полем ввода
# В text вставляем премиум-эмодзи в формате <tg-emoji emoji-id="..."></tg-emoji>
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text='<tg-emoji emoji-id="5197686464325915345">👛</tg-emoji> Кошелек'
            ),
            KeyboardButton(
                text='<tg-emoji emoji-id="5471895876790161593">🎮</tg-emoji> Играть'
            ),
            KeyboardButton(
                text='<tg-emoji emoji-id="5469969339144773395">📜</tg-emoji> Меню'
            ),
        ]
    ],
    resize_keyboard=True,
)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'

    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
