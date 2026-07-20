import asyncio
import logging
import aiohttp
from aiohttp import web
from datetime import datetime
import random
import uuid
import html

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
CRYPTO_BOT_TOKEN = "611566:AAtSWGwJ3QTFtDPqTVNmvHxi6niSqwCn3eP"

ADMIN_IDS = [6130985988, 7921743592]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

USERS_DB = {}
WITHDRAW_REQUESTS = {}
PENDING_INVOICES = {}

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

def get_or_create_user(user_id: int, full_name: str) -> dict:
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {
            "name": html.escape(full_name),
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

DEPOSIT_METHODS_TEXT = "<b>Выберите способ пополнения:</b>"
WITHDRAW_METHODS_TEXT = "<b>Выберите способ вывода:</b>"

def reply_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="Баланс"), KeyboardButton(text="Играть"), KeyboardButton(text="Меню")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def main_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Играть", "callback_data": "play"},
            {"text": "Чат", "callback_data": "chat"},
        ],
        [{"text": "Профиль", "callback_data": "profile"}],
        [
           {"text": "Правила", "url": "https://telegra.ph/Pravila-WXS-game-07-13"},
           {"text": "Помощь", "callback_data": "help"},
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def balance_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Пополнить", "callback_data": "deposit_select_balance"}, 
            {"text": "Вывести", "callback_data": "withdraw_select_balance"}
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def profile_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Пополнить", "callback_data": "deposit_select_profile"}, 
            {"text": "Вывести", "callback_data": "withdraw_select_profile"}
        ],
        [{"text": "Транзакции", "callback_data": "transactions"}],
        [{"text": "Настройки", "callback_data": "settings"}],
        [{"text": "< Назад", "callback_data": "back_to_main"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def help_keyboard() -> InlineKeyboardMarkup:
    raw_inline_keyboard = [
        [
            {"text": "Тех. поддержка", "url": "https://t.me/jei1a"}
        ],
        [
            {"text": "< Назад", "callback_data": "back_to_main"}
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)

def get_profile_message(user: dict) -> str:
    return (
        f"👤 <b>Имя:</b> {user['name']}\n"
        f"ℹ️ <b>Ваш ID:</b> <code>{user['id']}</code>\n"
        f"🕓 <b>Регистрация:</b> {user['reg_date']}\n\n"
        f"👝 <b>Оборот:</b> {user['turnover']:.2f} $\n\n"
        f"🔼 <b>Пополнений:</b> {user['deposits']:.2f} $\n"
        f"🔽 <b>Выводов:</b> {user['withdrawals']:.2f} $"
    )

@dp.message(CommandStart())
async def start_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    bot_info = await bot.get_me()
    welcome_text = f'💎 <b>Добро пожаловать в</b> @{bot_info.username}'
    
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=reply_main_keyboard())
    await message.answer('🏠 <b>Главное меню проекта:</b>', parse_mode="HTML", reply_markup=main_keyboard(bot_info.username))

@dp.message(F.text == "Баланс")
async def reply_balance_handler(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    await message.answer(text=f'💵 <b>Баланс :</b> {user["balance"]:.2f} $', parse_mode="HTML", reply_markup=balance_keyboard())

@dp.message(F.text == "Меню")
async def reply_menu_handler(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.full_name)
    bot_info = await bot.get_me()
    welcome_text = f'💎 <b>Добро пожаловать в</b> @{bot_info.username}'
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=reply_main_keyboard())
    await message.answer('🏠 <b>Главное меню проекта:</b>', parse_mode="HTML", reply_markup=main_keyboard(bot_info.username))

@dp.message(F.text == "Играть")
async def reply_play_handler(message: Message):
    await message.answer("🎰 <b>Раздел с играми находится в разработке!</b>", parse_mode="HTML")

@dp.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    help_text = (
        '⚠️ <b>Важно!</b>\n\n'
        '<b>— Вопросы по выводу/пополнению — в Техподдержку.</b>\n'
        '<b>— Технические сбои и ошибки — в Техподдержку.</b>\n'
        '<b>— Предложения и пожелания по работе казино — тоже в Техподдержку.</b>'
    )
    await callback.message.edit_text(text=help_text, reply_markup=help_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    await callback.message.edit_text(text=get_profile_message(user), parse_mode="HTML", reply_markup=profile_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    bot_info = await bot.get_me()
    menu_text = '🏠 <b>Главное меню проекта:</b>'
    await callback.message.edit_text(text=menu_text, parse_mode="HTML", reply_markup=main_keyboard(bot_info.username))
    await callback.answer()

@dp.callback_query(F.data == "back_to_balance")
async def back_to_balance_handler(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name)
    await callback.message.edit_text(text=f'💵 <b>Баланс :</b> {user["balance"]:.2f} $', parse_mode="HTML", reply_markup=balance_keyboard())
    await callback.answer()

@dp.callback_query(F.data.in_({"deposit_select_balance", "deposit_select_profile"}))
async def select_deposit_method(callback: CallbackQuery, state: FSMContext):
    source = callback.data.split("_")[-1]
    await state.update_data(return_to=source)
    
    back_cb = "back_to_balance" if source == "balance" else "profile"
    raw_inline_keyboard = [
        [{"text": "CryptoBot", "callback_data": "dep_method_crypto"}],
        [{"text": "< Назад", "callback_data": back_cb}]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)
    await callback.message.edit_text(DEPOSIT_METHODS_TEXT, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("dep_method_"))
async def process_deposit_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[-1]
    await state.update_data(deposit_method=method)
    
    data = await state.get_data()
    back_cb = "back_to_balance" if data.get("return_to") == "balance" else "profile"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [{"text": "< Назад", "callback_data": back_cb}]
    ])
    await callback.message.edit_text("<b>Введите сумму пополнения в USDT (от 0.1 $):</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(PaymentStates.waiting_for_deposit_amount)
    await callback.answer()

@dp.message(PaymentStates.waiting_for_deposit_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    back_cb = "back_to_balance" if data.get("return_to") == "balance" else "profile"

    try:
        amount = float(message.text.replace(",", "."))
        if amount < 0.1:
            kb = InlineKeyboardMarkup(inline_keyboard=[[{"text": "< Назад", "callback_data": back_cb}]])
            await message.answer("<b>Сумма пополнения должна быть от 0.1 $</b>", reply_markup=kb, parse_mode="HTML")
            return
    except ValueError:
        kb = InlineKeyboardMarkup(inline_keyboard=[[{"text": "< Назад", "callback_data": back_cb}]])
        await message.answer("<b>Пожалуйста, введите корректное число.</b>", reply_markup=kb, parse_mode="HTML")
        return

    method = data.get("deposit_method")
    
    invoice_url = ""
    invoice_id = ""
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            if method == "crypto":
                headers = {
                    "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
                    "User-Agent": DEFAULT_USER_AGENT
                }
                payload = {"asset": "USDT", "amount": str(amount)}
                async with session.post("https://pay.crypt.bot/api/createInvoice", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        resp_data = await resp.json()
                        if resp_data.get("ok"):
                            invoice_id = str(resp_data["result"]["invoice_id"])
                            invoice_url = resp_data["result"]["bot_invoice_url"]
                        else:
                            err_msg = html.escape(str(resp_data.get('error', 'Неизвестная ошибка')))
                            return await message.answer(f"<b>Ошибка API CryptoBot:</b> {err_msg}", parse_mode="HTML")
                    else:
                        return await message.answer(f"<b>HTTP Ошибка CryptoBot:</b> {resp.status}", parse_mode="HTML")

    except Exception as e:
        err_msg = html.escape(str(e))
        return await message.answer(f"<b>Ошибка соединения с платежной системой:</b>\n{err_msg}", parse_mode="HTML")

    PENDING_INVOICES[invoice_id] = {"user_id": message.from_user.id, "amount": amount, "method": method}
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить счет", url=invoice_url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_pay_{invoice_id}")]
    ])
    await message.answer(f"<b>Оплата на сумму</b> {amount} $\n<b>Перейдите по ссылке. После оплаты нажмите кнопку ниже.</b>", parse_mode="HTML", reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data.startswith("check_pay_"))
async def check_payment_handler(callback: CallbackQuery):
    invoice_id = callback.data.split("check_pay_")[1]
    if invoice_id not in PENDING_INVOICES:
        return await callback.answer("Счет не найден или уже оплачен.", show_alert=True)
    
    inv_data = PENDING_INVOICES[invoice_id]
    method = inv_data["method"]
    is_paid = False
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            if method == "crypto":
                headers = {
                    "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
                    "User-Agent": DEFAULT_USER_AGENT
                }
                async with session.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}", headers=headers) as resp:
                    if resp.status == 200:
                        resp_data = await resp.json()
                        if resp_data.get("ok") and resp_data["result"]["items"]:
                            if resp_data["result"]["items"][0]["status"] == "paid":
                                is_paid = True
    except Exception as e:
        logging.error(f"Ошибка при проверке платежа: {e}")
        
    if is_paid:
        user_id = inv_data["user_id"]
        amount = inv_data["amount"]
        user = get_or_create_user(user_id, " ")
        user["balance"] += amount
        user["deposits"] += amount
        del PENDING_INVOICES[invoice_id]
        
        await callback.message.edit_text(f"✅ <b>Платеж подтвержден! Баланс пополнен на</b> {amount} $.", parse_mode="HTML")
        await callback.answer()
    else:
        await callback.answer("Счет еще не оплачен.", show_alert=True)

async def handle_webhook(request):
    data = await request.json()
    if data.get("status") == "paid":
        user_id = data.get("user_id")
        amount = float(data.get("amount"))
        if user_id in USERS_DB:
            USERS_DB[user_id]["balance"] += amount
            USERS_DB[user_id]["deposits"] += amount
            await bot.send_message(user_id, f"✅ <b>Платеж подтвержден! +</b>{amount} $", parse_mode="HTML")
    return web.Response(status=200)

@dp.callback_query(F.data.in_({"withdraw_select_balance", "withdraw_select_profile"}))
async def select_withdraw_method(callback: CallbackQuery, state: FSMContext):
    source = callback.data.split("_")[-1]
    await state.update_data(return_to=source)
    
    back_cb = "back_to_balance" if source == "balance" else "profile"
    raw_inline_keyboard = [
        [{"text": "CryptoBot", "callback_data": "wd_method_crypto"}],
        [{"text": "< Назад", "callback_data": back_cb}]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=raw_inline_keyboard)
    await callback.message.edit_text(WITHDRAW_METHODS_TEXT, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("wd_method_"))
async def process_withdraw_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[-1]
    await state.update_data(withdraw_method=method)
    
    data = await state.get_data()
    back_cb = "back_to_balance" if data.get("return_to") == "balance" else "profile"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [{"text": "< Назад", "callback_data": back_cb}]
    ])
    await callback.message.edit_text("<b>Введите сумму вывода (от 1.1 $):</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(PaymentStates.waiting_for_withdraw_amount)
    await callback.answer()

@dp.message(PaymentStates.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    back_cb = "back_to_balance" if data.get("return_to") == "balance" else "profile"

    try:
        amount = float(message.text.replace(",", "."))
        if amount < 1.1:
            kb = InlineKeyboardMarkup(inline_keyboard=[[{"text": "< Назад", "callback_data": back_cb}]])
            await message.answer("<b>Сумма вывода должна быть от 1.1 $</b>", reply_markup=kb, parse_mode="HTML")
            return
    except ValueError:
        kb = InlineKeyboardMarkup(inline_keyboard=[[{"text": "< Назад", "callback_data": back_cb}]])
        await message.answer("<b>Пожалуйста, введите корректное число.</b>", reply_markup=kb, parse_mode="HTML")
        return

    user = get_or_create_user(message.from_user.id, message.from_user.full_name)
    
    if user["balance"] < amount:
        await message.answer("❌ <b>Недостаточно средств на балансе.</b>", parse_mode="HTML")
        await state.clear()
        return

    method = data.get("withdraw_method")
    
    user["balance"] -= amount
    req_id = random.randint(10000, 99999)
    WITHDRAW_REQUESTS[req_id] = {"user_id": message.from_user.id, "amount": amount, "method": method, "status": "pending"}
    
    await message.answer(f"✅ <b>Заявка #{req_id} создана и отправлена на проверку администратору.</b>", parse_mode="HTML")
    await state.clear()
    
    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Одобрить", callback_data=f"admin_approve_req_{req_id}")],
                [InlineKeyboardButton(text="Отклонить", callback_data=f"admin_reject_req_{req_id}")]
            ])
            await bot.send_message(admin_id, f"🚨 <b>Заявка #{req_id}</b>\n<b>От:</b> {message.from_user.id}\n<b>Сумма:</b> {amount} $\n<b>Способ:</b> {method}", reply_markup=kb, parse_mode="HTML")
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
    await message.answer("🔧 <b>Админ-панель:</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    total_users = len(USERS_DB)
    total_deps = sum(u["deposits"] for u in USERS_DB.values())
    total_wds = sum(u["withdrawals"] for u in USERS_DB.values())
    await callback.message.answer(f"📊 <b>Статистика:</b>\n<b>Пользователей:</b> {total_users}\n<b>Всего пополнений:</b> {total_deps} $\n<b>Всего выводов:</b> {total_wds} $", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("<b>Введите сообщение для рассылки:</b>", parse_mode="HTML")
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
    await message.answer(f"✅ <b>Рассылка завершена. Отправлено:</b> {count} <b>пользователям.</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "admin_deduct_bal")
async def admin_deduct_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("<b>Введите ID пользователя:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_deduct_id)
    await callback.answer()

@dp.message(AdminStates.waiting_for_deduct_id)
async def process_deduct_id(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("<b>ID должен быть числом.</b>", parse_mode="HTML")
    await state.update_data(deduct_user_id=int(message.text))
    await message.answer("<b>Введите сумму для списания:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_deduct_amount)

@dp.message(AdminStates.waiting_for_deduct_amount)
async def process_deduct_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError: return await message.answer("<b>Неверная сумма.</b>", parse_mode="HTML")
    data = await state.get_data()
    user_id = data.get("deduct_user_id")
    if user_id in USERS_DB:
        USERS_DB[user_id]["balance"] -= amount
        await message.answer(f"✅ <b>Списано</b> {amount} $ <b>у</b> {user_id}.", parse_mode="HTML")
    else: await message.answer("❌ <b>Пользователь не найден.</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "admin_withdraw_requests")
async def admin_show_requests(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    pending_reqs = [req_id for req_id, req in WITHDRAW_REQUESTS.items() if req["status"] == "pending"]
    if not pending_reqs: return await callback.answer("Нет активных заявок.", show_alert=True)
    for req_id in pending_reqs:
        req = WITHDRAW_REQUESTS[req_id]
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Одобрить", callback_data=f"admin_approve_req_{req_id}")], [InlineKeyboardButton(text="Отклонить", callback_data=f"admin_reject_req_{req_id}")]])
        await callback.message.answer(f"🚨 <b>Заявка #{req_id}</b>\n<b>Сумма:</b> {req['amount']} $\n<b>Способ:</b> {req['method']}\n<b>ID:</b> {req['user_id']}", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_approve_req_"))
async def admin_approve_req_inline(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[-1])
    if req_id not in WITHDRAW_REQUESTS or WITHDRAW_REQUESTS[req_id]["status"] != "pending":
        return await callback.answer("Заявка уже обработана.", show_alert=True)
        
    req = WITHDRAW_REQUESTS[req_id]
    amount = req["amount"]
    method = req["method"]
    target_user_id = int(req["user_id"])
    
    success = False
    error_text = ""
    
    await callback.message.edit_text(f"⏳ <b>Выполняю перевод по заявке #{req_id} через API...</b>", parse_mode="HTML")
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            if method == "crypto":
                headers = {
                    "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
                    "User-Agent": DEFAULT_USER_AGENT
                }
                payload = {
                    "user_id": target_user_id,
                    "asset": "USDT",
                    "amount": str(amount),
                    "spend_id": str(uuid.uuid4())
                }
                async with session.post("https://pay.crypt.bot/api/transfer", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        resp_data = await resp.json()
                        if resp_data.get("ok"):
                            success = True
                        else:
                            error_text = str(resp_data.get("error", resp_data))
                    else:
                        error_text = f"HTTP {resp.status}"

    except Exception as e:
        error_text = str(e)

    if success:
        req["status"] = "approved"
        USERS_DB[target_user_id]["withdrawals"] += amount
        await bot.send_message(target_user_id, f"✅ <b>Ваш вывод на сумму</b> {amount} $ <b>успешно зачислен на ваш кошелек!</b>", parse_mode="HTML")
        await callback.message.edit_text(f"✅ <b>Заявка #{req_id} одобрена, средства переведены по API.</b>", parse_mode="HTML")
    else:
        err_escaped = html.escape(error_text)
        await callback.message.edit_text(f"❌ <b>Ошибка API при переводе (#{req_id}).\nЛог:</b> <code>{err_escaped}</code>", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_reject_req_"))
async def admin_reject_req_inline(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[-1])
    if req_id not in WITHDRAW_REQUESTS or WITHDRAW_REQUESTS[req_id]["status"] != "pending":
        return await callback.answer("Заявка уже обработана.", show_alert=True)
        
    req = WITHDRAW_REQUESTS[req_id]
    req["status"] = "rejected"
    USERS_DB[req["user_id"]]["balance"] += req["amount"]
    await bot.send_message(req["user_id"], f"❌ <b>Вывод</b> {req['amount']} $ <b>отклонен, средства возвращены на баланс.</b>", parse_mode="HTML")
    await callback.message.edit_text(f"❌ <b>Заявка #{req_id} ОТКЛОНЕНА</b>", parse_mode="HTML")
    await callback.answer()

async def start_web_server():
    app = web.Application()
    app.router.add_post("/webhook", handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.gather(dp.start_polling(bot), start_web_server())

if __name__ == "__main__":
    asyncio.run(main())
