from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from .bot import create_dispatcher
from .config import Settings
from .database import close_database, init_database


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set"
        )

    await init_database(settings)

    try:
        retry_delay = settings.telegram_retry_delay_seconds

        while True:
            session = AiohttpSession(timeout=settings.telegram_request_timeout_seconds)
            bot = Bot(token=settings.telegram_bot_token, session=session)
            try:
                me = await bot.get_me()
                if not me.username:
                    raise RuntimeError("Telegram bot username is empty")

                dp = create_dispatcher(settings, me.username)
                logging.info(
                    "Starting Telegram polling for @%s with request timeout=%ss",
                    me.username,
                    settings.telegram_request_timeout_seconds,
                )
                await dp.start_polling(bot)
                retry_delay = settings.telegram_retry_delay_seconds
            except asyncio.CancelledError:
                logging.info("Polling was cancelled, shutting down.")
                raise
            except Exception:
                logging.exception(
                    "Telegram polling failed. Retrying in %.1f seconds.",
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(
                    retry_delay * 2,
                    settings.telegram_retry_delay_max_seconds,
                )
            finally:
                await bot.session.close()
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(run())
