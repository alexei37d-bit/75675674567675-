import asyncio
from aiogram import Bot, Dispatcher, html
from aiogram.filters import CommandStart
from aiogram.types import Message

# Замените 'ВАШ_ТОКЕН_БОТА' на токен, полученный от @BotFather
TOKEN = "8740242990:AAF2I7c7x_SD6-Dww3WQJKQYbk3WsXYP6BI"

dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    # Получаем имя пользователя (или 'Игрок', если имя не указано)
    user_name = message.from_user.first_name if message.from_user else "Игрок"

    # Экранируем имя пользователя для безопасности и делаем текст жирным
    text = f"<b><tg-emoji emoji-id=\"5472419592217332357\">🔥</tg-emoji> Добро пожаловать, {html.quote(user_name)}!</b>"

    # Отправляем сообщение с поддержкой HTML-разметки
    await message.answer(text, parse_mode="HTML")


async def main() -> None:
    bot = Bot(token=TOKEN)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
