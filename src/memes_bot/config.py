from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
import os
from __future__ import annotations

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / '.env')


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    telegram_bot_token: str
    openai_base_url: str = ""
    openrouter_site_url: str = ""
    openrouter_site_name: str = ""
    openai_embedding_model: str = "openai/text-embedding-3-small"
    openai_rerank_model: str = "openai/gpt-5-mini"
    chroma_dir: Path = ROOT_DIR / "storage" / "chroma"
    meme_collection: str = "memes"
    retrieval_top_k: int = 5
    # настройка таймаутов и ретраев для телеграм апи
    telegram_request_timeout_seconds: float = 120.0
    telegram_retry_delay_seconds: float = 5.0
    telegram_retry_delay_max_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            openai_base_url=os.getenv('OPENAI_BASE_URL', '').strip(),
            openrouter_site_url=os.getenv('OPENROUTER_SITE_URL', '').strip(),
            openrouter_site_name=os.getenv('OPENROUTER_SITE_NAME', '').strip(),
            openai_embedding_model=os.getenv('OPENAI_EMBEDDING_MODEL', 'openai/text-embedding-3-small').strip(),
            openai_rerank_model=os.getenv('OPENAI_RERANK_MODEL', 'openai/gpt-5-mini').strip(),
            chroma_dir=os.getenv('CHROMA_DIR', 'storage/chroma'),
            meme_collection=os.getenv('MEME_COLLECTION', 'memes'),
            retrieval_top_k=os.getenv('OPENROUTER_SITE_URL', ''),
            telegram_request_timeout_seconds=os.getenv('OPENROUTER_SITE_URL', '120.0'),
            telegram_retry_delay_seconds=os.getenv('OPENROUTER_SITE_URL', '5.0'),
            telegram_retry_delay_max_seconds=os.getenv('OPENROUTER_SITE_URL', '60.0'),
        )