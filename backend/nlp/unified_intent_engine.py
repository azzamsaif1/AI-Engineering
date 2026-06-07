# backend/nlp/unified_intent_engine.py
"""
UnifiedIntentEngine — the single source of truth for text intent / topic
classification across the whole application.

It is a thin wrapper over ``SelfAdaptiveUnderstandingLayer`` so that EVERY entry
point (REST API, audio / real-time transcript pipeline, and the frontend) shares
one semantic pipeline:

    * language detection      (langdetect)
    * domain inference        (zero-shot, semantic — NOT keyword matching)
    * semantic clustering     (KMeans over BGE-M3 embeddings)
    * confidence scoring      (zero-shot score)

There is intentionally **no keyword / category table** here. The previous
hardcoded classifiers (``engines.topic_engine.DynamicTopicAnalyzer`` and
``app.TOPIC_CATEGORIES`` / ``detect_topic_from_text``) have been removed; this
engine replaces both.

The only lookups below are *presentation* helpers (an emoji + a colour for a
given semantic domain label). They never influence the classification decision —
that is produced entirely by the semantic layer — they only theme the topic card
so the frontend does not have to re-derive an icon from keywords.
"""

import hashlib
import logging
import threading
import time
from typing import Optional

from backend.nlp.smart_understanding_layer import SelfAdaptiveUnderstandingLayer

logger = logging.getLogger(__name__)


# --- Presentation only (icon per semantic domain label). Keyed on the labels
# produced by SmartContextDetector.DOMAINS — these do NOT classify anything. ---
_DOMAIN_ICONS = {
    "software engineering and programming": "💻",
    "computer networking and protocols": "🌐",
    "cybersecurity and encryption": "🔒",
    "databases and data management": "🗄️",
    "algorithms and data structures": "🧠",
    "operating systems and kernels": "⚙️",
    "cloud computing and devops": "☁️",
    "artificial intelligence and machine learning": "🤖",
    "web development and frontend": "🌍",
    "mobile development": "📱",
    "mathematics and statistics": "📐",
    "general technical content": "📚",
}
_DEFAULT_ICON = "📚"


class UnifiedIntentEngine:
    """Single entry point for topic / intent understanding.

    Use :meth:`analyze` for the full semantic payload (same shape as
    ``SelfAdaptiveUnderstandingLayer.analyze``) and :meth:`detect_topic` for the
    compact, frontend-ready topic descriptor used by the audio / real-time path
    and ``/api/topic/detect``.
    """

    _instance: Optional["UnifiedIntentEngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self, layer: Optional[SelfAdaptiveUnderstandingLayer] = None,
                 cache_ttl: float = 8.0, min_chars: int = 20):
        self._layer = layer or SelfAdaptiveUnderstandingLayer()
        self._cache_ttl = cache_ttl
        self._min_chars = min_chars
        # Real-time debounce cache: avoid re-running the heavy pipeline on the
        # audio path when the transcript hasn't meaningfully changed.
        self._cache_lock = threading.Lock()
        self._last_text: Optional[str] = None
        self._last_topic: Optional[dict] = None
        self._last_ts: float = 0.0

    @classmethod
    def instance(cls, layer: Optional[SelfAdaptiveUnderstandingLayer] = None) -> "UnifiedIntentEngine":
        """Process-wide singleton so all entry points share one engine + cache."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(layer=layer)
        return cls._instance

    # ------------------------------------------------------------------ #
    # Core semantic analysis (full payload)
    # ------------------------------------------------------------------ #
    def analyze(self, text: str) -> dict:
        """Full self-adaptive analysis — delegates to the semantic layer."""
        return self._layer.analyze(text)

    # ------------------------------------------------------------------ #
    # Compact topic descriptor (audio / real-time / topic API / frontend)
    # ------------------------------------------------------------------ #
    def detect_topic(self, text: str) -> dict:
        """Return a compact, frontend-ready topic descriptor.

        Debounced + cached on the real-time path: if the text is unchanged and
        the previous result is still fresh (``cache_ttl`` seconds) the cached
        descriptor is returned instead of re-running the pipeline.
        """
        if not text or len(text.strip()) < self._min_chars:
            return self._empty_topic()

        now = time.time()
        with self._cache_lock:
            if (self._last_topic is not None
                    and text == self._last_text
                    and (now - self._last_ts) < self._cache_ttl):
                return self._last_topic

        try:
            analysis = self._layer.analyze(text)
        except Exception:
            logger.exception("UnifiedIntentEngine.detect_topic analysis failed")
            return self._empty_topic()

        topic = self._to_topic(analysis)

        with self._cache_lock:
            self._last_text = text
            self._last_topic = topic
            self._last_ts = time.time()

        return topic

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _to_topic(self, analysis: dict) -> dict:
        if not analysis or analysis.get("error"):
            return self._empty_topic()

        context = analysis.get("context", {})
        domain = context.get("domain") or "general technical content"
        confidence = int(round(context.get("domain_confidence", 0) or 0))

        entities = analysis.get("entities", {}).get("entities", [])
        keywords = [e["text"] for e in entities if e.get("text")][:5]

        clusters = analysis.get("clusters", {}).get("clusters", [])
        subtopics = [c.get("suggested_name") for c in clusters if c.get("suggested_name")][:4]

        display_name = self._titlecase(domain)

        return {
            "category": self._slug(domain),
            "title": display_name,
            "name": display_name,          # legacy field (/api/topic/detect + audio)
            "display_name": display_name,
            "icon": _DOMAIN_ICONS.get(domain, _DEFAULT_ICON),
            "color": self._color_for(domain),
            "confidence": confidence,
            "keywords": keywords,
            "subtopics": subtopics,
            "language": context.get("language", "en"),
            "level": context.get("level", ""),
            "topic_id": self._stable_id(domain),
        }

    def _empty_topic(self) -> dict:
        return {
            "category": "general",
            "title": "General Technical Content",
            "name": "General Technical Content",
            "display_name": "General Technical Content",
            "icon": _DEFAULT_ICON,
            "color": self._color_for("general technical content"),
            "confidence": 0,
            "keywords": [],
            "subtopics": [],
            "language": "en",
            "level": "",
            "topic_id": self._stable_id("general technical content"),
        }

    @staticmethod
    def _titlecase(domain: str) -> str:
        # "computer networking and protocols" -> "Computer Networking and Protocols"
        small = {"and", "or", "of", "the", "for", "to", "in"}
        words = domain.split()
        out = []
        for i, w in enumerate(words):
            out.append(w if (w in small and i != 0) else w.capitalize())
        return " ".join(out)

    @staticmethod
    def _slug(domain: str) -> str:
        return "_".join(domain.lower().split())

    @staticmethod
    def _stable_id(domain: str) -> int:
        return int(hashlib.md5(domain.encode("utf-8")).hexdigest()[:8], 16)

    @staticmethod
    def _color_for(domain: str) -> str:
        """Deterministic colour derived from the domain label (presentation only)."""
        h = int(hashlib.md5(domain.encode("utf-8")).hexdigest(), 16)
        hue = h % 360
        return f"hsl({hue}, 70%, 55%)"
