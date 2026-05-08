from __future__ import annotations
from .config import Settings
from openai import OpenAI
from typing import Iterable
import json


def build_openai_client(settings: Settings) -> OpenAI:
    headers = {}
    # openriuter
    headers['HTTP-Referer'] = settings.openrouter_site_url
    headers['X-OpenRouter-Title'] = settings.openrouter_site_name
    kwargs = {'api_key': settings.openai_api_key}
    kwargs['default_headers'] = headers
    return OpenAI(**kwargs)

# превращаем список текстов в эмбеддинги
def embed_texts(client: OpenAI, model: str, texts: Iterable[str]) -> list[list[float]]:
    text_list = list(texts)
    response = client.embeddings.create(model=model, input=text_list)
    return [item.embedding for item in response.data]


def choose_best_meme(client: OpenAI, model: str, query: str, candidates: list[dict]) -> dict:
    candidates_lines = []

    for idx, candidate in enumerate(candidates, start=1):
        candidates_lines.append(
            '\n'.join(
                [
                    f"{idx}. id: {candidate['id']}",
                    f"image_path: {candidate['image_path']}",
                    f"distance_score: {candidate.get('distance', 'n/a')}",
                ],
            )
        )

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        # промпт
        messages=[
            {
                "role": "system",
                "content": (
                    "ты выбираешь единственный наилучший мем для Telegram сообщения. "
                    "верни только валидный JSON с ключами: meme_id"
                ),
            },
            {
                "role": "user",
                "content": "\n\n".join(
                    [
                        f'user message: "{query}"',
                        "выбери ровно один мем-кандидат.",
                        "candidates:",
                        "\n\n".join(candidates_lines),
                    ]
                ),
            },
        ],
    )
    raw_text = (response.choices[0].message.content or '').strip()
    try: 
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "meme_id": candidates[0]["id"],
            "raw_output": raw_text,
        }
    return parsed