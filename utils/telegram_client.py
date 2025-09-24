import asyncio
import logging
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.functions.channels import CreateChannelRequest, EditAdminRequest
from telethon.tl.types import ChatAdminRights, PeerChannel
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from utils import database

logger = logging.getLogger(__name__)

_telethon_client: Optional[TelegramClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None
_client_lock = asyncio.Lock()


async def init_telethon_client(force_reconnect: bool = False) -> TelegramClient:
    """Ensure a single connected Telethon client is available."""

    global _telethon_client, _client_loop

    async with _client_lock:
        current_loop = asyncio.get_running_loop()

        if force_reconnect and _telethon_client is not None:
            if _telethon_client.is_connected():
                await _telethon_client.disconnect()
            _telethon_client = None
            _client_loop = None

        if (
            _telethon_client is not None
            and _client_loop is not None
            and _client_loop is not current_loop
        ):
            if _telethon_client.is_connected():
                await _telethon_client.disconnect()
            _telethon_client = None
            _client_loop = None

        if _telethon_client is None:
            _telethon_client = TelegramClient(
                StringSession(settings.session_string),
                settings.api_id,
                settings.api_hash,
                loop=current_loop,
            )
            _client_loop = current_loop

        if not _telethon_client.is_connected():
            await _telethon_client.connect()
            if not await _telethon_client.is_user_authorized():
                logger.error(
                    "[Telethon] CRITICAL: The session string is invalid or has expired. Please generate a new one."
                )
                raise RuntimeError("Telethon client authorization failed")

            me = await _telethon_client.get_me()
            identifier = getattr(me, "username", None) or me.id
            logger.info(f"[Telethon] Client connected successfully as {identifier}.")

    return _telethon_client


async def shutdown_telethon_client() -> None:
    """Disconnect the shared Telethon client if it is running."""

    global _telethon_client, _client_loop

    async with _client_lock:
        if _telethon_client and _telethon_client.is_connected():
            await _telethon_client.disconnect()
            logger.info("[Telethon] Client disconnected.")
        _client_loop = None


async def get_or_create_personal_archive(session: AsyncSession, user_id: int, bot_username: str) -> int | None:
    """
    Checks for a user's personal archive channel. If it doesn't exist,
    it creates a new private channel using the configured session string.
    """
    user = await database.get_or_create_user(session, user_id)
    if user.personal_archive_id:
        logger.info(f"[Archive] Personal channel for user {user_id} already exists: {user.personal_archive_id}")
        return user.personal_archive_id

    logger.info(f"[Archive] Creating personal archive channel for user {user_id}...")

    try:
        client = await init_telethon_client()
    except RuntimeError as err:
        logger.error(f"[Telethon] Unable to initialize client: {err}")
        return None

    try:
        result = await client(CreateChannelRequest(
            title=str(user_id),
            about=f"Personal media archive for @{bot_username}",
            megagroup=False
        ))

        new_channel_id = result.chats[0].id
        full_channel_id = int(f"-100{new_channel_id}")

        channel_entity = await client.get_entity(PeerChannel(new_channel_id))

        normalized_username = bot_username if bot_username.startswith('@') else f"@{bot_username}"
        bot_entity = await client.get_entity(normalized_username)

        admin_rights = ChatAdminRights(
            post_messages=True, edit_messages=True, delete_messages=True,
            invite_users=True, change_info=True, pin_messages=True,
            add_admins=False, ban_users=True, manage_call=True, anonymous=False, other=True
        )
        await client(EditAdminRequest(channel=channel_entity, user_id=bot_entity, admin_rights=admin_rights, rank='bot'))

        user.personal_archive_id = full_channel_id
        await session.commit()

        logger.info(f"[Archive] Successfully created channel {full_channel_id} for user {user_id}.")
        return full_channel_id

    except FloodWaitError as e:
        logger.error(f"[Archive] Flood wait error: Waiting for {e.seconds} seconds.")
        await asyncio.sleep(e.seconds)
        return None
    except Exception as e:
        logger.error(f"[Archive] Error creating personal channel for user {user_id}: {e}", exc_info=True)
        return None

