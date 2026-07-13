import asyncio
import logging
import aiohttp
from datetime import datetime
import random

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
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

ADMIN_IDS = [6130985988, 7921743592]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

USERS_DB = {}
WITHDRAW_REQUESTS = {}

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
    
class AdminStates(StatesGroup):
    waiting_for_approve_link = State()
    waiting_for_broadcast = State()
    waiting_for_deduct_id = State()
    waiting_for_deduct_amount = State()

WELCOME_TEXT = ('<b> <tg-emoji emoji-id=\"5451985838630014131\">💎</tg-emoji> Добро пожаловать в @dfnshfhsdnfksdbot</b>')

def reply_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="Баланс"), KeyboardButton(text="Играть"), KeyboardButton(text="Меню")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def main_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Играть", "callback_data": "play", "icon_custom_emoji_id": "5471895876790161593"},
            {"text": "Чат", "callback_data": "chat", "icon_custom_emoji_id": "5235931189591710436"},
        ],
        [{"text": "Профиль", "callback_data": "profile", "icon_custom_emoji_id": "5870994129244131212"}],
        [
           {"text": "Правила", "url": "https://telegra.ph/Pravila-WXS-game-07-13", "icon_custom_emoji_id": "5296369303661067030"},
           {"text": "Помощь", "callback_data": "help", "icon_custom_emoji_id": "6028435952299413210"},
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def balance_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Пополнить", "callback_data": "deposit_select", "icon_custom_emoji_id": "5206401524200145033"}, 
            {"text": "Вывести", "callback_data": "withdraw_select", "icon_custom_emoji_id": "5206510891247371052"}
        ],
        [{"text": "< Назад", "callback_data": "back_to_main"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def profile_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Пополнить", "callback_data": "deposit_select", "icon_custom_emoji_id": "5206401524200145033"}, 
            {"text": "Вывести", "callback_data": "withdraw_select", "icon_custom_emoji_id": "5206510891247371052"}
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
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=reply_main_keyboard())
    await message.answer('<tg-emoji emoji-id="5463225256942539355">🏠</tg-emoji> Главное меню проекта:', parse_mode="HTML", reply_markup=main_keyboard())

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

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    await callback.message.edit_text(text=WELCOME_TEXT, parse_mode="HTML", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "deposit_select")
async def select_deposit_method(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="CryptoBot", callback_data="dep_method_crypto")],
        [InlineKeyboardButton(text="Xrocket", callback_data="dep_method_xrocket")],
        [InlineKeyboardButton(text="< Назад", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("Выберите способ пополнения:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("dep_method_"))
async def process_deposit_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[-1]
    await state.update_data(deposit_method=method)
    await callback.message.answer("Введите сумму пополнения (от 0.01 $):")
    await state.set_state(PaymentStates.waiting_for_deposit_amount)
    await callback.answer()

@dp.message(PaymentStates.waiting_for_deposit_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount < 0.01:
            await message.answer("Сумма пополнения должна быть от 0.01 $")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")
        return

    data = await state.get_data()
    method = data.get("deposit_method")
    
    if method == "crypto":
        invoice_url = "http://t.me/send?start=IVL1pjPkm04v"
    else:
        invoice_url = "https://t.me/xrocket?start=inv_ltGmVOFnRWoVk9U"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить счет", url=invoice_url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_dep_{amount}")]
    ])
    await message.answer(f"Оплата на сумму <b>{amount} $</b>\nПерейдите по ссылке и после оплаты нажмите «Проверить оплату».", parse_mode="HTML", reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data.startswith("check_dep_"))
async def check_deposit_status(callback: CallbackQuery):
    await callback.answer("⏳ Ожидание подтверждения оплаты от платежной системы...", show_alert=True)

@dp.callback_query(F.data == "withdraw_select")
async def select_withdraw_method(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="CryptoBot", callback_data="wd_method_crypto")],
        [InlineKeyboardButton(text="Xrocket", callback_data="wd_method_xrocket")],
        [InlineKeyboardButton(text="< Назад", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("Выберите способ вывода:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("wd_method_"))
async def process_withdraw_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[-1]
    await state.update_data(withdraw_method=method)
    await callback.message.answer("Введите сумму вывода (от 1 $):")
    await state.set_state(PaymentStates.waiting_for_withdraw_amount)
    await callback.answer()

@dp.message(PaymentStates.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount < 1:
            await message.answer("Сумма вывода должна быть от 1 $")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")
        return

    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    if user["balance"] < amount:
        await message.answer("❌ Недостаточно средств на балансе.")
        await state.clear()
        return

    data = await state.get_data()
    method = data.get("withdraw_method")
    
    user["balance"] -= amount
    req_id = random.randint(10000, 99999)
    WITHDRAW_REQUESTS[req_id] = {"user_id": message.from_user.id, "amount": amount, "method": method, "status": "pending"}
    
    await message.answer(f"✅ Заявка #{req_id} создана.")
    await state.clear()
    
    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Одобрить", callback_data=f"admin_approve_req_{req_id}")],
                [InlineKeyboardButton(text="Отклонить", callback_data=f"admin_reject_req_{req_id}")]
            ])
            await bot.send_message(admin_id, f"🚨 Заявка #{req_id}\nОт: {message.from_user.id}\nСумма: {amount} $\nСпособ: {method}", reply_markup=kb)
        except Exception: pass

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заявки на вывод", callback_data="admin_withdraw_requests")],
        [InlineKeyboardButton(text="Отнять баланс", callback_data="admin_deduct_bal")],
        [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="Статистика", callback_data="admin_stats")]
    ])
    await message.answer("🔧 Админ-панель:", reply_markup=kb)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    total_users = len(USERS_DB)
    total_deps = sum(u["deposits"] for u in USERS_DB.values())
    total_wds = sum(u["withdrawals"] for u in USERS_DB.values())
    await callback.message.answer(f"📊 Статистика:\nПользователей: {total_users}\nВсего пополнений: {total_deps} $\nВсего выводов: {total_wds} $")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("Введите сообщение для рассылки:")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    count = 0
    for user_id in USERS_DB.keys():
        try:
            await bot.send_message(user_id, message.text, entities=message.entities)
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    await message.answer(f"✅ Рассылка завершена. Отправлено: {count} пользователям.")
    await state.clear()

@dp.callback_query(F.data == "admin_deduct_bal")
async def admin_deduct_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_deduct_id)
    await callback.answer()

@dp.message(AdminStates.waiting_for_deduct_id)
async def process_deduct_id(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("ID должен быть числом.")
    await state.update_data(deduct_user_id=int(message.text))
    await message.answer("Введите сумму для списания:")
    await state.set_state(AdminStates.waiting_for_deduct_amount)

@dp.message(AdminStates.waiting_for_deduct_amount)
async def process_deduct_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError: return await message.answer("Неверная сумма.")
    data = await state.get_data()
    user_id = data.get("deduct_user_id")
    if user_id in USERS_DB:
        USERS_DB[user_id]["balance"] -= amount
        await message.answer(f"✅ Списано {amount} $ у {user_id}.")
    else: await message.answer("❌ Пользователь не найден.")
    await state.clear()

@dp.callback_query(F.data == "admin_withdraw_requests")
async def admin_show_requests(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    pending_reqs = [req_id for req_id, req in WITHDRAW_REQUESTS.items() if req["status"] == "pending"]
    if not pending_reqs: return await callback.answer("Нет активных заявок.", show_alert=True)
    for req_id in pending_reqs:
        req = WITHDRAW_REQUESTS[req_id]
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Одобрить", callback_data=f"admin_approve_req_{req_id}")], [InlineKeyboardButton(text="Отклонить", callback_data=f"admin_reject_req_{req_id}")]])
        await callback.message.answer(f"🚨 Заявка #{req_id}\nСумма: {req['amount']} $\nСпособ: {req['method']}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_approve_req_"))
async def admin_approve_req_inline(callback: CallbackQuery, state: FSMContext):
    req_id = int(callback.data.split("_")[-1])
    await state.update_data(approve_req_id=req_id)
    await callback.message.answer(f"Отправьте ссылку на чек для заявки #{req_id}:")
    await state.set_state(AdminStates.waiting_for_approve_link)
    await callback.answer()

@dp.message(AdminStates.waiting_for_approve_link)
async def process_approve_link(message: Message, state: FSMContext):
    check_url = message.text
    data = await state.get_data()
    req_id = data.get("approve_req_id")
    req = WITHDRAW_REQUESTS[req_id]
    req["status"] = "approved"
    USERS_DB[req["user_id"]]["withdrawals"] += req["amount"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Активировать чек", url=check_url)]])
    await bot.send_message(req["user_id"], "✅ Ваш вывод одобрен.", reply_markup=kb)
    await message.answer("✅ Чек отправлен.")
    await state.clear()

@dp.callback_query(F.data.startswith("admin_reject_req_"))
async def admin_reject_req_inline(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[-1])
    req = WITHDRAW_REQUESTS[req_id]
    req["status"] = "rejected"
    USERS_DB[req["user_id"]]["balance"] += req["amount"]
    await bot.send_message(req["user_id"], f"❌ Вывод {req['amount']} $ отклонен.")
    await callback.message.edit_text("❌ ОТКЛОНЕНО")
    await callback.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
