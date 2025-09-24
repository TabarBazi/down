import asyncio
import platform
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import settings # Import settings from your config file

async def main():
    """
    Connects to Telegram, logs in, and prints the session string.
    """
    print("Starting session generation...")
    # The client will use the api_id and api_hash from your config.py
    # It will prompt for phone number, password, and login code in the console.
    async with TelegramClient(StringSession(), settings.api_id, settings.api_hash) as client:
        session_string = client.session.save()
        print("\nThis is your session string. Copy it and place it in your .env file:\n")
        print(f"SESSION_STRING=\"{session_string}\"")
        print("\nLogin successful. You can now close this script.")

if __name__ == "__main__":
    # Add a policy for Windows to prevent a common asyncio error
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the async main function
    asyncio.run(main())