#!/usr/bin/env python3
""" 
GOLD BOT - Исправленная версия с правильной системой отзывов
"""

import asyncio
import logging
import json
import os
import random
import re
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
# ===================== FLASK ДЛЯ RENDER =====================
from flask import Flask, request as flask_request, jsonify
import threading

# Создаем Flask app (для UptimeRobot пинга)
flask_app = Flask(__name__)

@flask_app.route('/')
def flask_home():
    return "✅ Gold Bot is ALIVE! Ping me every 5-10 minutes.", 200

@flask_app.route('/health')
def flask_health():
    return "OK", 200

# Запускаем Flask в отдельном потоке
def run_flask():
    import os
    port = int(os.environ.get('PORT', 5000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8546640668:AAEVHTdr4Qw2-CVyQlnFFKsVyvuods5Pibo"
ADMIN_ID = 6086536190
ADMIN_USERNAME = "@Bahich_1"
HUMO_CARD = "9860 6067 4427 9617"
CARD_HOLDER = "R.M"

# Курсы
EXCHANGE_RATE = 150  # 150 сум = 1 голда
RUB_UZS_RATE = 170   # 1 RUB = 170 UZS
TON_FEE = 0.55
MIN_WITHDRAWAL = 100

# TON адрес
TON_WALLET = "UQCgVleFGU6aQUSyJ-8XNh52Igy9SBhq5jhEMK3PwDFvc0n8"
# =====================================================

# Файлы баз данных
USERS_FILE = "users.json"
ORDERS_GOLD_FILE = "orders_gold.json"
ORDERS_BP_FILE = "orders_bp.json"
ORDERS_STARS_FILE = "orders_stars.json"
ORDERS_SUBS_FILE = "orders_subs.json"
WITHDRAWALS_FILE = "withdrawals.json"
REVIEWS_FILE = "reviews.json"

# Состояния
class UserStates(StatesGroup):
    waiting_gold_amount = State()
    waiting_gold_receipt = State()
    waiting_withdraw_amount = State()
    
    waiting_bp_choice = State()
    waiting_bp_id = State()
    waiting_bp_receipt = State()
    
    waiting_stars_choice = State()
    waiting_stars_username = State()
    waiting_stars_receipt = State()
    
    waiting_sub_type = State()
    waiting_sub_choice = State()
    waiting_sub_phone = State()
    waiting_sub_username = State()
    waiting_sub_receipt = State()
    
    waiting_review_photo = State()
    waiting_review_text = State()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===================== УТИЛИТЫ =====================
def load_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки {filename}: {e}")
            return {}
    return {}

def save_data(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")

async def get_ton_rate():
    try:
        url = "https://api.coinbase.com/v2/prices/TON-RUB/spot"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return float(data['data']['amount'])
    except:
        return 114.79

async def calculate_ton_price(amount_sums):
    rub_amount = amount_sums / RUB_UZS_RATE
    ton_rate = await get_ton_rate()
    ton_amount = rub_amount / ton_rate
    total_ton = ton_amount + TON_FEE
    return round(total_ton, 3), round(ton_rate, 2)

def get_random_bonus():
    """Генерация случайного бонуса 1-5 голды"""
    chances = {
        1: 50,   # 50% шанс
        2: 23,   # 23% шанс
        3: 12,   # 12% шанс
        4: 10,   # 10% шанс
        5: 5     # 5% шанс
    }
    
    rand = random.randint(1, 100)
    cumulative = 0
    for amount, chance in chances.items():
        cumulative += chance
        if rand <= cumulative:
            return amount
    return 1

# Загрузка данных
users = load_data(USERS_FILE)
orders_gold = load_data(ORDERS_GOLD_FILE)
orders_bp = load_data(ORDERS_BP_FILE)
orders_stars = load_data(ORDERS_STARS_FILE)
orders_subs = load_data(ORDERS_SUBS_FILE)
withdrawals = load_data(WITHDRAWALS_FILE)
reviews = load_data(REVIEWS_FILE)

# ===================== КЛАВИАТУРЫ =====================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟡 Купить голду")],
            [KeyboardButton(text="🎫 Купить BP")],
            [KeyboardButton(text="⭐️ Telegram Stars")],
            [KeyboardButton(text="📅 Telegram Premium")],
            [KeyboardButton(text="💰 Мой баланс"), KeyboardButton(text="💸 Вывести голду")],
            [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 HUMO", callback_data="pay_humo")],
        [InlineKeyboardButton(text="💎 TON", callback_data="pay_ton")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
    ])

def get_bp_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💎 GOLD PASS - 128,490 сум")],
            [KeyboardButton(text="💎 GOLD PASS + - 212,490 сум")],
            [KeyboardButton(text="💎 1 LVL - 20,490 сум")],
            [InlineKeyboardButton(text="💎 10 LVL - 144,490 сум")],
            [KeyboardButton(text="💎 20 LVL - 254,490 сум")],
            [KeyboardButton(text="💎 45 LVL - 442,490 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_stars_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⭐️ 50 stars - 13,000 сум")],
            [KeyboardButton(text="⭐️ 100 stars - 25,000 сум")],
            [KeyboardButton(text="⭐️ 150 stars - 37,000 сум")],
            [KeyboardButton(text="⭐️ 350 stars - 86,000 сум")],
            [KeyboardButton(text="⭐️ 500 stars - 125,000 сум")],
            [KeyboardButton(text="⭐️ 750 stars - 180,000 сум")],
            [KeyboardButton(text="⭐️ 1000 stars - 240,000 сум")],
            [KeyboardButton(text="⭐️ 1500 stars - 360,000 сум")],
            [KeyboardButton(text="⭐️ 2500 stars - 600,000 сум")],
            [KeyboardButton(text="⭐️ 5000 stars - 1,200,000 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_subs_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Со входом в аккаунт")],
            [KeyboardButton(text="🎁 Без входа (подарочная)")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_sub_period_keyboard(sub_type):
    if sub_type == "with_login":
        keyboard = [
            [KeyboardButton(text="⭐ 1 месяц - 50,000 сум")],
            [KeyboardButton(text="⭐ 12 месяцев - 375,990 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ]
    else:
        keyboard = [
            [KeyboardButton(text="🎁 3 месяца - 170,000 сум")],
            [KeyboardButton(text="🎁 6 месяцев - 230,000 сум")],
            [KeyboardButton(text="🎁 12 месяцев - 400,000 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_withdrawal_keyboard(withdrawal_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Купить скин", callback_data=f"buy_skin_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_w_{withdrawal_id}")
        ]
    ])

def get_admin_ready_for_photo_keyboard(withdrawal_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Отправить фото скина", callback_data=f"send_skin_{withdrawal_id}")]
    ])

def get_admin_skin_purchased_keyboard(withdrawal_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Я купил скин у покупателя", callback_data=f"skin_purchased_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Проблема", callback_data=f"skin_problem_{withdrawal_id}")
        ]
    ])

def get_leave_review_keyboard(order_id, order_type="withdrawal"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Оставить отзыв", callback_data=f"leave_review_{order_type}_{order_id}")]
    ])

def get_admin_order_keyboard(order_id, order_type="gold"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order_type}_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_type}_{order_id}")
        ]
    ])

def get_admin_complete_keyboard(order_id, order_type="gold"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить заказ", callback_data=f"complete_{order_type}_{order_id}")]
    ])

# ===================== ОСНОВНЫЕ КОМАНДЫ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "orders_count": 0,
            "reviews_count": 0,
            "total_bonus": 0
        }
        save_data(users, USERS_FILE)
    
    welcome_text = f"""
🎮 Добро пожаловать в Gold Bot!

💰 Ваш баланс: {users[user_id]['balance']} голды

🟡 Купить голду - пополнить баланс
🎫 Купить BP - Battle Pass для игры
⭐️ Telegram Stars - звёзды для Telegram
📅 Telegram Premium - премиум подписка
💸 Вывести голду - обменять на скин

💎 Курс: {EXCHANGE_RATE} сум = 1 голда
💸 Минимальный вывод: {MIN_WITHDRAWAL} голды
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ===================== ПОКУПКА ГОЛДЫ =====================
@dp.message(F.text == "🟡 Купить голду")
async def buy_gold_start(message: types.Message, state: FSMContext):
    await message.answer(
        "💵 Введите сумму в сумах:\n\nПример: 30000",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_gold_amount)

@dp.message(UserStates.waiting_gold_amount, F.text)
async def process_gold_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        amount_sums = int(message.text.strip())
        if amount_sums < EXCHANGE_RATE:
            await message.answer(f"Минимальная сумма: {EXCHANGE_RATE} сум")
            return
        
        gold_amount = amount_sums // EXCHANGE_RATE
        ton_total, ton_rate = await calculate_ton_price(amount_sums)
        
        await state.update_data(
            amount_sums=amount_sums,
            gold_amount=gold_amount,
            ton_total=ton_total,
            ton_rate=ton_rate
        )
        
        await message.answer(
            f"💎 Расчёт:\n"
            f"{amount_sums} сум = {gold_amount} голды\n\n"
            f"Вы получите: {gold_amount} голды\n\n"
            f"Выберите способ оплаты:",
            reply_markup=get_payment_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ Введите число!\nПример: 30000")

# ===================== ПОКУПКА BP =====================
@dp.message(F.text == "🎫 Купить BP")
async def buy_bp_start(message: types.Message, state: FSMContext):
    await message.answer(
        "🎫 Выберите пакет BP:",
        reply_markup=get_bp_keyboard()
    )
    await state.set_state(UserStates.waiting_bp_choice)

@dp.message(UserStates.waiting_bp_choice, F.text)
async def process_bp_choice(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    bp_prices = {
        "💎 GOLD PASS - 128,490 сум": 128490,
        "💎 GOLD PASS + - 212,490 сум": 212490,
        "💎 1 LVL - 20,490 сум": 20490,
        "💎 10 LVL - 144,490 сум": 144490,
        "💎 20 LVL - 254,490 сум": 254490,
        "💎 45 LVL - 442,490 сум": 442490
    }
    
    if message.text not in bp_prices:
        await message.answer("❌ Выберите пакет из списка")
        return
    
    price = bp_prices[message.text]
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        bp_package=message.text,
        bp_price=price,
        ton_total=ton_total,
        ton_rate=ton_rate
    )
    
    await message.answer(
        "🎮 Введите ваш ID в игре (цифры):\n\n"
        "Это нужно для активации BP",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_bp_id)

@dp.message(UserStates.waiting_bp_id, F.text)
async def process_bp_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(game_id=message.text)
    data = await state.get_data()
    
    await message.answer(
        f"🎫 Пакет: {data['bp_package']}\n"
        f"💰 Цена: {data['bp_price']} сум\n"
        f"🆔 ID в игре: {data['game_id']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== TELEGRAM STARS =====================
@dp.message(F.text == "⭐️ Telegram Stars")
async def buy_stars_start(message: types.Message, state: FSMContext):
    await message.answer(
        "⭐️ Выберите пакет Stars:",
        reply_markup=get_stars_keyboard()
    )
    await state.set_state(UserStates.waiting_stars_choice)

@dp.message(UserStates.waiting_stars_choice, F.text)
async def process_stars_choice(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    stars_prices = {
        "⭐️ 50 stars - 13,000 сум": ("50 stars", 13000),
        "⭐️ 100 stars - 25,000 сум": ("100 stars", 25000),
        "⭐️ 150 stars - 37,000 сум": ("150 stars", 37000),
        "⭐️ 350 stars - 86,000 сум": ("350 stars", 86000),
        "⭐️ 500 stars - 125,000 сум": ("500 stars", 125000),
        "⭐️ 750 stars - 180,000 сум": ("750 stars", 180000),
        "⭐️ 1000 stars - 240,000 сум": ("1000 stars", 240000),
        "⭐️ 1500 stars - 360,000 сум": ("1500 stars", 360000),
        "⭐️ 2500 stars - 600,000 сум": ("2500 stars", 600000),
        "⭐️ 5000 stars - 1,200,000 сум": ("5000 stars", 1200000)
    }
    
    if message.text not in stars_prices:
        await message.answer("❌ Выберите пакет из списка")
        return
    
    package_name, price = stars_prices[message.text]
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        stars_package=package_name,
        stars_price=price,
        ton_total=ton_total,
        ton_rate=ton_rate
    )
    
    await message.answer(
        "📱 Введите юзернейм получателя (например @username):\n\n"
        "Stars будут отправлены этому пользователю",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_stars_username)

@dp.message(UserStates.waiting_stars_username, F.text)
async def process_stars_username(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if not message.text.startswith("@"):
        await message.answer("❌ Юзернейм должен начинаться с @\nПример: @username")
        return
    
    await state.update_data(stars_recipient=message.text)
    data = await state.get_data()
    
    await message.answer(
        f"⭐️ Пакет: {data['stars_package']}\n"
        f"💰 Цена: {data['stars_price']} сум\n"
        f"👤 Получатель: {data['stars_recipient']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== TELEGRAM PREMIUM =====================
@dp.message(F.text == "📅 Telegram Premium")
async def buy_subs_start(message: types.Message, state: FSMContext):
    await message.answer(
        "📅 Выберите тип подписки:",
        reply_markup=get_subs_keyboard()
    )
    await state.set_state(UserStates.waiting_sub_type)

@dp.message(UserStates.waiting_sub_type, F.text)
async def process_sub_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text not in ["📱 Со входом в аккаунт", "🎁 Без входа (подарочная)"]:
        await message.answer("❌ Выберите тип из списка")
        return
    
    sub_type = "with_login" if message.text == "📱 Со входом в аккаунт" else "gift"
    await state.update_data(sub_type=sub_type)
    
    await message.answer(
        "📅 Выберите срок подписки:",
        reply_markup=get_sub_period_keyboard(sub_type)
    )
    await state.set_state(UserStates.waiting_sub_choice)

@dp.message(UserStates.waiting_sub_choice, F.text)
async def process_sub_choice(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    sub_type = data['sub_type']
    
    if sub_type == "with_login":
        sub_prices = {
            "⭐ 1 месяц - 50,000 сум": ("1 месяц", 50000),
            "⭐ 12 месяцев - 375,990 сум": ("12 месяцев", 375990)
        }
    else:
        sub_prices = {
            "🎁 3 месяца - 170,000 сум": ("3 месяца", 170000),
            "🎁 6 месяцев - 230,000 сум": ("6 месяцев", 230000),
            "🎁 12 месяцев - 400,000 сум": ("12 месяцев", 400000)
        }
    
    if message.text not in sub_prices:
        await message.answer("❌ Выберите срок из списка")
        return
    
    period, price = sub_prices[message.text]
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        sub_period=period,
        sub_price=price,
        ton_total=ton_total,
        ton_rate=ton_rate
    )
    
    if sub_type == "with_login":
        await message.answer(
            "📱 Введите номер телефона аккаунта:\n\n"
            "Пример: +998901234567",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_phone)
    else:
        await message.answer(
            "👤 Введите юзернейм получателя (например @username):\n\n"
            "Подарочная ссылка будет отправлена этому пользователю",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_username)

@dp.message(UserStates.waiting_sub_phone, F.text)
async def process_sub_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if not message.text.startswith("+"):
        await message.answer("❌ Введите номер в формате +998901234567")
        return
    
    await state.update_data(phone_number=message.text)
    data = await state.get_data()
    
    instructions = (
        "⚠️ **Перед оплатой подготовьте аккаунт:**\n"
        "1. Будьте онлайн в Telegram\n"
        "2. Включите уведомления от бота @Gold_stars_prem_donatuzbbot\n"
        "3. Отключите двухфакторную аутентификацию (если включена)\n\n"
    )
    
    await message.answer(
        f"{instructions}"
        f"📅 Подписка: Telegram Premium\n"
        f"📱 Тип: Со входом в аккаунт\n"
        f"⏳ Срок: {data['sub_period']}\n"
        f"💰 Цена: {data['sub_price']} сум\n"
        f"📞 Телефон: {data['phone_number']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(UserStates.waiting_sub_username, F.text)
async def process_sub_username(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if not message.text.startswith("@"):
        await message.answer("❌ Юзернейм должен начинаться с @\nПример: @username")
        return
    
    await state.update_data(gift_recipient=message.text)
    data = await state.get_data()
    
    await message.answer(
        f"📅 Подписка: Telegram Premium\n"
        f"🎁 Тип: Подарочная (без входа)\n"
        f"⏳ Срок: {data['sub_period']}\n"
        f"💰 Цена: {data['sub_price']} сум\n"
        f"👤 Получатель: {data['gift_recipient']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== ОПЛАТА =====================
@dp.callback_query(F.data == "pay_humo")
async def show_humo_details(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    if 'gold_amount' in data:
        amount_sums = data['amount_sums']
        details = f"Получите: {data['gold_amount']} голды"
    elif 'bp_package' in data:
        amount_sums = data['bp_price']
        details = f"Пакет: {data['bp_package']}\nID игры: {data.get('game_id', 'не указан')}"
    elif 'stars_package' in data:
        amount_sums = data['stars_price']
        details = f"Пакет: {data['stars_package']}\nПолучатель: {data.get('stars_recipient', 'не указан')}"
    elif 'sub_period' in data:
        amount_sums = data['sub_price']
        if data['sub_type'] == "with_login":
            details = f"Тип: Со входом\nСрок: {data['sub_period']}\nТелефон: {data.get('phone_number', 'не указан')}"
        else:
            details = f"Тип: Подарочная\nСрок: {data['sub_period']}\nПолучатель: {data.get('gift_recipient', 'не указан')}"
    else:
        await callback.answer("❌ Ошибка данных")
        return
    
    payment_text = f"""
💳 ОПЛАТА HUMO

🏦 Номер карты: {HUMO_CARD}
👤 Владелец: {CARD_HOLDER}
💰 Сумма: {amount_sums} сум

📋 Детали:
{details}

📋 Инструкция:
1. Переведите {amount_sums} сум на карту выше
2. Сделайте скриншот чека об оплате
3. Отправьте скриншот в этот чат
"""
    
    await callback.message.edit_text(payment_text, parse_mode="Markdown")
    await state.set_state(UserStates.waiting_gold_receipt)
    await callback.answer()

@dp.callback_query(F.data == "pay_ton")
async def show_ton_details(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    if 'gold_amount' in data:
        amount_sums = data['amount_sums']
        details = f"Получите: {data['gold_amount']} голды"
        ton_total = data['ton_total']
    elif 'bp_package' in data:
        amount_sums = data['bp_price']
        details = f"Пакет: {data['bp_package']}\nID игры: {data.get('game_id', 'не указан')}"
        ton_total = data['ton_total']
    elif 'stars_package' in data:
        amount_sums = data['stars_price']
        details = f"Пакет: {data['stars_package']}\nПолучатель: {data.get('stars_recipient', 'не указан')}"
        ton_total = data['ton_total']
    elif 'sub_period' in data:
        amount_sums = data['sub_price']
        if data['sub_type'] == "with_login":
            details = f"Тип: Со входом\nСрок: {data['sub_period']}\nТелефон: {data.get('phone_number', 'не указан')}"
        else:
            details = f"Тип: Подарочная\nСрок: {data['sub_period']}\nПолучатель: {data.get('gift_recipient', 'не указан')}"
        ton_total = data['ton_total']
    else:
        await callback.answer("❌ Ошибка данных")
        return
    
    payment_text = f"""
💎 ОПЛАТА TON

💰 Сумма: {amount_sums} сум

📋 Детали:
{details}

💎 ИТОГ к оплате: {ton_total} TON

🏦 Адрес TON: {TON_WALLET}

📋 Инструкция:
1. Переведите {ton_total} TON на адрес выше
2. Сделайте скриншот транзакции
3. Отправьте скриншот в этот чат
"""
    
    await callback.message.edit_text(payment_text, parse_mode="Markdown")
    await state.set_state(UserStates.waiting_gold_receipt)
    await callback.answer()

# ===================== ОБРАБОТКА ЧЕКОВ =====================
@dp.message(UserStates.waiting_gold_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = await state.get_data()
    
    if 'gold_amount' in data:
        await process_gold_receipt(message, state, user_id, data)
    elif 'bp_package' in data:
        await process_bp_receipt(message, state, user_id, data)
    elif 'stars_package' in data:
        await process_stars_receipt(message, state, user_id, data)
    elif 'sub_period' in data:
        await process_sub_receipt(message, state, user_id, data)
    else:
        await message.answer("❌ Ошибка данных")
        await state.clear()

async def process_gold_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    order_id = datetime.now().strftime("G%Y%m%d%H%M%S")
    
    orders_gold[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "amount_sums": data['amount_sums'],
        "gold_amount": data['gold_amount'],
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "gold",
        "review_requested": False
    }
    save_data(orders_gold, ORDERS_GOLD_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "gold")
    await state.clear()

async def process_bp_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    order_id = datetime.now().strftime("B%Y%m%d%H%M%S")
    
    orders_bp[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "bp_package": data['bp_package'],
        "price": data['bp_price'],
        "game_id": data.get('game_id', 'не указан'),
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "bp",
        "review_requested": False
    }
    save_data(orders_bp, ORDERS_BP_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "bp")
    await state.clear()

async def process_stars_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    order_id = datetime.now().strftime("S%Y%m%d%H%M%S")
    
    orders_stars[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "stars_package": data['stars_package'],
        "price": data['stars_price'],
        "recipient": data.get('stars_recipient', 'не указан'),
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "stars",
        "review_requested": False
    }
    save_data(orders_stars, ORDERS_STARS_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "stars")
    await state.clear()

async def process_sub_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    order_id = datetime.now().strftime("P%Y%m%d%H%M%S")
    
    orders_subs[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "sub_type": data['sub_type'],
        "sub_period": data['sub_period'],
        "price": data['sub_price'],
        "phone_number": data.get('phone_number'),
        "recipient": data.get('gift_recipient'),
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "sub",
        "review_requested": False
    }
    save_data(orders_subs, ORDERS_SUBS_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "sub")
    await state.clear()

async def notify_admin_about_order(order_id: str, order_type: str):
    if order_type == "gold":
        order = orders_gold.get(order_id)
        emoji = "🟡"
        product_info = f"Голда: {order['gold_amount']} голды\nСумма: {order['amount_sums']} сум"
    elif order_type == "bp":
        order = orders_bp.get(order_id)
        emoji = "🎫"
        product_info = f"Пакет: {order['bp_package']}\nЦена: {order['price']} сум\nID игры: {order.get('game_id', 'не указан')}"
    elif order_type == "stars":
        order = orders_stars.get(order_id)
        emoji = "⭐️"
        product_info = f"Пакет: {order['stars_package']}\nЦена: {order['price']} сум\nПолучатель: {order.get('recipient', 'не указан')}"
    elif order_type == "sub":
        order = orders_subs.get(order_id)
        emoji = "📅"
        sub_type_ru = "Со входом" if order['sub_type'] == "with_login" else "Подарочная"
        product_info = f"Тип: {sub_type_ru}\nСрок: {order['sub_period']}\nЦена: {order['price']} сум"
        if order['sub_type'] == "with_login":
            product_info += f"\nТелефон: {order.get('phone_number', 'не указан')}"
        else:
            product_info += f"\nПолучатель: {order.get('recipient', 'не указан')}"
    else:
        return
    
    admin_text = f"""
{emoji} НОВЫЙ ЗАКАЗ!

📊 Информация:
ID: {order_id}
Тип: {order_type}
Пользователь: {order['user_name']}
Username: {order['username']}
ID: {order['user_id']}

📦 Детали:
{product_info}

⏰ Время: {order['created_at']}
"""
    
    try:
        await bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="Markdown",
            reply_markup=get_admin_order_keyboard(order_id, order_type)
        )
        
        await bot.send_photo(
            ADMIN_ID,
            photo=order['receipt_photo_id'],
            caption=f"📸 Чек для заказа {order_id}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")

# ===================== БАЛАНС =====================
@dp.message(F.text == "💰 Мой баланс")
async def show_balance(message: types.Message):
    user_id = str(message.from_user.id)
    balance = users.get(user_id, {}).get('balance', 0)
    await message.answer(f"💰 Ваш баланс: {balance} голды")

# ===================== ВЫВОД ГОЛДЫ =====================
@dp.message(F.text == "💸 Вывести голду")
async def withdraw_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    balance = users.get(user_id, {}).get('balance', 0)
    
    if balance < MIN_WITHDRAWAL:
        await message.answer(
            f"❌ Недостаточно голды!\n"
            f"Минимум: {MIN_WITHDRAWAL} голды\n"
            f"Ваш баланс: {balance} голды"
        )
        return
    
    await message.answer(
        f"💸 Вывод голды\n\n"
        f"💰 Ваш баланс: {balance} голды\n"
        f"📊 Минимум: {MIN_WITHDRAWAL} голды\n\n"
        f"Введите сумму для вывода:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_withdraw_amount)

@dp.message(UserStates.waiting_withdraw_amount, F.text)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    user_id = str(message.from_user.id)
    balance = users[user_id]['balance']
    
    try:
        withdraw_amount = int(message.text.strip())
        
        if withdraw_amount < MIN_WITHDRAWAL:
            await message.answer(f"❌ Минимум: {MIN_WITHDRAWAL} голды")
            return
        if withdraw_amount > balance:
            await message.answer(f"❌ Недостаточно голды!\nВаш баланс: {balance} голды")
            return
        
        # Списываем голду
        users[user_id]['balance'] -= withdraw_amount
        save_data(users, USERS_FILE)
        
        # Создаем запрос на вывод
        withdrawal_id = datetime.now().strftime("W%Y%m%d%H%M%S")
        withdrawals[withdrawal_id] = {
            "withdrawal_id": withdrawal_id,
            "user_id": user_id,
            "user_name": message.from_user.full_name,
            "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
            "amount": withdraw_amount,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "skin_price": None,
            "skin_photo_id": None,
            "buyer_screenshot_id": None,
            "admin_awaiting_photo": False,
            "buyer_awaiting_screenshot": False,
            "review_requested": False,
            "review_completed": False
        }
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        await message.answer(
            f"✅ Запрос на вывод {withdraw_amount} голды отправлен!\n"
            f"💰 Новый баланс: {users[user_id]['balance']} голды\n\n"
            f"⏳ Ожидайте, когда админ купит скин и отправит вам фото.",
            reply_markup=get_main_keyboard()
        )
        
        # Уведомляем админа
        admin_text = f"""
💸 НОВЫЙ ЗАПРОС НА ВЫВОД!

👤 Пользователь: {withdrawals[withdrawal_id]['user_name']}
📱 Username: {withdrawals[withdrawal_id]['username']}
🆔 ID: {user_id}

💰 Сумма: {withdraw_amount} голды
📋 ID вывода: {withdrawal_id}
⏰ Время: {datetime.now().strftime('%H:%M:%S')}

🛒 Купите скин на рынке и отправьте фото покупателю!
"""
        
        try:
            await bot.send_message(
                ADMIN_ID,
                admin_text,
                parse_mode="Markdown",
                reply_markup=get_admin_withdrawal_keyboard(withdrawal_id)
            )
            logger.info(f"✅ Уведомление отправлено админу {ADMIN_ID} о выводе {withdrawal_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки админу: {e}")
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число!\nПример: 100")

# ===================== ШАГ 1: АДМИН ПОКУПАЕТ СКИН =====================
@dp.callback_query(F.data.startswith("buy_skin_"))
async def admin_buy_skin(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    withdrawal_id = callback.data.split("_")[2]
    withdrawal = withdrawals.get(withdrawal_id)
    
    if not withdrawal:
        await callback.answer("Запрос не найден!")
        return
    
    withdrawals[withdrawal_id]['status'] = "admin_buying"
    withdrawals[withdrawal_id]['admin_bought_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    await callback.message.edit_text(
        f"🛒 ВЫ КУПИЛИ СКИН!\n\n"
        f"👤 Для: {withdrawal['user_name']}\n"
        f"💰 Сумма: {withdrawal['amount']} голды\n"
        f"📋 ID: {withdrawal_id}\n\n"
        f"📸 Теперь отправьте фото этого скина покупателю!\n\n"
        f"В подписи к фото укажите точную цену и описание\n"
        f"💡 Пример: '125.24 с 2 наклейками'",
        reply_markup=get_admin_ready_for_photo_keyboard(withdrawal_id)
    )
    await callback.answer("📸 Теперь отправьте фото скина...")

# ===================== ШАГ 2: АДМИН ОТПРАВЛЯЕТ ФОТО СКИНА =====================
@dp.callback_query(F.data.startswith("send_skin_"))
async def admin_send_skin(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    withdrawal_id = callback.data.split("_")[2]
    withdrawal = withdrawals.get(withdrawal_id)
    
    if not withdrawal:
        await callback.answer("Запрос не найден!")
        return
    
    withdrawals[withdrawal_id]['admin_awaiting_photo'] = True
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    await callback.message.edit_text(
        f"📸 ОТПРАВЬТЕ ФОТО СКИНА\n\n"
        f"Отправьте скриншот скина в этот чат.\n"
        f"Укажите в подписи точную цену и описание.\n\n"
        f"💡 Пример: '125.24 с 2 наклейками'\n\n"
        f"ID вывода: {withdrawal_id}"
    )
    await callback.answer("Отправьте фото...")

@dp.message(F.from_user.id == ADMIN_ID, F.photo)
async def handle_admin_photo(message: types.Message):
    logger.info(f"Админ отправил фото. ID сообщения: {message.message_id}")
    
    # Ищем активный вывод, ожидающий фото
    withdrawal_id = None
    for w_id, withdrawal in withdrawals.items():
        if withdrawal.get('admin_awaiting_photo') and withdrawal['status'] == 'admin_buying':
            withdrawal_id = w_id
            logger.info(f"Найден вывод для фото: {w_id}")
            break
    
    if not withdrawal_id:
        logger.warning("Не найден активный вывод для фото от админа")
        return
    
    withdrawal = withdrawals[withdrawal_id]
    
    # Сохраняем фото
    withdrawals[withdrawal_id]['skin_photo_id'] = message.photo[-1].file_id
    withdrawals[withdrawal_id]['admin_awaiting_photo'] = False
    withdrawals[withdrawal_id]['status'] = 'skin_sent_to_buyer'
    
    # Сохраняем ПОДЛИННЫЙ ТЕКСТ ПОДПИСИ
    skin_price = message.caption or f"{withdrawal['amount']} голды"
    withdrawals[withdrawal_id]['skin_price'] = skin_price
    withdrawals[withdrawal_id]['skin_sent_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    logger.info(f"Фото сохранено для вывода {withdrawal_id}. Цена: {skin_price}")
    
    # Отправляем фото покупателю с ТОЧНОЙ ценой из подписи
    try:
        logger.info(f"Пытаюсь отправить фото покупателю {withdrawal['user_id']}")
        
        await bot.send_photo(
            withdrawal['user_id'],
            photo=message.photo[-1].file_id,
            caption=f"""🎮 АДМИН КУПИЛ ДЛЯ ВАС СКИН!

💰 Сумма вывода: {withdrawal['amount']} голды
💲 Цена скина: {skin_price}
📋 ID вывода: {withdrawal_id}

📋 **ВАША ЗАДАЧА:**
1. **КУПИТЕ ЭТОТ СКИН** на рынке который на фото
2. **ВЫСТАВЬТЕ ЕГО ОБРАТНО** за ТОЧНО ТАКУЮ ЖЕ ЦЕНУ ({skin_price})
3. **СДЕЛАЙТЕ СКРИНШОТ** выставленного скина
4. **ОТПРАВЬТЕ СКРИНШОТ** в этот чат

⚠️ **ВАЖНО:**
• Купите именно этот скин который на фото
• Выставьте за ТОЧНО ТАКУЮ ЖЕ ЦЕНУ ({skin_price})
• Не меняйте цену после выставления!"""
        )
        
        logger.info(f"✅ Фото отправлено покупателю {withdrawal['user_id']}")
        
        # Обновляем статус
        withdrawals[withdrawal_id]['buyer_awaiting_screenshot'] = True
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        # Уведомляем админа
        await message.answer(
            f"✅ Фото отправлено покупателю!\n\n"
            f"👤 Покупатель: {withdrawal['user_name']}\n"
            f"💰 Сумма: {withdrawal['amount']} голды\n"
            f"💲 Цена: {skin_price}\n"
            f"📋 ID: {withdrawal_id}\n\n"
            f"⏳ Ожидайте скриншот от покупателя..."
        )
        
    except Exception as e:
        error_msg = f"❌ Ошибка отправки фото покупателю: {e}"
        logger.error(error_msg)
        await message.answer(error_msg)

# ===================== ШАГ 3: ПОКУПАТЕЛЬ ОТПРАВЛЯЕТ СКРИНШОТ ВЫСТАВЛЕННОГО СКИНА =====================
@dp.message(F.photo)
async def handle_buyer_photo(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    logger.info(f"Пользователь {user_id} отправил фото")
    
    # Проверяем, не админ ли это
    if str(message.from_user.id) == str(ADMIN_ID):
        return
    
    # ПРОВЕРЯЕМ: Может это фото для отзыва?
    current_state = await state.get_state()
    logger.info(f"Текущее состояние пользователя: {current_state}")
    
    if current_state == UserStates.waiting_review_photo:
        logger.info("Это фото для отзыва, обрабатываем...")
        # Сохраняем фото для отзыва
        await state.update_data(review_photo_id=message.photo[-1].file_id)
        await message.answer(
            "✅ Фото получено!\n\n"
            "📝 Теперь напишите текст отзыва:"
        )
        await state.set_state(UserStates.waiting_review_text)
        return
    
    # Ищем активный вывод для этого пользователя
    withdrawal_id = None
    for w_id, withdrawal in withdrawals.items():
        if (withdrawal['user_id'] == user_id and 
            withdrawal.get('buyer_awaiting_screenshot') and
            withdrawal['status'] == 'skin_sent_to_buyer'):
            withdrawal_id = w_id
            logger.info(f"Найден активный вывод для скриншота: {withdrawal_id}")
            break
    
    if not withdrawal_id:
        logger.warning(f"Не найден активный вывод для пользователя {user_id}")
        await message.answer("❌ У вас нет активных запросов на вывод.")
        return
    
    withdrawal = withdrawals[withdrawal_id]
    
    # Получаем ПРАВИЛЬНУЮ цену из записи
    skin_price = withdrawal.get('skin_price', f"{withdrawal['amount']} голды")
    
    # Сохраняем скриншот покупателя
    withdrawals[withdrawal_id]['buyer_screenshot_id'] = message.photo[-1].file_id
    withdrawals[withdrawal_id]['buyer_awaiting_screenshot'] = False
    withdrawals[withdrawal_id]['status'] = 'awaiting_admin_purchase'
    withdrawals[withdrawal_id]['buyer_screenshot_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    # Уведомляем покупателя с ПРАВИЛЬНОЙ ценой
    await message.answer(
        f"✅ Скриншот получен!\n\n"
        f"⚠️ **ВАЖНО: НЕ УБИРАЙТЕ СКИН С РЫНКА!**\n\n"
        f"📋 ID вывода: {withdrawal_id}\n"
        f"💰 Сумма: {withdrawal['amount']} голды\n"
        f"💲 Цена скина: {skin_price}\n\n"
        f"Админ купит скин в ближайшее время.\n"
        f"Спасибо за ожидание! 🙏"
    )
    
    logger.info(f"✅ Скриншот сохранен для вывода {withdrawal_id}")
    
    # Уведомляем админа
    admin_text = f"""
📸 ПОКУПАТЕЛЬ ВЫСТАВИЛ СКИН!

👤 Покупатель: {withdrawal['user_name']}
📱 {withdrawal['username']}

💰 Сумма вывода: {withdrawal['amount']} голды
💲 Цена скина: {skin_price}
📋 ID вывода: {withdrawal_id}

✏️ Подпись: {message.caption or 'Нет подписи'}

⏰ Время: {datetime.now().strftime('%H:%M:%S')}

⚠️ **ПОКУПАТЕЛЬ ПРЕДУПРЕЖДЕН:**
• Не убирать скин с рынка
• Не менять цену ({skin_price})
• Не менять аватарку профиля

🛒 **Теперь купите этот скин у покупателя!**
После покупки нажмите кнопку ниже:
"""
    
    try:
        await bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="Markdown",
            reply_markup=get_admin_skin_purchased_keyboard(withdrawal_id)
        )
        
        # Отправляем фото от покупателя админу
        await bot.send_photo(
            ADMIN_ID,
            photo=message.photo[-1].file_id,
            caption=f"📸 Скриншот выставленного скина {withdrawal_id}"
        )
        
        logger.info(f"✅ Уведомление отправлено админу о скриншоте {withdrawal_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка уведомления админа: {e}")

# ===================== ШАГ 4: АДМИН ПОДТВЕРЖДАЕТ ПОКУПКУ =====================
@dp.callback_query(F.data.startswith("skin_purchased_"))
async def admin_confirm_purchase(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    withdrawal_id = callback.data.split("_")[2]
    withdrawal = withdrawals.get(withdrawal_id)
    
    if not withdrawal:
        await callback.answer("Запрос не найден!")
        return
    
    # Получаем правильную цену скина
    skin_price = withdrawal.get('skin_price', f"{withdrawal['amount']} голды")
    
    # Обновляем статус
    withdrawals[withdrawal_id]['status'] = "completed"
    withdrawals[withdrawal_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    withdrawals[withdrawal_id]['admin_purchased_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    # Отправляем завершение покупателю с предложением оставить отзыв
    try:
        await bot.send_message(
            withdrawal['user_id'],
            f"""🎉 **ВАШ ЗАКАЗ УСПЕШНО ВЫПОЛНЕН!**

✅ Админ успешно купил ваш скин!

📋 **Детали вывода:**
• Сумма: {withdrawal['amount']} голды
• Цена скина: {skin_price}
• ID вывода: {withdrawal_id}
• Время завершения: {datetime.now().strftime('%H:%M:%S')}

💎 **ОСТАВЬТЕ ОТЗЫВ И ПОЛУЧИТЕ БОНУС!**
За отзыв о выводе голды вы можете получить случайный бонус!
Нажмите кнопку ниже 👇""",
            reply_markup=get_leave_review_keyboard(withdrawal_id, "withdrawal")
        )
        
        logger.info(f"✅ Завершение отправлено покупателю {withdrawal['user_id']}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки завершения: {e}")
    
    # Обновляем сообщение админу
    await callback.message.edit_text(
        f"✅ **СКИН КУПЛЕН И ЗАКАЗ ЗАВЕРШЕН**\n\n"
        f"👤 Покупатель: {withdrawal['user_name']}\n"
        f"💰 Сумма: {withdrawal['amount']} голды\n"
        f"💲 Цена: {skin_price}\n"
        f"📋 ID: {withdrawal_id}\n"
        f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"✅ Покупатель уведомлен о завершении.\n"
        f"✅ Предложено оставить отзыв (может получить бонус)."
    )
    await callback.answer("✅ Заказ завершен!")

# ===================== ОТМЕНА ВЫВОДА =====================
@dp.callback_query(F.data.startswith("reject_w_"))
async def admin_reject_withdrawal(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    withdrawal_id = callback.data.split("_")[2]
    withdrawal = withdrawals.get(withdrawal_id)
    
    if not withdrawal:
        await callback.answer("Запрос не найден!")
        return
    
    # Возвращаем голду
    user_id = withdrawal['user_id']
    if user_id in users:
        users[user_id]['balance'] += withdrawal['amount']
        save_data(users, USERS_FILE)
    
    # Обновляем статус
    withdrawals[withdrawal_id]['status'] = "rejected"
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    # Уведомляем покупателя
    try:
        await bot.send_message(
            user_id,
            f"❌ **ВЫВОД ОТКЛОНЕН**\n\n"
            f"💰 Сумма: {withdrawal['amount']} голды\n"
            f"📋 ID: {withdrawal_id}\n\n"
            f"✅ Голда возвращена на ваш баланс.\n"
            f"📞 По вопросам: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"❌ ВЫВОД ОТКЛОНЕН\n\n"
        f"ID: {withdrawal_id}\n"
        f"Голда возвращена покупателю"
    )
    await callback.answer("❌ Отклонено!")

# ===================== АДМИНСКИЕ ОБРАБОТЧИКИ ДЛЯ ЗАКАЗОВ =====================
@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve_order(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных")
        return
    
    order_type = parts[1]
    order_id = parts[2]
    
    if order_type == "gold":
        await approve_gold_order(callback, order_id)
    elif order_type == "bp":
        await approve_bp_order(callback, order_id)
    elif order_type == "stars":
        await approve_stars_order(callback, order_id)
    elif order_type == "sub":
        await approve_sub_order(callback, order_id)
    else:
        await callback.answer("❌ Неизвестный тип заказа")

async def approve_gold_order(callback: types.CallbackQuery, order_id: str):
    order = orders_gold.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    user_id = order['user_id']
    gold_amount = order['gold_amount']
    
    if user_id in users:
        users[user_id]['balance'] = users[user_id].get('balance', 0) + gold_amount
        users[user_id]['orders_count'] = users[user_id].get('orders_count', 0) + 1
        save_data(users, USERS_FILE)
    
    orders_gold[order_id]['status'] = "approved"
    orders_gold[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_gold, ORDERS_GOLD_FILE)
    
    try:
        await bot.send_message(
            user_id,
            f"✅ Заказ подтвержден!\n\n"
            f"Начислено: {gold_amount} голды\n"
            f"ID заказа: {order_id}\n"
            f"💰 Баланс: {users[user_id]['balance']} голды"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Голда\n"
        f"Пользователь: {order['user_name']}\n"
        f"Сумма: {gold_amount} голды\n\n"
        f"Баланс пользователя обновлен",
        reply_markup=get_admin_complete_keyboard(order_id, "gold")
    )
    await callback.answer("✅ Подтверждено!")

async def approve_bp_order(callback: types.CallbackQuery, order_id: str):
    order = orders_bp.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_bp[order_id]['status'] = "approved"
    orders_bp[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_bp, ORDERS_BP_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ Заказ BP подтвержден!\n\n"
            f"Пакет: {order['bp_package']}\n"
            f"ID заказа: {order_id}\n"
            f"🆔 ID в игре: {order.get('game_id', 'не указан')}\n\n"
            f"Админ активирует BP в ближайшее время"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: BP\n"
        f"Пользователь: {order['user_name']}\n"
        f"Пакет: {order['bp_package']}\n"
        f"ID игры: {order.get('game_id', 'не указан')}\n\n"
        f"Пользователь уведомлен",
        reply_markup=get_admin_complete_keyboard(order_id, "bp")
    )
    await callback.answer("✅ Подтверждено!")

async def approve_stars_order(callback: types.CallbackQuery, order_id: str):
    order = orders_stars.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_stars[order_id]['status'] = "approved"
    orders_stars[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_stars, ORDERS_STARS_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ Заказ Stars подтвержден!\n\n"
            f"Пакет: {order['stars_package']}\n"
            f"ID заказа: {order_id}\n"
            f"👤 Получатель: {order.get('recipient', 'не указан')}\n\n"
            f"Админ отправит Stars в ближайшее время"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Stars\n"
        f"Пользователь: {order['user_name']}\n"
        f"Пакет: {order['stars_package']}\n"
        f"Получатель: {order.get('recipient', 'не указан')}\n\n"
        f"Пользователь уведомлен",
        reply_markup=get_admin_complete_keyboard(order_id, "stars")
    )
    await callback.answer("✅ Подтверждено!")

async def approve_sub_order(callback: types.CallbackQuery, order_id: str):
    order = orders_subs.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_subs[order_id]['status'] = "approved"
    orders_subs[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_subs, ORDERS_SUBS_FILE)
    
    sub_type_ru = "Со входом в аккаунт" if order['sub_type'] == "with_login" else "Подарочная"
    
    try:
        message_text = f"✅ Заказ подписки подтвержден!\n\n"
        message_text += f"Тип: {sub_type_ru}\n"
        message_text += f"Срок: {order['sub_period']}\n"
        message_text += f"ID заказа: {order_id}\n\n"
        
        if order['sub_type'] == "with_login":
            message_text += f"📱 Телефон: {order.get('phone_number', 'не указан')}\n"
            message_text += "Подготовьте аккаунт:\n"
            message_text += "1. Будьте онлайн\n"
            message_text += "2. Включите уведомления от @Gold_stars_prem_donatuzbbot\n"
            message_text += "3. Отключите 2FA (если включена)\n\n"
        else:
            message_text += f"👤 Получатель: {order.get('recipient', 'не указан')}\n"
            message_text += "Подарочная ссылка будет отправлена получателю\n\n"
        
        await bot.send_message(order['user_id'], message_text)
    except:
        pass
    
    admin_text = f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\nID: {order_id}\nТип: Подписка\n"
    admin_text += f"Пользователь: {order['user_name']}\nТип: {sub_type_ru}\n"
    admin_text += f"Срок: {order['sub_period']}\n\nПользователь уведомлен"
    
    await callback.message.edit_text(
        admin_text,
        reply_markup=get_admin_complete_keyboard(order_id, "sub")
    )
    await callback.answer("✅ Подтверждено!")

@dp.callback_query(F.data.startswith("complete_"))
async def admin_complete_order(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных")
        return
    
    order_type = parts[1]
    order_id = parts[2]
    
    if order_type == "gold":
        await complete_gold_order(callback, order_id)
    elif order_type == "bp":
        await complete_bp_order(callback, order_id)
    elif order_type == "stars":
        await complete_stars_order(callback, order_id)
    elif order_type == "sub":
        await complete_sub_order(callback, order_id)
    else:
        await callback.answer("❌ Неизвестный тип заказа")

async def complete_gold_order(callback: types.CallbackQuery, order_id: str):
    order = orders_gold.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_gold[order_id]['status'] = "completed"
    orders_gold[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_gold, ORDERS_GOLD_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"""🎉 Заказ выполнен!

✅ Спасибо за покупку голды!

💰 Сумма: {order['gold_amount']} голды
📋 ID заказа: {order_id}

🙏 **Пожалуйста, оставьте отзыв о нашей работе!**
Нажмите кнопку ниже 👇""",
            reply_markup=get_leave_review_keyboard(order_id, "gold")
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Голда\n"
        f"Пользователь получил уведомление и предложение оставить отзыв"
    )
    await callback.answer("✅ Завершено!")

async def complete_bp_order(callback: types.CallbackQuery, order_id: str):
    order = orders_bp.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_bp[order_id]['status'] = "completed"
    orders_bp[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_bp, ORDERS_BP_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"""🎉 Заказ выполнен!

✅ Спасибо за покупку BP!

🎮 Пакет: {order['bp_package']}
📋 ID заказа: {order_id}

🙏 **Пожалуйста, оставьте отзыв о нашей работе!**
Нажмите кнопку ниже 👇""",
            reply_markup=get_leave_review_keyboard(order_id, "bp")
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: BP\n"
        f"Пользователь получил уведомление и предложение оставить отзыв"
    )
    await callback.answer("✅ Завершено!")

async def complete_stars_order(callback: types.CallbackQuery, order_id: str):
    order = orders_stars.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_stars[order_id]['status'] = "completed"
    orders_stars[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_stars, ORDERS_STARS_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"""🎉 Заказ выполнен!

✅ Спасибо за покупку Stars!

⭐️ Пакет: {order['stars_package']}
📋 ID заказа: {order_id}
👤 Получатель: {order.get('recipient', 'не указан')}

🙏 **Пожалуйста, оставьте отзыв о нашей работе!**
Нажмите кнопку ниже 👇""",
            reply_markup=get_leave_review_keyboard(order_id, "stars")
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Stars\n"
        f"Пользователь получил уведомление и предложение оставить отзыв"
    )
    await callback.answer("✅ Завершено!")

async def complete_sub_order(callback: types.CallbackQuery, order_id: str):
    order = orders_subs.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_subs[order_id]['status'] = "completed"
    orders_subs[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_subs, ORDERS_SUBS_FILE)
    
    sub_type_ru = "Со входом в аккаунт" if order['sub_type'] == "with_login" else "Подарочная"
    
    try:
        message_text = f"""🎉 Заказ выполнен!

✅ Спасибо за покупку Telegram Premium!

📅 Тип: {sub_type_ru}
⏳ Срок: {order['sub_period']}
📋 ID заказа: {order_id}

🙏 **Пожалуйста, оставьте отзыв о нашей работе!**
Нажмите кнопку ниже 👇"""
        
        await bot.send_message(
            order['user_id'],
            message_text,
            reply_markup=get_leave_review_keyboard(order_id, "sub")
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Подписка\n"
        f"Пользователь получил уведомление и предложение оставить отзыв"
    )
    await callback.answer("✅ Завершено!")

# ===================== СИСТЕМА ОТЗЫВОВ =====================
@dp.callback_query(F.data.startswith("leave_review_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка данных")
        return
    
    review_type = parts[2]  # withdrawal, gold, bp, stars, sub
    order_id = parts[3]
    
    logger.info(f"Начинаем отзыв: type={review_type}, order_id={order_id}")
    
    # Проверяем, не оставлял ли уже отзыв
    if review_type == "withdrawal":
        if order_id in withdrawals and withdrawals[order_id].get('review_completed'):
            await callback.answer("❌ Вы уже оставили отзыв за этот вывод!")
            return
    elif review_type == "gold":
        if order_id in orders_gold and orders_gold[order_id].get('review_requested'):
            await callback.answer("❌ Вы уже оставили отзыв за этот заказ!")
            return
    elif review_type == "bp":
        if order_id in orders_bp and orders_bp[order_id].get('review_requested'):
            await callback.answer("❌ Вы уже оставили отзыв за этот заказ!")
            return
    elif review_type == "stars":
        if order_id in orders_stars and orders_stars[order_id].get('review_requested'):
            await callback.answer("❌ Вы уже оставили отзыв за этот заказ!")
            return
    elif review_type == "sub":
        if order_id in orders_subs and orders_subs[order_id].get('review_requested'):
            await callback.answer("❌ Вы уже оставили отзыв за этот заказ!")
            return
    
    # Сохраняем информацию о типе заказа
    await state.update_data(
        review_type=review_type,
        order_id=order_id
    )
    
    # Разные сообщения для разных типов заказов
    if review_type == "withdrawal":
        message_text = """
📝 **Оставить отзыв**

За отзыв о выводе голды вы можете получить случайный бонус!

1. 📸 Отправьте фото полученного скина
2. 📝 Напишите текст отзыва

Спасибо! 🎁
"""
    else:
        message_text = """
📝 **Оставить отзыв**

Пожалуйста, оставьте отзыв о нашей работе!

1. 📸 Отправьте фото (чек или что получили)
2. 📝 Напишите текст отзыва

Спасибо за ваш выбор! 🙏
"""
    
    await callback.message.answer(message_text)
    await state.set_state(UserStates.waiting_review_photo)
    await callback.answer()

@dp.message(UserStates.waiting_review_text, F.text)
async def process_review_text(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = await state.get_data()
    
    review_type = data.get('review_type')
    order_id = data.get('order_id')
    review_photo_id = data.get('review_photo_id')
    
    if not review_type or not order_id:
        await message.answer("❌ Ошибка данных!")
        await state.clear()
        return
    
    # Создаем отзыв
    review_id = datetime.now().strftime("R%Y%m%d%H%M%S")
    
    # Начисляем бонус ТОЛЬКО для выводов голды
    bonus_amount = 0
    if review_type == "withdrawal":
        bonus_amount = get_random_bonus()
        
        # Начисляем бонус пользователю
        if user_id in users:
            users[user_id]['balance'] = users[user_id].get('balance', 0) + bonus_amount
            users[user_id]['reviews_count'] = users[user_id].get('reviews_count', 0) + 1
            users[user_id]['total_bonus'] = users[user_id].get('total_bonus', 0) + bonus_amount
            save_data(users, USERS_FILE)
    
    # Сохраняем отзыв
    reviews[review_id] = {
        "review_id": review_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "review_type": review_type,
        "order_id": order_id,
        "photo_id": review_photo_id,
        "text": message.text,
        "bonus_amount": bonus_amount,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_data(reviews, REVIEWS_FILE)
    
    # Обновляем статус заказа
    if review_type == "withdrawal":
        if order_id in withdrawals:
            withdrawals[order_id]['review_completed'] = True
            withdrawals[order_id]['review_id'] = review_id
            withdrawals[order_id]['bonus_amount'] = bonus_amount
            save_data(withdrawals, WITHDRAWALS_FILE)
    elif review_type == "gold":
        if order_id in orders_gold:
            orders_gold[order_id]['review_requested'] = True
            orders_gold[order_id]['review_id'] = review_id
            save_data(orders_gold, ORDERS_GOLD_FILE)
    elif review_type == "bp":
        if order_id in orders_bp:
            orders_bp[order_id]['review_requested'] = True
            orders_bp[order_id]['review_id'] = review_id
            save_data(orders_bp, ORDERS_BP_FILE)
    elif review_type == "stars":
        if order_id in orders_stars:
            orders_stars[order_id]['review_requested'] = True
            orders_stars[order_id]['review_id'] = review_id
            save_data(orders_stars, ORDERS_STARS_FILE)
    elif review_type == "sub":
        if order_id in orders_subs:
            orders_subs[order_id]['review_requested'] = True
            orders_subs[order_id]['review_id'] = review_id
            save_data(orders_subs, ORDERS_SUBS_FILE)
    
    # Отправляем ответ пользователю
    if review_type == "withdrawal":
        await message.answer(
            f"""✅ Спасибо за отзыв!

🎉 Вам начислен бонус: {bonus_amount} голды!

💎 Ваш баланс: {users[user_id]['balance']} голды
🙏 Приходите еще!"""
        )
    else:
        await message.answer(
            """✅ Спасибо за отзыв!

🙏 Мы ценим ваше мнение!
Приходите еще за новыми покупками! 🎮"""
        )
    
    # Уведомляем админа
    try:
        review_type_ru = {
            "withdrawal": "Вывод голды",
            "gold": "Покупка голды",
            "bp": "Покупка BP",
            "stars": "Покупка Stars",
            "sub": "Покупка подписки"
        }.get(review_type, "Неизвестный тип")
        
        admin_text = f"""
📝 НОВЫЙ ОТЗЫВ

👤 Пользователь: {message.from_user.full_name}
📱 {reviews[review_id]['username']}

📊 Тип: {review_type_ru}
📋 ID заказа: {order_id}
📋 ID отзыва: {review_id}
{'💰 Бонус: ' + str(bonus_amount) + ' голды' if bonus_amount > 0 else ''}

📝 Отзыв: {message.text[:500]}...
"""
        
        await bot.send_message(
            ADMIN_ID,
            admin_text
        )
        
        if review_photo_id:
            await bot.send_photo(
                ADMIN_ID,
                photo=review_photo_id,
                caption=f"📸 Фото отзыва {review_id}"
            )
        
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")
    
    await state.clear()

# ===================== ПОДДЕРЖКА =====================
@dp.message(F.text == "🆘 Поддержка")
async def support_cmd(message: types.Message):
    support_text = f"""
🆘 ПОДДЕРЖКА

📍 Администратор: {ADMIN_USERNAME}
🤖 Бот: @Gold_stars_prem_donatuzbbot

📞 По вопросам:
• Не пришла голда / товар
• Проблемы с оплатой
• Ошибки в боте
• Другие вопросы

💎 Курс: {EXCHANGE_RATE} сум = 1 голда
💸 Мин. вывод: {MIN_WITHDRAWAL} голды

💳 Реквизиты HUMO:
{HUMO_CARD}
👤 {CARD_HOLDER}

💎 Реквизиты TON:
{TON_WALLET}
"""
    await message.answer(support_text, parse_mode="Markdown")

# ===================== МОИ ЗАКАЗЫ =====================
@dp.message(F.text == "📋 Мои заказы")
async def my_orders_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    
    orders_text = "📋 Ваши заказы:\n\n"
    has_orders = False
    
    # Добавляем выводы голды
    for withdrawal_id, withdrawal in withdrawals.items():
        if withdrawal['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "admin_buying": "🛒",
                "skin_sent_to_buyer": "📸",
                "awaiting_admin_purchase": "📋",
                "completed": "✅",
                "rejected": "❌"
            }.get(withdrawal['status'], "❓")
            
            orders_text += f"{status_emoji} Вывод голды\n"
            orders_text += f"💰 {withdrawal['amount']} голды\n"
            orders_text += f"📅 {withdrawal['created_at']}\n"
            orders_text += f"📋 ID: {withdrawal_id}\n\n"
    
    # Добавляем заказы голды
    for order_id, order in orders_gold.items():
        if order['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "completed": "🎉",
                "rejected": "❌"
            }.get(order['status'], "❓")
            
            orders_text += f"{status_emoji} Покупка голды\n"
            orders_text += f"💰 {order['gold_amount']} голды\n"
            orders_text += f"💸 {order['amount_sums']} сум\n"
            orders_text += f"📅 {order['created_at']}\n"
            orders_text += f"📋 ID: {order_id}\n\n"
    
    # Добавляем заказы BP
    for order_id, order in orders_bp.items():
        if order['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "completed": "🎉",
                "rejected": "❌"
            }.get(order['status'], "❓")
            
            orders_text += f"{status_emoji} Покупка BP\n"
            orders_text += f"🎮 {order['bp_package']}\n"
            orders_text += f"📅 {order['created_at']}\n"
            orders_text += f"📋 ID: {order_id}\n\n"
    
    if not has_orders:
        orders_text = "📭 У вас нет заказов"
    
    await message.answer(orders_text, parse_mode="Markdown")

# ===================== ОБРАБОТКА ОШИБОК =====================
@dp.message()
async def handle_other_messages(message: types.Message):
    if message.text and message.text not in ["❌ Отмена"]:
        await message.answer(
            "🤖 Используйте кнопки меню ниже ⬇️\n"
            "Или нажмите /start для перезапуска",
            reply_markup=get_main_keyboard()
        )

# ===================== ЗАПУСК БОТА =====================
async def main():
    logger.info("🚀 Запускаю Gold Bot...")
    logger.info(f"🤖 Бот: @Gold_stars_prem_donatuzbbot")
    logger.info(f"👑 Админ: {ADMIN_USERNAME}")
    
    for file in [USERS_FILE, ORDERS_GOLD_FILE, ORDERS_BP_FILE, 
                 ORDERS_STARS_FILE, ORDERS_SUBS_FILE, WITHDRAWALS_FILE, REVIEWS_FILE]:
        if not os.path.exists(file):
            save_data({}, file)
            logger.info(f"📁 Создан файл: {file}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
# ===================== ЗАПУСК ВСЕГО =====================
if __name__ == "__main__":
    logger.info("🚀 Запуск Gold Bot...")
    
    # Запускаем Flask в отдельном потоке (для пинга)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask запущен для пинга")
    
    # НЕМНОГО ЖДЕМ, чтобы Flask успел запуститься
    import time
    time.sleep(3)
    
    # Запускаем Telegram бота
    logger.info("🤖 Запускаю Telegram бота...")
    asyncio.run(main())
