import asyncio
from aiogram import Bot, Dispatcher, html
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message

# Твой рабочий токен
TOKEN = "ТВОЙ_ТОКЕН_БОТА"

dp = Dispatcher()

# Создаём обычную клавиатуру (внизу экрана)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text='<tg-emoji emoji-id="5472419592217332357">👛</tg-emoji> Кошелек'
            ),
            KeyboardButton(
                text='<tg-emoji emoji-id="5472419592217332357">🎮</tg-emoji> Играть'
            ),
            KeyboardButton(
                text='<tg-emoji emoji-id="5472419592217332357">📜</tg-emoji> Меню'
            ),
        ]
    ],
    resize_keyboard=True,  # Делает кнопки компактными
)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    # Получаем имя пользователя
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    # Экранируем имя и формируем жирный текст с эмодзи
    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'

    # Отправляем сообщение с клавиатурой
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
