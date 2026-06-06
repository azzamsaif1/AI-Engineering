# backend/vector_db/qdrant_client.py
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

class QdrantVectorStore:
    def __init__(self, host="localhost", port=6333, collection="tech_concepts"):
        self.client = QdrantClient(host=host, port=port)
        self.collection = collection
        self._ensure_collection()
    
    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection for c in collections):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
            )
    
    def upsert(self, point_id, vector, payload):
        from qdrant_client.models import PointStruct
        point = PointStruct(id=point_id, vector=vector, payload=payload)
        self.client.upsert(collection_name=self.collection, points=[point])
    
    def search(self, query_vector, top_k=10):
        return self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=top_k
        )