import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from handlers import router, handle_start_command, cleanup_old_deals

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    await db.init()
    logger.info("Database initialized")

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(router)
    dp.message.register(handle_start_command, Command("start"))

    cleanup_task = asyncio.create_task(cleanup_old_deals())

    logger.info("Bot started")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        cleanup_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
