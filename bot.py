import asyncio
from aiogram import Bot, Dispatcher, html
from aiogram.filters import CommandStart
from aiogram.types import Message

# Тестовый токен
TOKEN = "8740242990:AAF2I7c7x_SD6-Dww3WQJKQYbk3WsXYP5BI"

dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    # Получаем имя пользователя
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    # Экранируем имя и формируем жирный текст с эмодзи
    text = f'<b><tg-emoji emoji-id="5472419592217332357">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>'

    # Отправляем сообщение
    await message.answer(text, parse_mode="HTML")


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
