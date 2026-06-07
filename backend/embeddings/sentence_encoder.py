# backend/embeddings/sentence_encoder.py
import numpy as np


class TechnicalEncoder:
    """Thin wrapper over the shared BGE-M3 encoder.

    Reuses the singleton model held by the Self-Adaptive Understanding Layer
    (`_SharedModels`) so BGE-M3 is loaded at most once process-wide instead of
    once per component.
    """

    def __init__(self, model_name='BAAI/bge-m3'):
        from backend.nlp.smart_understanding_layer import _models
        self._shared = _models
        self._model_name = model_name

    @property
    def model(self):
        return self._shared.encoder

    @property
    def dimension(self):
        return self.model.get_sentence_embedding_dimension()

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, normalize_embeddings=True)

    def similarity(self, text1, text2):
        emb1 = self.encode([text1])[0]
        emb2 = self.encode([text2])[0]
        return float(np.dot(emb1, emb2))
