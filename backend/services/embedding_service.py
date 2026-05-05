from typing import List
from sentence_transformers import SentenceTransformer

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
    
    
        