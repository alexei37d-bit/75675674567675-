import asyncio
import logging
import aiohttp
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardButton
)

BOT_TOKEN = "8804355629:AAH6auh84fLdBhSfQkI_dKBnY9QTa-XXm_k"

CRYPTO_BOT_API_KEY = "548204:AAZOXSPMBWOj3XO29UyRcrxpgxlzujtetPO"
XROCKET_API_KEY = "c36722e4cae191a22a9097963"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

USERS_DB = {}

def get_or_create_user(user_id: int, full_name: str) -> dict:
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {
            "name": full_name,
            "id": user_id,
            "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "balance": 0.0,
            "turnover": 0.0,
            "deposits": 0.0,
            "withdrawals": 0.0,
        }
    return USERS_DB[user_id]

class PaymentStates(StatesGroup):
    waiting_for_deposit_amount = State() 
    waiting_for_withdraw_amount = State()  
    waiting_for_withdraw_wallet = State()  

async def create_crypto_bot_invoice(amount: float, user_id: int) -> str:
    return "https://t.me/CryptoBot"

async def create_xrocket_invoice(amount: float, user_id: int) -> str:
    return "https://t.me/RocketWalletBot"

async def send_crypto_bot_payout(amount: float, target_user_id: int) -> bool:
    return False

WELCOME_TEXT = (
    '<b> <tg-emoji emoji-id=\"5451985838630014131\">💎</tg-emoji> Добро пожаловать в @dfnshfhsdnfksdbot</b>'
)

def reply_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="Баланс"), KeyboardButton(text="Играть"), KeyboardButton(text="Меню")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def main_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {
                "text": "Играть",
                "callback_data": "play",
                "icon_custom_emoji_id": "5471895876790161593",
            },
            {
                "text": "Чат",
                "callback_data": "chat",
                "icon_custom_emoji_id": "5235931189591710436",
            },
        ],
        [
            {
                "text": "Профиль",
                "callback_data": "profile",
                "icon_custom_emoji_id": "5870994129244131212",
            }
        ],
        [
            {
                "text": "🔒 Правила",
                "url": "https://telegra.ph/Pravila-WXS-game-07-13",
            },
            {
                "text": "Помощь",
                "callback_data": "help",
                "icon_custom_emoji_id": "6028435952299413210",
            },
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def balance_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Пополнить", "callback_data": "dev_mode", "icon_custom_emoji_id": "5415897719522744378"}, 
            {"text": "Вывести", "callback_data": "dev_mode", "icon_custom_emoji_id": "5361914370068613491"}
        ],
        [{"text": "< Назад", "callback_data": "back_to_main"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def profile_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Пополнить", "callback_data": "dev_mode", "icon_custom_emoji_id": "5415897719522744378"}, 
            {"text": "Вывести", "callback_data": "dev_mode", "icon_custom_emoji_id": "5361914370068613491"}
        ],
        [{"text": "Транзакции", "callback_data": "transactions"}],
        [{"text": "Настройки", "callback_data": "settings"}],
        [{"text": "< Назад", "callback_data": "back_to_main"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def get_profile_message(user: dict) -> str:
    return (
        f"<tg-emoji emoji-id=\"5275979556308674886\">👤</tg-emoji> <b>Имя:</b> {user['name']}\n"
        f"<tg-emoji emoji-id=\"5278753302023004775\">ℹ️</tg-emoji> <b>Ваш ID:</b> <code>{user['id']}</code>\n"
        f"<tg-emoji emoji-id=\"5276412364458059956\">🕓</tg-emoji> <b>Регистрация:</b> {user['reg_date']}\n\n"
        f"<tg-emoji emoji-id=\"5276398496008663230\">👝</tg-emoji> <b>Оборот:</b> {user['turnover']:.2f} $\n\n"
        f"<tg-emoji emoji-id=\"5206401524200145033\">🔼</tg-emoji> <b>Пополнений:</b> {user['deposits']:.2f} $\n"
        f"<tg-emoji emoji-id=\"5206510891247371052\">🔽</tg-emoji> <b>Выводов:</b> {user['withdrawals']:.2f} $"
    )

@dp.message(CommandStart())
async def start_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=reply_main_keyboard(),
    )
    await message.answer(
        '<tg-emoji emoji-id="5463225256942539355">🏠</tg-emoji> Главное меню проекта:',
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "Баланс")
async def reply_balance_handler(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(text=f'<tg-emoji emoji-id="5470019396988606408">💵</tg-emoji> Баланс : {user["balance"]:.2f} $', parse_mode="HTML", reply_markup=balance_keyboard())

@dp.message(F.text == "Меню")
async def reply_menu_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_keyboard())

@dp.message(F.text == "Играть")
async def reply_play_handler(message: Message):
    await message.answer("🎰 Раздел с играми находится в разработке!")

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    await callback.message.edit_text(text=get_profile_message(user), parse_mode="HTML", reply_markup=profile_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "dev_mode")
async def dev_mode_handler(callback: CallbackQuery):
    await callback.answer("Технические работы: функционал временно недоступен", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text=WELCOME_TEXT, parse_mode="HTML", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(F.data.in_({"play", "chat", "help", "referral", "checks", "top_players", "transactions", "settings", "dep_stars", "dep_usdt", "dep_trx", "dep_ton"}))
async def silent_callback(callback: CallbackQuery):
    await callback.answer("Эта функция сейчас в разработке!", show_alert=False)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
