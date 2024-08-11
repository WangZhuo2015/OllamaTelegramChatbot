import asyncio
import json
import logging
import os
from functools import wraps

from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func

from bot.ollama_integration import generate_response
from models import User, db_session, Context
from utils.config import TOKEN, ADMIN_IDS

session = AiohttpSession(proxy=os.getenv("PROXY_URL"))
bot = Bot(token=TOKEN, session=session) if os.getenv("PROXY_URL") else Bot(token=TOKEN)
dp = Dispatcher()

# Global lock to make user messages sequential
lock = asyncio.Lock()
# {user: [context]}
active_sessions = {}

start_kb = InlineKeyboardBuilder()
start_kb.row(
    types.InlineKeyboardButton(text="ℹ️ About", callback_data="about"),
    types.InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"),
)
commands = [
    types.BotCommand(command="start", description="Start"),
    types.BotCommand(command="reset", description="Reset Context"),
    types.BotCommand(command="authorize", description="Authorize User"),
]


def requires_authorization(func):
    @wraps(func)
    async def wrapped(message: types.Message, *args, **kwargs):
        user = db_session.query(User).filter_by(platform_user_id=str(message.from_user.id)).first()
        if user and user.is_authorized:
            return await func(message, *args, **kwargs)
        else:
            await message.answer("You are not authorized to use this bot.")

    return wrapped


@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    start_message = f"Welcome, <b>{message.from_user.full_name}</b>!"
    await message.answer(
        start_message,
        parse_mode=ParseMode.HTML,
        reply_markup=start_kb.as_markup()
    )


@dp.message(Command("reset"))
async def command_reset_handler(message: types.Message):
    await message.answer("Chat has been reset.")


def create_authorize_button(user_id):
    button = InlineKeyboardButton(text="Authorize", callback_data=f"authorize:{user_id}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    return keyboard


@dp.message(Command("authorize"))
@requires_authorization
async def authorize_user_command(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        keyboard = create_authorize_button(message.from_user.id)
        await message.answer("Click the button below to authorize a user.", reply_markup=keyboard)
    else:
        await message.answer("You do not have permission to authorize users.")


@dp.callback_query()
async def handle_authorize_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id in ADMIN_IDS:
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.message.chat.id, "Please enter the user ID you want to authorize:")
        dp['waiting_for_user_id'] = callback_query.from_user.id
    else:
        await bot.answer_callback_query(callback_query.id, "You do not have permission to authorize users.")


@dp.message()
async def handle_user_id_input(message: types.Message):
    if dp.get('waiting_for_user_id') == message.from_user.id:
        user_id = message.text.strip()

        user = db_session.query(User).filter_by(platform_user_id=user_id).first()
        if user:
            user.is_authorized = True
            await message.answer(f"User {user_id} has been authorized.")
        else:
            new_user = User(platform_user_id=user_id, is_authorized=True, platform="Telegram")
            db_session.add(new_user)
            await message.answer(f"User {user_id} has been added and authorized.")

        db_session.commit()
        dp['waiting_for_user_id'] = None
    else:
        await handle_message(message)


@dp.message()
@requires_authorization
async def handle_message(message: types.Message):
    async with lock:
        logging.info(f"Handle message from {message.from_user.full_name}: {message.text}")
        prompt = message.text

        # 获取当前session的上下文
        user_id = message.from_user.id

        # 如果还没有active session，创建一个新的，或者从数据库加载
        if user_id not in active_sessions:
            user = db_session.query(User).filter_by(platform_user_id=user_id).first()
            if user and user.active_session_id:
                # 从数据库加载当前session的上下文
                context_entries = db_session.query(Context).filter_by(session_id=user.active_session_id).order_by(
                    Context.entry_id).all()
                active_sessions[user_id] = [json.loads(entry.context_data) for entry in context_entries]
            else:
                create_new_session(user_id)

        context_entries = get_active_context(user_id)  # 获取内容数据

        # 记录用户的输入
        add_context_entry(db_session.query(User).filter_by(platform_user_id=user_id).first().active_session_id, user_id,
                          {'role': 'user', 'content': prompt})

        full_response = ""
        partial_sent = ""
        initial_message = await message.answer("typing...")

        # 生成回复
        async for part in generate_response(context_entries):
            full_response += part

            # 在回复完整的一句话后更新消息
            if any(full_response.endswith(c) for c in ".!?") and full_response != partial_sent:
                await bot.edit_message_text(
                    text=full_response + "...",
                    chat_id=message.chat.id,
                    message_id=initial_message.message_id
                )
                partial_sent = full_response

        if full_response:
            # 记录机器人的回复
            add_context_entry(db_session.query(User).filter_by(platform_user_id=user_id).first().active_session_id,
                              user_id, {'role': 'assistant', 'content': full_response})

            # 发送最终回复
            await bot.edit_message_text(
                text=f"{full_response}",
                chat_id=message.chat.id,
                message_id=initial_message.message_id
            )


def create_new_session(user_id):
    new_session_id = db_session.query(func.max(Context.session_id)).scalar() or 0
    new_session_id += 1

    # 初始化内存中的session
    active_sessions[user_id] = []

    # 更新用户表中的active_session_id
    user = db_session.query(User).filter_by(platform_user_id=user_id).first()
    user.active_session_id = new_session_id
    db_session.commit()

    return new_session_id


def add_context_entry(session_id, user_id, context_data):
    # 将context_data字典转换为JSON字符串
    context_data_json = json.dumps(context_data)

    # 将新条目添加到内存中的session
    active_sessions[user_id].append(context_data)

    # 将新的上下文数据保存到数据库中
    new_entry = Context(
        session_id=session_id,
        entry_id=len(active_sessions[user_id]) - 1,
        user_id=user_id,
        context_data=context_data_json  # 存储为JSON字符串
    )
    db_session.add(new_entry)
    db_session.commit()


def get_active_context(user_id):
    return active_sessions.get(user_id, [])


def reset_context(user_id):
    new_session_id = create_new_session(user_id)
    return new_session_id


@dp.message(Command("reset"))
async def command_reset_handler(message: types.Message):
    user_id = message.from_user.id
    reset_context(user_id)
    await message.answer("Chat has been reset. A new session has been created.")
