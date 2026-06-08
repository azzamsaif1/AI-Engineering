# backend/memory/vector_memory.py
"""
Stage 2 — Layer 9: Vector Memory Integration (long-term semantic memory).

A per-user long-term memory backed by Qdrant + the shared BGE-M3 encoder. Every
learning interaction (a Smart-Understanding analysis, a flagged term, a question,
...) can be *remembered* as a 1024-dim vector with structured payload, then later
*recalled* by semantic similarity, scoped to a single user.

Design notes / reuse:
- Reuses the same BGE-M3 encoder singleton (`TechnicalEncoder` → `_SharedModels`)
  used everywhere else, so no extra model is loaded.
- Uses a dedicated Qdrant collection (default ``learning_memory``) separate from
  the concept collection (``tech_concepts``), with **payload-based user scoping**
  (a single collection + ``user_id`` filter) rather than one-collection-per-user,
  which scales to many users without exploding Qdrant collection count.
- Cosine distance on normalized embeddings (the encoder normalizes), matching the
  existing vector store.

This is a production module: it talks to a real Qdrant instance and stores/reads
real vectors. There are no mocks or placeholders.
"""

import logging
import time
import uuid
from collections import Counter
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Direction,
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    OrderBy,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

# Kinds of memory we store. Free-form, but constrained to keep payloads tidy.
VALID_KINDS = {"analysis", "term", "question", "summary", "note", "code"}
DEFAULT_KIND = "analysis"


class VectorMemory:
    """Per-user long-term semantic memory over Qdrant."""

    def __init__(self, encoder, host="localhost", port=6333,
                 collection="learning_memory", dim=1024):
        self._encoder = encoder
        self._collection = collection
        self._dim = dim
        self._client = QdrantClient(host=host, port=port)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )
        # Ensure payload indexes (idempotent): user_id for fast filtering, and
        # created_at so Qdrant-side `order_by` works for the timeline. Running this
        # outside the create branch also upgrades pre-existing collections.
        for field, schema in (("user_id", "integer"), ("created_at", "float")):
            try:
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field,
                    field_schema=schema,
                )
            except Exception:
                logger.debug("payload index for %s already exists or unsupported", field)

    # ------------------------------------------------------------------ #
    def _embed(self, text: str):
        vec = self._encoder.encode([text])[0]
        # encoder returns a numpy array; Qdrant wants a plain list of floats
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)

    @staticmethod
    def _user_filter(user_id: int, kind: Optional[str] = None) -> Filter:
        must = [FieldCondition(key="user_id", match=MatchValue(value=int(user_id)))]
        if kind:
            must.append(FieldCondition(key="kind", match=MatchValue(value=kind)))
        return Filter(must=must)

    # ------------------------------------------------------------------ #
    def remember(self, user_id: int, text: str, kind: str = DEFAULT_KIND,
                 metadata: Optional[dict] = None) -> Optional[str]:
        """Store a memory for ``user_id``. Returns the new point id (uuid) or None."""
        if not text or not text.strip():
            return None
        kind = kind if kind in VALID_KINDS else DEFAULT_KIND
        point_id = str(uuid.uuid4())
        payload = {
            "user_id": int(user_id),
            "kind": kind,
            "text": text[:2000],
            "created_at": time.time(),
        }
        if metadata:
            # keep only JSON-serializable scalars/short lists
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    payload[k] = v
                elif isinstance(v, (list, tuple)):
                    payload[k] = list(v)[:10]
        self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=point_id, vector=self._embed(text), payload=payload)],
        )
        return point_id

    def recall(self, user_id: int, query: str, top_k: int = 5,
               kind: Optional[str] = None) -> list:
        """Return the user's most semantically similar past memories to ``query``."""
        if not query or not query.strip():
            return []
        hits = self._client.query_points(
            collection_name=self._collection,
            query=self._embed(query),
            query_filter=self._user_filter(user_id, kind),
            limit=top_k,
        ).points
        out = []
        for h in hits:
            p = h.payload or {}
            out.append({
                "id": h.id,
                "score": round(float(h.score), 4),
                "text": p.get("text", ""),
                "kind": p.get("kind"),
                "domain": p.get("domain"),
                "created_at": p.get("created_at"),
            })
        return out

    def timeline(self, user_id: int, limit: int = 50) -> list:
        """Return the user's most recent memories (newest first).

        Uses Qdrant-side ``order_by(created_at DESC)`` so we get the actual N most
        recent memories; a plain ``scroll(limit=...)`` returns points in point-id
        (UUID) order, which is unrelated to insertion time.
        """
        points, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=self._user_filter(user_id),
            limit=limit,
            with_payload=True,
            with_vectors=False,
            order_by=OrderBy(key="created_at", direction=Direction.DESC),
        )
        return [{
            "id": pt.id,
            "text": (pt.payload or {}).get("text", ""),
            "kind": (pt.payload or {}).get("kind"),
            "domain": (pt.payload or {}).get("domain"),
            "created_at": (pt.payload or {}).get("created_at", 0),
        } for pt in points]

    def profile(self, user_id: int, sample: int = 500) -> dict:
        """Aggregate the user's memories into a 'learning fingerprint'."""
        points, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=self._user_filter(user_id),
            limit=sample,
            with_payload=True,
            with_vectors=False,
        )
        domains, kinds, languages, levels = Counter(), Counter(), Counter(), Counter()
        timestamps = []
        for pt in points:
            p = pt.payload or {}
            if p.get("domain"):
                domains[p["domain"]] += 1
            if p.get("kind"):
                kinds[p["kind"]] += 1
            if p.get("language"):
                languages[p["language"]] += 1
            if p.get("level"):
                levels[p["level"]] += 1
            if p.get("created_at"):
                timestamps.append(p["created_at"])
        return {
            "total_memories": len(points),
            "top_domains": [{"domain": d, "count": c} for d, c in domains.most_common(5)],
            "by_kind": dict(kinds),
            "by_language": dict(languages),
            "by_level": dict(levels),
            "first_seen": min(timestamps) if timestamps else None,
            "last_seen": max(timestamps) if timestamps else None,
        }

    def forget(self, user_id: int) -> bool:
        """Delete all memories for a user (privacy / reset)."""
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(filter=self._user_filter(user_id)),
        )
        return True
