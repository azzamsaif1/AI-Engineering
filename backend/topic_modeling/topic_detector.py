# backend/topic_modeling/topic_detector.py
"""Lightweight topic descriptor.

Note: this is a minimal descriptor used by the legacy /api/smart_analyze (v1).
It intentionally does NOT load an embedding model — the previous version loaded
BGE-M3 (~2.3 GB) in __init__ and never used it. Semantic domain detection lives
in backend.nlp.smart_understanding_layer (SmartContextDetector).
"""


class SmartTopicDetector:
    def get_topic_for_text(self, text):
        snippet = text[:50] if len(text) > 50 else text
        return {
            'topic_id': 0,
            'name': snippet,
            'confidence': 0.7,
        }
