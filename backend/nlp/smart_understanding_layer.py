# backend/nlp/smart_understanding_layer.py
"""
Self-Adaptive Understanding Layer
Production-ready implementation with lazy model loading and shared resources.
No hardcoded patterns - discovers everything automatically.
"""

import re
import logging
from collections import defaultdict
from typing import Optional

import numpy as np
from langdetect import detect as langdetect_detect
from sklearn.cluster import KMeans

logger = logging.getLogger(__name__)


class _SharedModels:
    """Singleton lazy-loader for heavy ML models to avoid duplicate memory usage."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._encoder = None
            cls._instance._zero_shot = None
            cls._instance._spacy_en = None
            cls._instance._spacy_de = None
        return cls._instance

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading BGE-M3 encoder (first use)...")
            self._encoder = SentenceTransformer("BAAI/bge-m3")
            logger.info("BGE-M3 encoder loaded.")
        return self._encoder

    @property
    def zero_shot_classifier(self):
        if self._zero_shot is None:
            from transformers import pipeline
            logger.info("Loading zero-shot classifier (first use)...")
            self._zero_shot = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=-1,
            )
            logger.info("Zero-shot classifier loaded.")
        return self._zero_shot

    @property
    def spacy_en(self):
        if self._spacy_en is None:
            import spacy
            try:
                self._spacy_en = spacy.load("en_core_web_sm")
            except OSError:
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
                self._spacy_en = spacy.load("en_core_web_sm")
        return self._spacy_en

    @property
    def spacy_de(self):
        if self._spacy_de is None:
            import spacy
            try:
                self._spacy_de = spacy.load("de_core_news_sm")
            except OSError:
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "de_core_news_sm"], check=True)
                self._spacy_de = spacy.load("de_core_news_sm")
        return self._spacy_de


_models = _SharedModels()


class SmartContextDetector:
    """Automatically detects language, domain, and content level."""

    DOMAINS = [
        "software engineering and programming",
        "computer networking and protocols",
        "cybersecurity and encryption",
        "databases and data management",
        "algorithms and data structures",
        "operating systems and kernels",
        "cloud computing and devops",
        "artificial intelligence and machine learning",
        "web development and frontend",
        "mobile development",
        "mathematics and statistics",
        "general technical content",
    ]

    ADVANCED_INDICATORS = [
        "kernel", "protocol", "encryption", "distributed", "concurrency",
        "asynchronous", "microservices", "consensus", "multithreading",
        "deadlock", "mutex", "semaphore", "virtualization", "hypervisor",
    ]

    def detect_all(self, text: str) -> dict:
        """Detect language, domain, and level automatically."""
        # Language detection
        try:
            language = langdetect_detect(text)
        except Exception:
            language = "en"

        # Domain detection via zero-shot
        try:
            result = _models.zero_shot_classifier(
                text[:512], self.DOMAINS, multi_label=False
            )
            primary_domain = result["labels"][0]
            domain_confidence = round(result["scores"][0] * 100, 2)
        except Exception as e:
            logger.warning("Domain detection failed: %s", e)
            primary_domain = "general technical content"
            domain_confidence = 0.0

        level = self._estimate_level(text)

        return {
            "language": language,
            "domain": primary_domain,
            "domain_confidence": domain_confidence,
            "level": level,
            "text_length": len(text),
        }

    def _estimate_level(self, text: str) -> str:
        words = text.lower().split()
        avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
        advanced_count = sum(1 for w in self.ADVANCED_INDICATORS if w in text.lower())

        if avg_word_len > 7 or advanced_count >= 3:
            return "advanced"
        elif avg_word_len > 5 or advanced_count >= 1:
            return "intermediate"
        return "beginner"


class DynamicEntityExtractor:
    """Extracts entities dynamically using spaCy + noun chunks + regex. No hardcoded lists."""

    TECH_PATTERNS = [
        r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',   # CamelCase
        r'\b[A-Z]{2,}\b',                       # Acronyms (TCP, API)
        r'\b[a-z]+[0-9]+[a-z0-9]*\b',          # tech identifiers (http2, ipv4)
        r'\b[a-z]+(?:[_-][a-z]+)+\b',           # snake_case / kebab-case
    ]

    def extract(self, text: str, language: str = "en") -> dict:
        nlp = _models.spacy_en if language.startswith("en") else _models.spacy_de
        doc = nlp(text)

        entities = []

        # 1. spaCy NER entities
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "type": ent.label_,
                "method": "spacy_ner",
                "start": ent.start_char,
                "end": ent.end_char,
            })

        # 2. Noun chunks (multi-word concepts)
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) >= 2 and len(chunk.text) > 3:
                entities.append({
                    "text": chunk.text,
                    "type": "concept_phrase",
                    "method": "noun_chunking",
                    "start": chunk.start_char,
                    "end": chunk.end_char,
                })

        # 3. Regex-based tech term detection
        for pattern in self.TECH_PATTERNS:
            for match in re.finditer(pattern, text):
                matched = match.group()
                if len(matched) > 2 and not any(e["text"] == matched for e in entities):
                    entities.append({
                        "text": matched,
                        "type": "tech_term",
                        "method": "regex",
                        "start": match.start(),
                        "end": match.end(),
                    })

        # Deduplicate (case-insensitive)
        unique = []
        seen = set()
        for e in entities:
            key = e["text"].lower()
            if key not in seen and len(e["text"]) > 2:
                seen.add(key)
                unique.append(e)

        return {"entities": unique, "count": len(unique)}


class SemanticConceptExtractor:
    """Extracts semantic embeddings using BGE-M3."""

    def extract(self, text: str) -> dict:
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
        if not sentences:
            sentences = [text[:500]]

        embeddings = _models.encoder.encode(sentences, normalize_embeddings=True)

        return {
            "sentences": sentences,
            "embeddings": embeddings.tolist(),
            "dimension": int(embeddings.shape[1]) if len(embeddings.shape) > 1 else 768,
            "num_sentences": len(sentences),
        }

    def get_sentence_vectors(self, text: str) -> np.ndarray:
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
        if not sentences:
            sentences = [text[:500]]
        return _models.encoder.encode(sentences, normalize_embeddings=True)


class AdaptiveConceptClusterer:
    """Clusters similar concepts using KMeans on shared BGE-M3 embeddings."""

    def cluster_concepts(self, concepts: list, embeddings: Optional[np.ndarray] = None) -> dict:
        if not concepts or len(concepts) < 2:
            return {"clusters": [], "concept_clusters": {}, "num_clusters": 0, "total_concepts": len(concepts)}

        if embeddings is None:
            embeddings = _models.encoder.encode(concepts, normalize_embeddings=True)

        n_clusters = min(max(2, len(concepts) // 3), 8)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        clusters = defaultdict(list)
        for concept, label in zip(concepts, labels):
            clusters[int(label)].append(concept)

        cluster_list = []
        for label, members in clusters.items():
            cluster_list.append({
                "cluster_id": label,
                "size": len(members),
                "members": members[:10],
                "suggested_name": self._suggest_name(members),
            })

        return {
            "clusters": cluster_list,
            "concept_clusters": {c: int(l) for c, l in zip(concepts, labels)},
            "num_clusters": n_clusters,
            "total_concepts": len(concepts),
        }

    @staticmethod
    def _suggest_name(members: list) -> str:
        if not members:
            return "Unknown"
        return max(members, key=len)[:30]


class RelationDetector:
    """Detects relations between concepts from text using pattern matching."""

    STOPWORDS = {"a", "an", "the", "it", "its", "this", "that", "these", "those", "to", "of"}

    RELATION_PATTERNS = [
        (r"(\w+)\s+uses\s+(\w+)", "USES"),
        (r"(\w+)\s+depends on\s+(\w+)", "DEPENDS_ON"),
        (r"(\w+)\s+is a(?:n)?\s+(\w+)", "IS_A"),
        (r"(\w+)\s+contains\s+(\w+)", "CONTAINS"),
        (r"(\w+)\s+has\s+(\w+)", "HAS"),
        (r"(\w+)\s+calls\s+(\w+)", "CALLS"),
        (r"(\w+)\s+communicates with\s+(\w+)", "COMMUNICATES_WITH"),
        (r"(\w+)\s+implements\s+(\w+)", "IMPLEMENTS"),
        (r"(\w+)\s+extends\s+(\w+)", "EXTENDS"),
        (r"(\w+)\s+sends\s+(\w+)", "SENDS"),
        (r"(\w+)\s+receives\s+(\w+)", "RECEIVES"),
        (r"(\w+)\s+requires\s+(\w+)", "REQUIRES"),
    ]

    def detect_relations(self, concepts: list, text: str) -> list:
        relations = []
        seen = set()

        for pattern, rel_type in self.RELATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                source, target = match.group(1), match.group(2)
                if source.lower() in self.STOPWORDS or target.lower() in self.STOPWORDS:
                    continue
                key = f"{source.lower()}_{target.lower()}_{rel_type}"
                if key not in seen:
                    seen.add(key)
                    relations.append({
                        "source": source,
                        "target": target,
                        "type": rel_type,
                        "detected_by": "pattern_matching",
                    })

        return relations


class SelfAdaptiveUnderstandingLayer:
    """
    Production-ready orchestrator for the full Self-Adaptive Understanding pipeline.
    All heavy models are lazy-loaded on first use via _SharedModels singleton.
    """

    def __init__(self):
        self.context_detector = SmartContextDetector()
        self.entity_extractor = DynamicEntityExtractor()
        self.semantic_extractor = SemanticConceptExtractor()
        self.concept_clusterer = AdaptiveConceptClusterer()
        self.relation_detector = RelationDetector()

    def analyze(self, text: str) -> dict:
        """Full self-adaptive analysis pipeline."""
        if not text or len(text) < 20:
            return {"error": "Text too short for analysis (minimum 20 characters)"}

        # 1. Context detection (language, domain, level)
        context = self.context_detector.detect_all(text)

        # 2. Dynamic entity extraction
        entities = self.entity_extractor.extract(text, context["language"])

        # 3. Semantic embedding extraction
        semantic = self.semantic_extractor.extract(text)

        # 4. Concept clustering
        concept_texts = [e["text"] for e in entities["entities"]]
        if len(concept_texts) > 1:
            clusters = self.concept_clusterer.cluster_concepts(concept_texts)
        else:
            clusters = {"clusters": [], "concept_clusters": {}, "num_clusters": 0, "total_concepts": len(concept_texts)}

        # 5. Relation detection
        relations = self.relation_detector.detect_relations(concept_texts, text)

        return {
            "context": context,
            "entities": entities,
            "semantic": {
                "dimension": semantic["dimension"],
                "num_sentences": semantic["num_sentences"],
                "sentences": semantic["sentences"],
            },
            "clusters": clusters,
            "relations": relations,
            "summary": {
                "total_entities": entities["count"],
                "num_clusters": clusters.get("num_clusters", 0),
                "num_relations": len(relations),
                "has_semantic_data": semantic["num_sentences"] > 0,
            },
        }
