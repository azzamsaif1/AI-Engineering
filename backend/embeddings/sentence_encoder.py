# backend/embeddings/sentence_encoder.py
from sentence_transformers import SentenceTransformer
import numpy as np

class TechnicalEncoder:
    def __init__(self, model_name='BAAI/bge-m3'):
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
    
    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, normalize_embeddings=True)
    
    def similarity(self, text1, text2):
        emb1 = self.encode([text1])[0]
        emb2 = self.encode([text2])[0]
        return float(np.dot(emb1, emb2))