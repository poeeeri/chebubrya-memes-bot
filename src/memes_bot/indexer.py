from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
from typing import Iterable

from .config import Settings
from pathlib import Path
from .vector_store import get_collection
from .client import build_openai_client, embed_texts


@dataclass(frozen=True)
class MemeRecord:
    meme_id: str
    image_path: str
    summary: str
    source_row: int

# загружаем мемы и преобразуем в список объектов MemeRecord
def load_memes_from_df(
        df: pd.DataFrame,
        image_column: str,
        text_columns: Iterable[str]
) -> list[MemeRecord]:
    records: list[MemeRecord] = []
    for row_idx, row in df.iterrows():
        image_path = str(row.get(image_column, '')).strip()
        if not image_path:
            continue
        parts = []
        for column in text_columns:
            value = str(row.get(column, "")).strip()
            if value and value.lower() != 'nan':
                parts.append(f'{column}: {value}')
        
        summary = ' | '.join(parts)
        if not summary:
            continue
            
        meme_id = str(row.get('meme_id', f'meme_{row_idx + 1:04d}')).strip()
        records.append(
            MemeRecord(
                meme_id=meme_id,
                image_path=image_path,
                summary=summary,
                source_row=row_idx
            )
        )
    return records


# индексация мемов в векторной бд
def index_meme(
        dataset_path: Path,
        image_column: str,
        text_columns: list[str],
        settings: Settings
) -> int:
    dataset_path = dataset_path.resolve()
    df = pd.read_csv(dataset_path, encoding='cp1251', sep=';')
    records = load_memes_from_df(df, image_column=image_column, text_columns=text_columns)
    if not records:
        raise RuntimeError(
            "для индексации не найдено подходящих строк"
        )
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    collection = get_collection(settings.chroma_dir, settings.meme_collection)
    client = build_openai_client(settings)
    embeddings = embed_texts(client, settings.openai_embedding_model, [record.summary for record in records])
    
    metadatas = []
    ids = []
    documents = []
    for record in records:
        resolved_image = _resolve_image_path(dataset_path.parent, record.image_path)
        ids.append(record.meme_id)
        documents.append(record.summary)
        metadatas.append(
            {
                "image_path": str(resolved_image),
                "summary": record.summary,
                "source_row": record.source_row,
            }
        )

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    return len(records)


def _resolve_image_path(base_dir: Path, image_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()