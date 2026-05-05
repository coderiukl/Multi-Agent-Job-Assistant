from typing import List, Dict
from sentence_transformers import SentenceTransformer
import re

from fastembed import SparseTextEmbedding

SparseVectorDict = Dict[str, List[int] | List[float]]

class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str | None = None, normalize_embeddings: bool = True):
        self.model = SentenceTransformer(model_name, device=device)
        self.normalize_embeddings = normalize_embeddings
        self.dimension = self.model.get_embedding_dimension()

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]
    
    def embed_texts(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()
    
class SparseEmbeddingService:
    def __init__(self, model_name: str = "Qdrant/bm25", min_text_length: int = 1, max_text_length: int = 12000):
        self.model_name = model_name
        self.min_text_length = min_text_length
        self.max_text_length = max_text_length

        print(f"[Sparse] Loading sparse model: {model_name}")

        try:
            self.model = SparseTextEmbedding(model_name=model_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load sparse embedding model '{model_name}': {e}") from e
        
        print("[Sparse] Sparse model loaded.")

    def embed_text(self, text: str) -> SparseVectorDict:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: List[str]) -> dict[SparseVectorDict]:
        if not texts:
            return None

        normalized_texts = [self._normalize_text(text) for text in texts]

        try:
            embeddings = self.model.embed(normalized_texts)
        except Exception as e:
            raise RuntimeError(f"Failed to create sparse embeddings: {e}") from e
        
        results: List[SparseVectorDict] = []
        
        for embedding in embeddings:
            indices = embedding.indices.tolist()
            values = embedding.values.tolist()

            results.append({
                "indices": [int(index) for index in indices],
                "values": [float(value) for value in values]
            })

        return results
    
    def _normalize_text(self, text: str) -> str:
        text = (text or "").replace("\x00", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = text.strip()

        if len(text) < self.min_text_length:
            return "empty"

        return text[:self.max_text_length]