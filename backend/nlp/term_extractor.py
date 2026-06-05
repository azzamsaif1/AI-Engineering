# backend/nlp/term_extractor.py
"""
Technical Term Extractor - Dynamic extraction without hardcoded lists.
Replaced with Self-Adaptive approach using spaCy NER + noun chunking + regex.
Maintains backward-compatible extract_terms() interface.
"""

import re
import logging

logger = logging.getLogger(__name__)


class TechnicalTermExtractor:
    """Dynamic technical term extractor - no hardcoded pattern lists."""

    TECH_PATTERNS = [
        r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',   # CamelCase
        r'\b[A-Z]{2,}\b',                       # Acronyms (TCP, API, DMA)
        r'\b[a-z]+[0-9]+[a-z0-9]*\b',          # tech identifiers (http2, ipv4)
        r'\b[a-z]+(?:[_-][a-z]+)+\b',           # snake_case / kebab-case
    ]

    def __init__(self):
        self._nlp_en = None
        self._nlp_de = None

    @property
    def nlp_en(self):
        if self._nlp_en is None:
            import spacy
            try:
                self._nlp_en = spacy.load("en_core_web_sm")
            except OSError:
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
                self._nlp_en = spacy.load("en_core_web_sm")
        return self._nlp_en

    @property
    def nlp_de(self):
        if self._nlp_de is None:
            import spacy
            try:
                self._nlp_de = spacy.load("de_core_news_sm")
            except OSError:
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "de_core_news_sm"], check=True)
                self._nlp_de = spacy.load("de_core_news_sm")
        return self._nlp_de

    def extract_terms(self, text: str, language: str = "en") -> dict:
        """
        Extract technical terms dynamically using multiple methods.
        Returns: {'terms': [...], 'count': int}
        """
        nlp = self.nlp_en if language.startswith("en") else self.nlp_de
        doc = nlp(text)

        terms = []

        # 1. spaCy NER entities
        for ent in doc.ents:
            terms.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "method": "spacy_ner",
            })

        # 2. Noun chunks (multi-word concepts)
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) >= 2 and len(chunk.text) > 3:
                terms.append({
                    "text": chunk.text,
                    "label": "CONCEPT",
                    "start": chunk.start_char,
                    "end": chunk.end_char,
                    "method": "noun_chunking",
                })

        # 3. Regex-based technical term detection
        for pattern in self.TECH_PATTERNS:
            for match in re.finditer(pattern, text):
                matched = match.group()
                if len(matched) > 2 and not any(t["text"] == matched for t in terms):
                    terms.append({
                        "text": matched,
                        "label": "TECH_TERM",
                        "start": match.start(),
                        "end": match.end(),
                        "method": "regex",
                    })

        # Deduplicate
        unique = []
        seen = set()
        for t in terms:
            key = t["text"].lower()
            if key not in seen and len(t["text"]) > 2:
                seen.add(key)
                unique.append(t)

        return {"terms": unique, "count": len(unique)}
