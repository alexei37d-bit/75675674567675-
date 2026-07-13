import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Токен бота (лучше хранить в переменных окружения)
BOT_TOKEN = "8956232681:AAHMiBNrTPiLg-a3ACr-dpZP-yIG9EPJAoE"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    # Создаём клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Премиум 🎁",
                callback_data="premium"
            ),
            InlineKeyboardButton(
                text="Профиль 👤",
                callback_data="profile"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Магазин ⭐",
                callback_data="shop"
            ),
            InlineKeyboardButton(
                text="Задания 🎯",
                callback_data="tasks"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Удалить ❌",
                callback_data="delete"
            ),
        ],
    ])

    await message.answer(
        "👋 Добро пожаловать!\nВыберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    # Обработка нажатий на кнопки
    if callback.data == "premium":
        await callback.message.answer("🎁 Вы выбрали Премиум!\nДоступны эксклюзивные функции.")
    elif callback.data == "profile":
        await callback.message.answer("👤 Ваш профиль:\nИмя: Пользователь\nСтатус: Обычный")
    elif callback.data == "shop":
        await callback.message.answer("🛍️ Магазин:\n1. Премиум - 100⭐\n2. Бонусы - 50⭐")
    elif callback.data == "tasks":
        await callback.message.answer("🎯 Задания:\n- Пригласи друга\n- Выполни 5 действий")
    elif callback.data == "delete":
        await callback.message.answer("🗑️ Сообщение удалено!")
        await callback.message.delete()
    
    # Подтверждаем получение callback
    await callback.answer()

@dp.message()
async def echo(message: types.Message):
    # Ответ на любые другие сообщения
    await message.answer(
        "Используйте команду /start для начала работы с ботом"
    )

async def main():
    # Запуск бота
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
