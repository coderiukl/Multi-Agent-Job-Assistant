from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams
)

class QdrantService:
    def __init__(self, collection_name: str, url: str = "http://localhost:6333", api_key: Optional[str] =  None, vector_size: int = 1024):
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.client = QdrantClient(
            url=url,
            api_key=api_key
        )

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
    
    def upsert(self, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        if ids is None:
            ids = [str(uuid4()) for _ in vectors]
        points = [
            PointStruct(
                id=ids[i],
                vector=vectors[i],
                payload=payloads[i],
            )
            for i in range(len(vectors))
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

        return ids

    def search(self, query_vector: List[float], limit: int = 10, filters: Optional[Dict[str, Any]] = None):
        query_filter = self._build_filter(filters) if filters else None

        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
    
    def delete(self, ids: List[str]) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=ids,
        )

    def delete_collection(self) -> None:
        self.client.delete_collection(
            collection_name=self.collection_name
        )

    def _build_filter(self, filters: Dict[str, Any]) -> Filter:
        return Filter(
            must=[
                FieldCondition(
                    key=key,
                    match=MatchValue(value=value),
                )
                for key, value in filters.items()
            ]
        )