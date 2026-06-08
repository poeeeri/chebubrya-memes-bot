from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Any

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .config import Settings
from .database import (
    get_meme_request,
    log_feedback,
    log_meme_error,
    log_meme_request,
    log_next_meme_request_once,
    update_response_message_id,
)
from .retriever import pick_best_meme_with_candidates_async


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

    @dp.callback_query(F.data.startswith("fb:"))
    async def feedback_handler(callback: CallbackQuery) -> None:
        if not callback.data:
            await callback.answer("Не понял feedback.")
            return

        parts = callback.data.split(":", maxsplit=2)
        if len(parts) != 3:
            await callback.answer("Не понял feedback.")
            return

        _, feedback, request_id = parts
        if feedback not in {"like", "dislike", "more"}:
            await callback.answer("Не понял feedback.")
            return

        try:
            if feedback == "more" and isinstance(callback.message, Message):
                has_next = await _reply_with_next_candidate(
                    callback.message,
                    callback.from_user.id if callback.from_user else None,
                    request_id,
                )
                if not has_next:
                    await callback.answer("Других вариантов не осталось.")
                    return
            else:
                saved = await log_feedback(
                    request_id=request_id,
                    user_id=callback.from_user.id if callback.from_user else None,
                    feedback=feedback,
                )
                if not saved:
                    await callback.answer("Уже сохранил.")
                    return
        except Exception:
            logging.exception("Failed to save meme feedback: %s", callback.data)
            await callback.answer("Не смог сохранить feedback.")
            return

        await callback.answer("Сохранил.")

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
        match, candidates = await pick_best_meme_with_candidates_async(query, settings)
        request_id = await _log_success(message, query, match, candidates)

        image_path = Path(match["image_path"])
        if not image_path.exists():
            raise FileNotFoundError(f"Meme image was not found: {image_path}")

        photo = FSInputFile(image_path)
        sent_message = await message.reply_photo(
            photo=photo,
            reply_markup=_feedback_keyboard(
                request_id,
                include_more=_has_next_candidate(candidates, match.get("id")),
            ) if request_id else None,
        )
        await update_response_message_id(request_id, sent_message.message_id)
    except Exception as exc:
        logging.exception("Failed to serve meme for query: %s", query)
        await _log_error(message, query, exc)
        await message.reply("Не смог подобрать мем")


async def _log_success(
    message: Message,
    query: str,
    match: dict,
    candidates: list[dict],
) -> str | None:
    try:
        return await log_meme_request(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            request_message_id=message.message_id,
            query=query,
            selected_meme=match,
            candidates=candidates,
        )
    except Exception:
        logging.exception("Failed to save meme request history.")
        return None


async def _log_error(message: Message, query: str, exc: Exception) -> None:
    try:
        await log_meme_error(
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            request_message_id=message.message_id,
            query=query,
            error=repr(exc),
        )
    except Exception:
        logging.exception("Failed to save meme request error.")


def _feedback_keyboard(request_id: str, *, include_more: bool = True) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text="👍", callback_data=f"fb:like:{request_id}"),
        InlineKeyboardButton(text="👎", callback_data=f"fb:dislike:{request_id}"),
    ]
    if include_more:
        buttons.append(InlineKeyboardButton(text="Еще", callback_data=f"fb:more:{request_id}"))

    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons
        ]
    )


async def _reply_with_next_candidate(
    message: Message,
    user_id: int | None,
    previous_request_id: str,
) -> bool:
    request = await get_meme_request(previous_request_id)
    if not request:
        await _hide_more_button(message, previous_request_id)
        return False

    candidates = _load_candidates(request.get("candidates"))
    next_candidate = _find_next_candidate(candidates, request.get("selected_meme_id"))
    if not next_candidate:
        await _hide_more_button(message, previous_request_id)
        return False

    await _hide_more_button(message, previous_request_id)

    query = str(request["query"])
    new_request_id = await log_next_meme_request_once(
        previous_request_id=previous_request_id,
        chat_id=message.chat.id,
        user_id=user_id,
        request_message_id=message.message_id,
        query=query,
        selected_meme=next_candidate,
        candidates=candidates,
    )
    if not new_request_id:
        return False

    image_path = Path(next_candidate["image_path"])
    if not image_path.exists():
        raise FileNotFoundError(f"Meme image was not found: {image_path}")

    photo = FSInputFile(image_path)
    sent_message = await message.answer_photo(
        photo=photo,
        reply_markup=_feedback_keyboard(
            new_request_id,
            include_more=_has_next_candidate(candidates, next_candidate.get("id")),
        ) if new_request_id else None,
    )
    await update_response_message_id(new_request_id, sent_message.message_id)
    return True


def _load_candidates(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _find_next_candidate(candidates: list[dict], selected_meme_id: object) -> dict | None:
    if not candidates:
        return None

    selected_id = str(selected_meme_id)
    for index, candidate in enumerate(candidates):
        if str(candidate.get("id")) == selected_id:
            next_index = index + 1
            if next_index < len(candidates):
                return candidates[next_index]
            return None

    return candidates[0]


def _has_next_candidate(candidates: list[dict], selected_meme_id: object) -> bool:
    return _find_next_candidate(candidates, selected_meme_id) is not None


async def _hide_more_button(message: Message, request_id: str) -> None:
    try:
        await message.edit_reply_markup(reply_markup=_feedback_keyboard(request_id, include_more=False))
    except Exception:
        logging.exception("Failed to hide more button for request: %s", request_id)