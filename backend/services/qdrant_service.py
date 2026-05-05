from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    SparseVector,
    FusionQuery,
    Prefetch,
    Fusion
)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = 'sparse'

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
                vectors_config={
                    DENSE_VECTOR_NAME: VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: SparseVectorParams(
                        index=SparseIndexParams(on_disk=False)
                    )
                },
            )

            print(f"[Qdrant] Created collection '{self.collection_name}'"
                  "with named dense+sparse vectors.")
            return
        
        info = self.client.get_collection(self.collection_name)

        if not self._has_named_dense_vector(info):
            raise RuntimeError(
                f"Collection '{self.collection_name}' exists but does not use "
                f"named dense vector '{DENSE_VECTOR_NAME}'. "
                "Recreate or migrate the collection before enabling hybrid search."
            )
        
        if not self._has_sparse_vector(info):
            self.client.update_collection(
                collection_name=self.collection_name,
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: SparseVectorParams(
                        index = SparseIndexParams(on_disk=False)
                    )
                },
            )
        
        print(
                f"[Qdrant] Added sparse vector config to existing collection "
                f"'{self.collection_name}'."
            )
    
    def upsert(self, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids: Optional[List[str]] = None, sparse_vectors: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        self._validate_upsert_input(
            vectors=vectors,
            payloads=payloads,
            ids=ids,
            sparse_vectors=sparse_vectors
        )

        point_ids = ids or [str(uuid4()) for _ in vectors]
        points = []

        for index, vector in enumerate(vectors):
            named_vectors: Dict[str, Any] = {
                DENSE_VECTOR_NAME: vector,
            }

            if sparse_vectors is not None and sparse_vectors[index]:
                named_vectors[SPARSE_VECTOR_NAME] = self._to_sparse_vector(
                    sparse_vectors[index]
                )

            points.append(
                PointStruct(
                    id=point_ids[index],
                    vector=named_vectors,
                    payload=payloads[index],
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

        return point_ids

    def search(self, query_vector: List[float], limit: int = 10, filters: Optional[Dict[str, Any]] = None):
        query_filter = self._build_filter(filters) if filters else None

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using=DENSE_VECTOR_NAME,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return results.points

    def hybrid_search(self, query_dense: List[float], query_sparse: Dict[str, Any], limit: int = 10, filters: Optional[Dict[str, Any]] = None, prefetch_factor: int = 3):
        query_filter = self._build_filter(filters) if filters else None
        sparse_vector = self._to_sparse_vector(query_sparse)

        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=query_dense,
                    using=DENSE_VECTOR_NAME,
                    filter=query_filter,
                    limit=limit * prefetch_factor,
                ),
                Prefetch(
                    query=sparse_vector,
                    using=SPARSE_VECTOR_NAME,
                    filter=query_filter,
                    limit=limit * prefetch_factor
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
            with_vectors=False
        )

        return results.points
    
    def search_by_type(self, query_vector: List[float], item_type: str, limit: int = 10):
        return self.search(
            query_vector=query_vector,
            limit=limit,
            filters={"type": item_type},
        )
    
    def hybrid_search_by_type(self, query_dense: List[float], query_sparse: Dict[str, Any], item_type: str, limit: int = 10):
        return self.hybrid_search(
            query_dense=query_dense,
            query_sparse=query_sparse,
            limit=limit,
            filters={'type': item_type}
        )

    def delete(self, ids: List[str]) -> None:
        if not ids:
            return None
        
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=ids,
        )

    def delete_by_filter(self, filters: Dict[str, Any]) -> None:
        if not filters:
            raise ValueError("delete_by_filters requires at least on filter")
        
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=self._build_filter(filters)
        )

    def delete_collection(self) -> None:
        self.client.delete_collection(
            collection_name=self.collection_name
        )

    def _validate_upsert_input(self, vectors: List[List[float]], payloads: List[Dict[str, Any]], ids: Optional[List[str]], sparse_vectors: Optional[List[Dict[str, Any]]]) -> None:
        if not vectors:
            raise ValueError("vectors cannot be empty")
        
        if len(vectors) != len(payloads):
            raise ValueError("vectors and payloads must have the same length")
        
        if ids is not None and len(ids) != len(vectors):
            raise ValueError("ids and vectors must the same length")
        
        if sparse_vectors is not None and len(sparse_vectors) != len(vectors):
            raise ValueError("sparse_vectors and vectors must have the same length")
        
        for vector in vectors:
            if len(vector) != self.vector_size:
                raise ValueError(
                    f"Dense vector size mismatch. Expected {self.vector_size}, "
                    f"got {len(vector)}"
                )
            
    def _to_sparse_vector(self, sparse: Dict[str, Any]) -> SparseVector:
        indices = sparse.get("indices") or []
        values = sparse.get("values") or []

        if len(indices) != len(values):
            raise ValueError("Sparse vector indices and values must have the same length")
        
        return SparseVector(
            indices=[int(index) for index in indices],
            values=[float(value) for value in values]
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
    
    def _has_named_dense_vector(self, collection_info) -> bool:
        vectors_config = collection_info.config.params.vectors

        if isinstance(vectors_config, dict):
            return DENSE_VECTOR_NAME in vectors_config

        return False
    
    def _has_sparse_vector(self, collection_info) -> bool:
        sparse_config = collection_info.config.params.sparse_vectors

        if not sparse_config:
            return False

        return SPARSE_VECTOR_NAME in sparse_config