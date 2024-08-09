import asyncio
import logging

from bot.telegram_bot import dp, bot, commands

logging.basicConfig(level=logging.INFO)


async def main():
    await bot.set_my_commands(commands)
    await dp.start_polling(bot, skip_update=True)


if __name__ == "__main__":
    asyncio.run(main())
