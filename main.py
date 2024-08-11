import asyncio
import logging

from bot.telegram_bot import dp, bot, commands
from models import add_admins_to_db

logging.basicConfig(level=logging.INFO)


async def main():
    await bot.set_my_commands(commands)
    await dp.start_polling(bot, skip_update=True)


if __name__ == "__main__":
    add_admins_to_db()
    asyncio.run(main())
