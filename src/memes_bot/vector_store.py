from __future__ import annotations
import logging

import chromadb
from chromadb.api.models.Collection import Collection
from pathlib import Path

# постоянное подключение к векторной базе данных
def get_collection(chroma_dir: Path, collection_name: str) -> Collection:
    client = chromadb.PersistentClient(path=str(chroma_dir))
    return client.get_or_create_collection(name=collection_name)


def reset_collection(chroma_dir: Path, collection_name: str) -> Collection:
    client = chromadb.PersistentClient(path=str(chroma_dir))
    try:
        client.delete_collection(name=collection_name)
    except Exception as exc:
        logging.info(
            "Chroma collection '%s' was not deleted before reset: %s",
            collection_name,
            exc,
        )
    return client.get_or_create_collection(name=collection_name)