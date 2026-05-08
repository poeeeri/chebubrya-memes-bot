from __future__ import annotations
import json
import logging
from typing import Any
from uuid import uuid4
import asyncpg
from .config import Settings


_pool: asyncpg.Pool | None = None


async def init_database(settings: Settings) -> None:
    global _pool
    if not settings.database_url:
        logging.info("DATABASE_URL is empty, request history storage is disabled.")
        return

    _pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            create table if not exists meme_requests (
                id uuid primary key,
                created_at timestamptz not null default now(),
                telegram_chat_id bigint not null,
                telegram_user_id bigint,
                request_message_id bigint,
                response_message_id bigint,
                query text not null,
                selected_meme_id text,
                selected_image_path text,
                candidates jsonb not null default '[]'::jsonb,
                status text not null default 'served',
                error text
            );

            create table if not exists meme_feedback (
                id bigserial primary key,
                created_at timestamptz not null default now(),
                request_id uuid not null references meme_requests(id) on delete cascade,
                telegram_user_id bigint,
                feedback text not null check (feedback in ('like', 'dislike', 'more'))
            );

            create index if not exists idx_meme_requests_created_at
                on meme_requests (created_at desc);
            create index if not exists idx_meme_requests_selected_meme_id
                on meme_requests (selected_meme_id);
            create index if not exists idx_meme_feedback_request_id
                on meme_feedback (request_id);
            """
        )


async def close_database() -> None:
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None


async def log_meme_request(
    *,
    chat_id: int,
    user_id: int | None,
    request_message_id: int | None,
    query: str,
    selected_meme: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> str | None:
    if _pool is None:
        return None

    request_id = str(uuid4())
    await _pool.execute(
        """
        insert into meme_requests (
            id,
            telegram_chat_id,
            telegram_user_id,
            request_message_id,
            query,
            selected_meme_id,
            selected_image_path,
            candidates,
            status
        )
        values ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb, 'served')
        """,
        request_id,
        chat_id,
        user_id,
        request_message_id,
        query,
        str(selected_meme.get("id", "")),
        str(selected_meme.get("image_path", "")),
        _json_dumps(candidates),
    )
    return request_id


async def update_response_message_id(request_id: str | None, response_message_id: int) -> None:
    if _pool is None or not request_id:
        return

    await _pool.execute(
        """
        update meme_requests
        set response_message_id = $2
        where id = $1::uuid
        """,
        request_id,
        response_message_id,
    )


async def log_meme_error(
    *,
    chat_id: int,
    user_id: int | None,
    request_message_id: int | None,
    query: str,
    error: str,
) -> None:
    if _pool is None:
        return

    await _pool.execute(
        """
        insert into meme_requests (
            id,
            telegram_chat_id,
            telegram_user_id,
            request_message_id,
            query,
            status,
            error
        )
        values ($1::uuid, $2, $3, $4, $5, 'error', $6)
        """,
        str(uuid4()),
        chat_id,
        user_id,
        request_message_id,
        query,
        error[:2000],
    )


async def log_feedback(
    *,
    request_id: str,
    user_id: int | None,
    feedback: str,
) -> None:
    if _pool is None:
        return

    await _pool.execute(
        """
        insert into meme_feedback (request_id, telegram_user_id, feedback)
        values ($1::uuid, $2, $3)
        """,
        request_id,
        user_id,
        feedback,
    )


async def get_meme_request(request_id: str) -> dict[str, Any] | None:
    if _pool is None:
        return None

    row = await _pool.fetchrow(
        """
        select query, selected_meme_id, candidates
        from meme_requests
        where id = $1::uuid
        """,
        request_id,
    )
    if row is None:
        return None

    return dict(row)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)