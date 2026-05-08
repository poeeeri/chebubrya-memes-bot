from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import FSInputFile, Message

from .config import Settings
from .retriever import pick_best_meme


def create_dispatcher(settings: Settings, bot_username: str) -> Dispatcher:
    dp = Dispatcher()
    mention = f"@{bot_username}".lower()

    @dp.message(Command("start"))
    async def start_handler(message: Message) -> None:
        await message.answer(
            "Отмечай меня в групповом чате текстом, и я попробую подобрать подходящий мем. "
            "Еще можно ответить на сообщение командой /meme."
        )

    @dp.message(Command("meme"))
    async def meme_handler(message: Message, command: CommandObject) -> None:
        query = (command.args or "").strip()
        if not query:
            query = _extract_reply_text(message)

        if not query:
            await message.reply(
                "После /meme нужен текст запроса или reply на сообщение."
            )
            return

        await _reply_with_meme(message, query, settings)

    @dp.message(F.text)
    async def mention_handler(message: Message) -> None:
        if not message.text:
            return

        if mention not in message.text.lower():
            return

        query = _strip_mention(message.text, mention).strip()
        if not query:
            query = _extract_reply_text(message)

        if not query:
            await message.reply(
                "После упоминания нужен текст запроса или reply на сообщение."
            )
            return

        await _reply_with_meme(message, query, settings)

    return dp


def _strip_mention(text: str, mention: str) -> str:
    words = text.split()
    cleaned_words = [word for word in words if word.lower() != mention]
    return " ".join(cleaned_words)


def _extract_reply_text(message: Message) -> str:
    if not message.reply_to_message:
        return ""

    return (
        message.reply_to_message.text
        or message.reply_to_message.caption
        or ""
    ).strip()


async def _reply_with_meme(message: Message, query: str, settings: Settings) -> None:
    try:
        match = pick_best_meme(query, settings)
        image_path = Path(match["image_path"])
        photo = FSInputFile(image_path)
        await message.reply_photo(photo=photo)
    except Exception:
        logging.exception("Failed to serve meme for query: %s", query)
        await message.reply("Не смог подобрать мем")