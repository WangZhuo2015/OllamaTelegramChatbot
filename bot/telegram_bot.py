import os

from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.ollama_integration import generate_response
from models import User, db_session
from utils.config import TOKEN, ADMIN_IDS
from functools import wraps

session = AiohttpSession(proxy=os.getenv("PROXY_URL"))
bot = Bot(token=TOKEN, session=session) if os.getenv("PROXY_URL") else Bot(token=TOKEN)
dp = Dispatcher()

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
            new_user = User(platform_user_id=user_id, is_authorized=True)
            db_session.add(new_user)
            await message.answer(f"User {user_id} has been added and authorized.")

        db_session.commit()
        dp['waiting_for_user_id'] = None
    else:
        await handle_message(message)


@dp.message()
@requires_authorization
async def handle_message(message: types.Message):
    print(f"Handle message from {message.from_user.full_name}: {message.text}")
    prompt = message.text
    full_response = ""
    partial_sent = ""
    initial_message = await message.answer("typing...")

    async for part in generate_response(prompt):
        full_response += part

        if any(full_response.endswith(c) for c in ".!?") and full_response != partial_sent:
            await bot.edit_message_text(
                text=full_response + "...",
                chat_id=message.chat.id,
                message_id=initial_message.message_id
            )
            partial_sent = full_response

    if full_response:
        await bot.edit_message_text(
            text=f"{full_response}",
            chat_id=message.chat.id,
            message_id=initial_message.message_id
        )
