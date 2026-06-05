# engines/topic_engine.py
import time
from collections import deque

class DynamicTopicAnalyzer:
    def __init__(self):
        print("Topic detector ready")
        self.buffer = deque(maxlen=20)
        self.last = 0
        self.current = {"name": "No topic", "confidence": 0, "keywords": []}

    def analyze(self, text):
        if not text or len(text) < 50:
            return self.current
        
        self.buffer.append(text)
        
        if len(self.buffer) >= 3 or (time.time() - self.last) > 8:
            self.last = time.time()
            combined = " ".join(self.buffer).lower()
            
            topics = {
                'Algorithms': ['algorithm', 'sort', 'search', 'bubble', 'quick', 'merge', 'tree', 'array'],
                'Databases': ['database', 'sql', 'table', 'query', 'join', 'index'],
                'Networks': ['network', 'server', 'client', 'tcp', 'udp', 'http', 'router', 'ip'],
                'Web': ['web', 'html', 'css', 'javascript', 'react', 'api'],
                'Programming': ['python', 'java', 'variable', 'function', 'class', 'loop'],
                'Security': ['security', 'encryption', 'firewall', 'hacking', 'virus'],
                'AI': ['ai', 'machine learning', 'neural', 'model', 'training'],
                'Cloud': ['cloud', 'docker', 'kubernetes', 'aws', 'azure']
            }
            
            scores = {}
            for topic, keywords in topics.items():
                score = sum(1 for kw in keywords if kw in combined)
                scores[topic] = score
            
            best = max(scores, key=scores.get)
            best_score = scores[best]
            confidence = min(85, 35 + best_score * 10) if best_score > 0 else 30
            
            words = combined.split()
            stopwords = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'are'}
            keywords = [w for w in words if w not in stopwords and len(w) > 3][:5]
            
            self.current = {
                "name": best if best_score > 0 else "General IT",
                "confidence": confidence,
                "keywords": keywords
            }
            
            if best_score > 0:
                print(f"Topic: {best} ({confidence}%)")
        
        return self.current
    
    def reset(self):
        self.buffer.clear()
        self.current = {"name": "No topic", "confidence": 0, "keywords": []}