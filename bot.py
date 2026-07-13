import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart  # ДОБАВЛЕНО

bot = Bot(token="8364120048:AAFE8DkMaaTt8_MgYoJQkHVsiG41Cg_AZIo")
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: types.Message):
    # Создаём клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Премиум 🎁",  # Текст кнопки
                callback_data="premium",  # Данные при нажатии
                style="primary",  # Синий цвет
                icon_custom_emoji_id="5471952986970267163"  # ID эмодзи: 💎
            ),
            InlineKeyboardButton(
                text="Профиль",  # Текст кнопки
                callback_data="profile",  # Данные при нажатии
                style="success",  # Зелёный цвет
                icon_custom_emoji_id="5368324170671202286"  # ID эмодзи: 👤
            ),
        ],
        [
            InlineKeyboardButton(
                text="Магазин ⭐",  # Текст кнопки
                callback_data="shop",  # Данные при нажатии
                icon_custom_emoji_id="547644880824181073"  # ID эмодзи: ⭐
            ),
            InlineKeyboardButton(
                text="Задания 🎯",  # Текст кнопки
                callback_data="tasks",  # Данные при нажатии
                icon_custom_emoji_id="547528498097861387"  # ID эмодзи: 🎯
            ),
        ],
        [
            InlineKeyboardButton(
                text="Удалить ❌",  # Текст кнопки
                callback_data="delete",  # Данные при нажатии
                style="danger",  # Красный цвет
                icon_custom_emoji_id="5310169226856644648"  # ID эмодзи: 🗑
            ),
        ],
    ])

    # Отправляем сообщение с кнопками
    await message.answer("Выберите действие:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    await callback.answer()  # ДОБАВЛЕНО
    
    # Обработка нажатий
    if callback.data == "premium":
        await callback.message.answer("Вы нажали на Премиум кнопку!")
    elif callback.data == "profile":
        await callback.message.answer("Вы открыли профиль!")
    elif callback.data == "shop":
        await callback.message.answer("Вы выбрали магазин!")
    elif callback.data == "delete":
        await callback.message.answer("Вы удалили!")

# Запуск бота
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))  # ИСПРАВЛЕНО
