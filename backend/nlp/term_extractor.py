# backend/nlp/term_extractor.py
import spacy
import re

class TechnicalTermExtractor:
    def __init__(self):
        try:
            self.nlp_en = spacy.load("en_core_web_sm")
        except:
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp_en = spacy.load("en_core_web_sm")
        
        try:
            self.nlp_de = spacy.load("de_core_news_sm")
        except:
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "de_core_news_sm"])
            self.nlp_de = spacy.load("de_core_news_sm")
    
    def extract_terms(self, text, language='en'):
        nlp = self.nlp_en if language == 'en' else self.nlp_de
        doc = nlp(text)
        
        terms = []
        for ent in doc.ents:
            terms.append({
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char
            })
        
        return {'terms': terms, 'count': len(terms)}