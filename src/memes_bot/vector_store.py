from __future__ import annotations

import chromadb
from chromadb.api.models.Collection import Collection
from pathlib import Path

# постоянное подключение к векторной базе данных
def get_collection(chroma_dir: Path, collection_name: str) -> Collection:
    client = chromadb.PersistentClient(path=str(chroma_dir))
    return client.get_or_create_collection(name=collection_name)