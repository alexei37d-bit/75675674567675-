import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])  # Для aiogram 2.x используется message_handler
async def start(message: types.Message):
    # Создаём клавиатуру с кнопками (эмодзи поддерживаются)
    keyboard = InlineKeyboardMarkup(row_width=2)  # row_width - сколько кнопок в ряду
    
    # Добавляем кнопки
    keyboard.add(
        InlineKeyboardButton("🎁 Премиум", callback_data="premium"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )
    keyboard.add(
        InlineKeyboardButton("⭐ Магазин", callback_data="shop"),
        InlineKeyboardButton("🎯 Задания", callback_data="tasks")
    )
    keyboard.add(
        InlineKeyboardButton("❌ Удалить", callback_data="delete")
    )

    await message.answer("👋 Добро пожаловать!\nВыберите действие:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: True)  # Для aiogram 2.x
async def handle_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)  # Подтверждаем получение
    
    if callback_query.data == "premium":
        await bot.send_message(callback_query.from_user.id, "🎁 Вы выбрали Премиум!\nДоступны эксклюзивные функции.")
    elif callback_query.data == "profile":
        await bot.send_message(callback_query.from_user.id, "👤 Ваш профиль:\nИмя: Пользователь\nСтатус: Обычный")
    elif callback_query.data == "shop":
        await bot.send_message(callback_query.from_user.id, "🛍️ Магазин:\n1. Премиум - 100⭐\n2. Бонусы - 50⭐")
    elif callback_query.data == "tasks":
        await bot.send_message(callback_query.from_user.id, "🎯 Задания:\n- Пригласи друга\n- Выполни 5 действий")
    elif callback_query.data == "delete":
        await bot.send_message(callback_query.from_user.id, "🗑️ Сообщение удалено!")
        await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

@dp.message_handler()
async def echo(message: types.Message):
    await message.answer("Используйте команду /start для начала работы с ботом")

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
