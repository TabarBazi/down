import asyncio
import logging
import sys

from bot.core import bot, setup_dispatcher
from utils.helpers import check_dependencies
from utils.db_session import engine
from utils.models import Base
from utils.telegram_client import init_telethon_client, shutdown_telethon_client

async def init_database():
    """
    Initializes the database and creates tables if they don't exist.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.getLogger(__name__).info("Database tables checked/created successfully.")

async def main():
    """
    The main function to start the bot.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    logger.info("Checking system dependencies...")
    if not check_dependencies():
        logger.error("A required system dependency is missing. Please install it and try again.")
        sys.exit(1)
        
    logger.info("Initializing database...")
    await init_database()
    
    logger.info("Starting Telethon client...")
    try:
        await init_telethon_client()
    except RuntimeError as err:
        logger.error(f"Failed to start Telethon client: {err}")
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error while starting Telethon client.")
        sys.exit(1)

    dp = setup_dispatcher()

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await shutdown_telethon_client()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")