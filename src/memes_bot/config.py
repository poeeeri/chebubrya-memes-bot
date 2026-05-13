from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
import os


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
    telegram_request_timeout_seconds: float = 120.0
    telegram_retry_delay_seconds: float = 5.0
    telegram_retry_delay_max_seconds: float = 60.0
    local_reranker_model_path: str = ""
    local_retrieval_model_path: str = ""
    local_retrieval_use_e5_prefixes: bool = True
    database_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        chroma_dir_env = os.getenv('CHROMA_DIR', 'storage/chroma')
        if isinstance(chroma_dir_env, str):
            chroma_dir_path = ROOT_DIR / chroma_dir_env
        else:
            chroma_dir_path = chroma_dir_env
        return cls(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            openai_base_url=os.getenv('OPENAI_BASE_URL', '').strip(),
            openrouter_site_url=os.getenv('OPENROUTER_SITE_URL', '').strip(),
            openrouter_site_name=os.getenv('OPENROUTER_SITE_NAME', '').strip(),
            openai_embedding_model=os.getenv('OPENAI_EMBEDDING_MODEL', 'openai/text-embedding-3-small').strip(),
            openai_rerank_model=os.getenv('OPENAI_RERANK_MODEL', 'openai/gpt-5-mini').strip(),
            chroma_dir=chroma_dir_path,
            meme_collection=os.getenv('MEME_COLLECTION', 'memes'),
            retrieval_top_k=int(os.getenv('RETRIEVAL_TOP_K', 5)),
            telegram_request_timeout_seconds=float(os.getenv('telegram_request_timeout_seconds', 120.0)),
            telegram_retry_delay_seconds=float(os.getenv('telegram_retry_delay_seconds', 5.0)),
            telegram_retry_delay_max_seconds=float(os.getenv('telegram_retry_delay_max_seconds', 60.0)),
            local_reranker_model_path=os.getenv("LOCAL_RERANKER_MODEL_PATH", "").strip(),
            local_retrieval_model_path=os.getenv("LOCAL_RETRIEVAL_MODEL_PATH", "").strip(),
            local_retrieval_use_e5_prefixes=os.getenv(
                "LOCAL_RETRIEVAL_USE_E5_PREFIXES", 
                "true").strip().lower() in {"1", "true", "yes", "y"},
            database_url=os.getenv("DATABASE_URL", "").strip(),
        )