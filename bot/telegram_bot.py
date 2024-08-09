import os

from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.ollama_integration import generate_response
from utils.config import TOKEN

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
]


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


@dp.message()
async def handle_message(message: types.Message):
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
