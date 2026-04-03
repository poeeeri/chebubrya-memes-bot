from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from .config import Settings
from .retriever import pick_best_meme


def create_dispatcher(settings: Settings) -> Dispatcher:
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start_handler(message: Message) -> None:
        await message.answer(
            "Отмечай меня в групповом чате текстом, и я попробую подобрать подходящий мем."
        )

    @dp.message(F.text)
    async def mention_handler(message: Message, bot: Bot) -> None:
        if not message.text:
            return

        me = await bot.get_me()
        mention = f"@{me.username}".lower()
        text_lower = message.text.lower()

        if mention not in text_lower:
            return

        cleaned_query = _strip_mention(message.text, mention).strip()
        if not cleaned_query:
            await message.reply("После упоминания нужен текст запроса, например: @bot_name понедельник.")
            return

        try:
            match = pick_best_meme(cleaned_query, settings)
            image_path = Path(match["image_path"])
            photo = FSInputFile(image_path)
            await message.reply_photo(photo=photo)
        except Exception:
            logging.exception("Failed to serve meme for query: %s", cleaned_query)
            await message.reply("Не смог подобрать мем")

    return dp


def _strip_mention(text: str, mention: str) -> str:
    words = text.split()
    cleaned_words = [word for word in words if word.lower() != mention]
    return " ".join(cleaned_words)