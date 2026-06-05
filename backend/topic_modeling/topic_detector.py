# backend/topic_modeling/topic_detector.py
from sentence_transformers import SentenceTransformer

class SmartTopicDetector:
    def __init__(self):
        self.encoder = SentenceTransformer("BAAI/bge-m3")
    
    def get_topic_for_text(self, text):
        # نسخة مبسطة - بدون BERTopic لتوفير الموارد
        return {
            'topic_id': 0,
            'name': text[:50] if len(text) > 50 else text,
            'confidence': 0.7
        }