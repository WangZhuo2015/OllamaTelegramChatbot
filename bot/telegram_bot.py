import asyncio
import json
import logging
import os
import re
from functools import wraps

from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func

from bot.ollama_integration import generate_response, model_list
from models import User, db_session, Context
from utils.config import TOKEN, ADMIN_IDS, INITMODEL

session = AiohttpSession(proxy=os.getenv("PROXY_URL"))
bot = Bot(token=TOKEN, session=session) if os.getenv("PROXY_URL") else Bot(token=TOKEN)
dp = Dispatcher()

# Global lock to ensure sequential processing of user messages
lock = asyncio.Lock()
# Dictionary to store active sessions: {user: [context]}
active_sessions = {}

# Inline keyboard for start command
start_kb = InlineKeyboardBuilder()
start_kb.row(
    types.InlineKeyboardButton(text="ℹ️ About", callback_data="about"),
    types.InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"),
    types.InlineKeyboardButton(text="🔄 Switch Model", callback_data="switchModel"),
)

# List of bot commands with descriptions
commands = [
    types.BotCommand(command="start", description="Start"),
    types.BotCommand(command="reset", description="Reset Context"),
    types.BotCommand(command="authorize", description="Authorize User"),
]


# Decorator to check if the user is authorized
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


@dp.callback_query(lambda query: query.data == "switchModel")
async def switch_model_callback_handler(query: types.CallbackQuery):
    models = (await model_list())["models"]
    model_selector = InlineKeyboardBuilder()
    for model in models:
        model_name = model["name"]
        parameter_size = model["details"]["parameter_size"]
        model_selector.row(
            types.InlineKeyboardButton(
                text=f"{model_name} - {parameter_size}", callback_data=f"model_{model_name}"
            )
        )
    await query.message.edit_text(
        f"{len(models)} models available.", reply_markup=model_selector.as_markup(),
    )


@dp.callback_query(lambda query: query.data.startswith("model_"))
async def model_callback_handler(query: types.CallbackQuery):
    selected_model = query.data.split("model_")[1]
    user_id = query.from_user.id

    # Update the user's current model in the database
    user = db_session.query(User).filter_by(platform_user_id=user_id).first()
    if user:
        user.model = selected_model
        db_session.commit()
        await query.answer(f"Model switched to {selected_model}!")
    else:
        await query.answer(f"User not found. Please try again.")

    await query.message.edit_reply_markup()  # Remove buttons after selection


@dp.message(Command("reset"))
async def command_reset_handler(message: types.Message):
    dp['waiting_for_user_id'] = None
    user_id = message.from_user.id
    reset_context(user_id)
    await message.answer("Chat has been reset. A new session has been created.")


# Function to create an inline authorize button for user authorization
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


# Handle incoming messages from authorized users
@dp.message()
@requires_authorization
async def handle_message(message: types.Message):
    async with lock:
        logging.info(f"Handle message from {message.from_user.full_name}: {message.text}")
        prompt = message.text

        # Get the current session context for the user
        user_id = message.from_user.id

        user = db_session.query(User).filter_by(platform_user_id=user_id).first()
        # If no active session exists, create a new one or load from the database
        if user_id not in active_sessions:
            if user and user.active_session_id:
                # Load the current session context from the database
                context_entries = db_session.query(Context).filter_by(session_id=user.active_session_id).order_by(
                    Context.entry_id).all()
                active_sessions[user_id] = [json.loads(entry.context_data) for entry in context_entries]
            else:
                create_new_session(user_id)

        context_entries = get_active_context(user_id)  # Get the context data

        # Record the user's input
        add_context_entry(db_session.query(User).filter_by(platform_user_id=user_id).first().active_session_id, user_id,
                          {'role': 'user', 'content': prompt})

        full_response = ""
        partial_sent = ""
        initial_message = await message.answer("typing...", parse_mode=ParseMode.MARKDOWN, )

        # Generate a response using the context
        async for part in generate_response(context_entries, model=user.model or INITMODEL):
            full_response += part

            # Update the message after a complete sentence
            if is_sentence_end(full_response, partial_sent, custom_regex=None) and full_response != partial_sent:
                await bot.edit_message_text(
                    text=full_response + "...",
                    chat_id=message.chat.id,
                    message_id=initial_message.message_id,
                    parse_mode=ParseMode.MARKDOWN,
                )
                partial_sent = full_response

        if full_response:
            # Record the bot's response
            add_context_entry(db_session.query(User).filter_by(platform_user_id=user_id).first().active_session_id,
                              user_id, {'role': 'assistant', 'content': full_response})

            # Send the final response
            await bot.edit_message_text(
                # if LOGLEVEL=DEBUG, add model name to the response
                text=f"{full_response} \n\n*Generated by {user.model or INITMODEL}*" if os.getenv(
                    "LOGLEVEL") == "DEBUG" else full_response,
                chat_id=message.chat.id,
                message_id=initial_message.message_id,
                parse_mode=ParseMode.MARKDOWN,
            )


# Create a new session for the user
def create_new_session(user_id):
    # Get the current maximum session_id from the table, or start from 0 if none exist
    new_session_id = db_session.query(func.max(Context.session_id)).scalar() or 0
    new_session_id += 1  # Increment to get a new session ID

    # Initialize the session in memory
    active_sessions[user_id] = []

    # Update the user's active session ID in the database
    user = db_session.query(User).filter_by(platform_user_id=user_id).first()
    user.active_session_id = new_session_id

    # Commit the new session_id to the database
    db_session.commit()

    return new_session_id


# Add a new context entry to the session
def add_context_entry(session_id, user_id, context_data):
    # Convert the context_data dictionary to a JSON string
    context_data_json = json.dumps(context_data)

    # Append the new entry to the session in memory
    active_sessions[user_id].append(context_data)

    # Save the new context data to the database
    new_entry = Context(
        session_id=session_id,
        entry_id=len(active_sessions[user_id]) - 1,
        user_id=user_id,
        context_data=context_data_json  # Store as a JSON string
    )
    db_session.add(new_entry)
    db_session.commit()


# Get the active context for the user
def get_active_context(user_id):
    return active_sessions.get(user_id, [])


# Reset the context for the user, creating a new session
def reset_context(user_id):
    new_session_id = create_new_session(user_id)
    return new_session_id


def is_sentence_end(full_response, partial_sent, custom_regex=None):
    # Default regex pattern for sentence end
    default_regex = r"[.!?。！？]\s*$"

    # Use custom regex if provided, otherwise use the default one
    regex = custom_regex if custom_regex else default_regex

    # Check if the response matches the regex pattern and is not the same as the partial_sent
    if re.search(regex, full_response) and full_response != partial_sent:
        return True
    return False
