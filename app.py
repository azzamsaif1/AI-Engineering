import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import random
import re
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from deep_translator import GoogleTranslator
from engines.ghost_engine import GhostCoderEngine
from engines.prediction_engine import PredictionEngine
from flask_socketio import SocketIO, emit, join_room
from engines.topic_engine import DynamicTopicAnalyzer
import sys
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.nlp.term_extractor import TechnicalTermExtractor
from backend.embeddings.sentence_encoder import TechnicalEncoder
from backend.vector_db.qdrant_client import QdrantVectorStore
from backend.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from backend.topic_modeling.topic_detector import SmartTopicDetector
from backend.recommendation.roadmap_generator import RoadmapGenerator
from backend.nlp.smart_understanding_layer import SelfAdaptiveUnderstandingLayer
from backend.code_understanding.ast_analyzer import ASTAnalyzer
from backend.code_understanding.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)

# --- Lazy component registry (avoids crash if services/models not ready) ---
_components = {}

def _get_component(name):
    if name not in _components:
        try:
            if name == 'term_extractor':
                _components[name] = TechnicalTermExtractor()
            elif name == 'encoder':
                _components[name] = TechnicalEncoder()
            elif name == 'vector_store':
                host = os.environ.get('QDRANT_HOST', 'localhost')
                port = int(os.environ.get('QDRANT_PORT', '6333'))
                _components[name] = QdrantVectorStore(host=host, port=port)
            elif name == 'graph_builder':
                uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
                user = os.environ.get('NEO4J_USER', 'neo4j')
                password = os.environ.get('NEO4J_PASSWORD', 'password')
                _components[name] = KnowledgeGraphBuilder(uri=uri, user=user, password=password)
            elif name == 'topic_detector':
                _components[name] = SmartTopicDetector()
            elif name == 'roadmap_gen':
                _components[name] = RoadmapGenerator()
            elif name == 'smart_layer':
                _components[name] = SelfAdaptiveUnderstandingLayer()
            elif name == 'ast_analyzer':
                _components[name] = ASTAnalyzer()
            elif name == 'performance_analyzer':
                _components[name] = PerformanceAnalyzer()
        except Exception as e:
            logger.warning("Failed to initialize component '%s': %s", name, e)
            raise
    return _components[name]


def get_term_extractor():
    return _get_component('term_extractor')

def get_encoder():
    return _get_component('encoder')

def get_vector_store():
    return _get_component('vector_store')

def get_graph_builder():
    return _get_component('graph_builder')

def get_topic_detector():
    return _get_component('topic_detector')

def get_roadmap_gen():
    return _get_component('roadmap_gen')

def get_smart_layer():
    return _get_component('smart_layer')

def get_ast_analyzer():
    return _get_component('ast_analyzer')

def get_performance_analyzer():
    return _get_component('performance_analyzer')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'techlingua-secret-key-2024'
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== MODELS ====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    level = db.Column(db.String(20), default='A1')
    points = db.Column(db.Integer, default=0)

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active')
    words_analyzed = db.Column(db.Integer, default=0)
    new_terms = db.Column(db.Integer, default=0)
    questions_generated = db.Column(db.Integer, default=0)
    topic_category = db.Column(db.String(50), default='general')
    topic_title = db.Column(db.String(200), default='')
    topic_confidence = db.Column(db.Integer, default=0)
    topic_keywords = db.Column(db.Text, default='[]')

class Transcript(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    text = db.Column(db.Text, nullable=False)
    translation = db.Column(db.Text)
    is_final = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Term(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    term = db.Column(db.String(100), nullable=False)
    translation = db.Column(db.String(200))
    times_encountered = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    question_text = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    summary_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

class DigitalRival(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    accuracy = db.Column(db.Float, default=0.7)
    response_speed = db.Column(db.Float, default=2.0)
    last_updated = db.Column(db.DateTime, default=datetime.now)

class CompetitionSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')
    user_score = db.Column(db.Integer, default=0)

class CompetitionAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competition_session.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    question_text = db.Column(db.Text)
    user_answer = db.Column(db.Text)
    user_time = db.Column(db.Float)
    user_correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

class UserFingerprint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    weak_terms = db.Column(db.Text, default='[]')
    past_level = db.Column(db.String(20), default='A1')
    present_level = db.Column(db.String(20), default='A1')
    future_prediction = db.Column(db.String(20), default='A2')

class SmartNotebook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    term = db.Column(db.String(100))
    translation = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)

class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    focus_score = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.now)

# ==================== CREATE TABLES ====================
with app.app_context():
    db.create_all()

# ==================== AUTHENTICATION ====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html', current_user=current_user if current_user.is_authenticated else None)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({'success': True, 'username': user.username})
    return jsonify({'success': False, 'error': 'Invalid credentials'})

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': 'Username exists'})
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    
    rival = DigitalRival(user_id=new_user.id)
    db.session.add(rival)
    
    fingerprint = UserFingerprint(user_id=new_user.id)
    db.session.add(fingerprint)
    
    db.session.commit()
    login_user(new_user)
    return jsonify({'success': True, 'username': username})

@app.route('/logout')
def logout():
    logout_user()
    return jsonify({'success': True})

# ==================== SESSION API ====================
@app.route('/api/start_session', methods=['POST'])
@login_required
def start_session():
    new_session = Session(user_id=current_user.id)
    db.session.add(new_session)
    db.session.commit()
    
    focus = FocusSession(user_id=current_user.id, session_id=new_session.id)
    db.session.add(focus)
    db.session.commit()
    
    return jsonify({'session_id': new_session.id, 'success': True})

@app.route('/api/stop_session/<int:session_id>', methods=['POST'])
@login_required
def stop_session(session_id):
    session = Session.query.get(session_id)
    if session and session.user_id == current_user.id:
        session.end_time = datetime.now()
        session.duration = (session.end_time - session.start_time).seconds
        session.status = 'completed'
        db.session.commit()
        return jsonify({'success': True, 'duration': session.duration})
    return jsonify({'error': 'Session not found'}), 404

@app.route('/api/save_transcript', methods=['POST'])
def save_transcript():
    data = request.json
    session_id = data.get('session_id')
    text = data.get('text')
    is_final = data.get('is_final', False)
    
    if not session_id or not text:
        return jsonify({'error': 'Missing data'}), 400
    
    session = Session.query.get(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    transcript = Transcript(session_id=session_id, text=text, is_final=is_final)
    db.session.add(transcript)
    
    if is_final:
        words = len(text.split())
        session.words_analyzed = (session.words_analyzed or 0) + words
        
        all_text = ' '.join([t.text for t in Transcript.query.filter_by(session_id=session_id, is_final=True).all()])
        
        if len(all_text) > 100 and session.topic_confidence < 80:
            topic_data = detect_topic_from_text(all_text)
            
            session.topic_category = topic_data['category']
            session.topic_title = topic_data['title']
            session.topic_confidence = topic_data['confidence']
            session.topic_keywords = json.dumps(topic_data['keywords'])
            
            db.session.commit()
            
            from flask_socketio import emit
            emit('topic_detected', {
                'category': topic_data['category'],
                'title': topic_data['title'],
                'display_name': topic_data['display_name'],
                'icon': topic_data['icon'],
                'color': topic_data['color'],
                'confidence': topic_data['confidence'],
                'keywords': topic_data['keywords'],
                'subtopics': topic_data['subtopics']
            }, room=f"session_{session_id}", namespace='/')
    
    db.session.commit()
    return jsonify({'success': True})

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')

@app.route('/api/translate', methods=['POST'])
def translate():
    data = request.json
    text = data.get('text')
    target_lang = data.get('target_lang', 'ar')
    
    if not text:
        return jsonify({'error': 'No text'}), 400
    
    try:
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text[:500])
        return jsonify({'translated_text': translated})
    except Exception as e:
        return jsonify({'translated_text': text})

@app.route('/api/save_term', methods=['POST'])
@login_required
def save_term():
    data = request.json
    session_id = data.get('session_id')
    term = data.get('term')
    
    if not term:
        return jsonify({'error': 'No term'}), 400
    
    existing = Term.query.filter_by(user_id=current_user.id, term=term).first()
    if existing:
        existing.times_encountered += 1
    else:
        new_term = Term(user_id=current_user.id, session_id=session_id, term=term)
        db.session.add(new_term)
        
        session = Session.query.get(session_id)
        if session:
            session.new_terms = (session.new_terms or 0) + 1
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/save_question', methods=['POST'])
@login_required
def save_question():
    data = request.json
    session_id = data.get('session_id')
    question_text = data.get('question_text')
    
    if not question_text:
        return jsonify({'error': 'No question'}), 400
    
    question = Question(user_id=current_user.id, session_id=session_id, question_text=question_text)
    db.session.add(question)
    
    session = Session.query.get(session_id)
    if session:
        session.questions_generated = (session.questions_generated or 0) + 1
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/generate_summary/<int:session_id>', methods=['GET'])
@login_required
def generate_summary(session_id):
    session = Session.query.get(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    transcripts = Transcript.query.filter_by(session_id=session_id, is_final=True).all()
    text = ' '.join([t.text for t in transcripts])
    
    summary = f"""
    <div style="padding: 15px;">
        <h4>Session Summary</h4>
        <p><strong>Date:</strong> {session.start_time.strftime('%Y-%m-%d %H:%M')}</p>
        <p><strong>Duration:</strong> {session.duration // 60} minutes</p>
        <p><strong>Words analyzed:</strong> {session.words_analyzed or 0}</p>
        <p><strong>New terms:</strong> {session.new_terms or 0}</p>
        <hr>
        <p>{text[:500]}...</p>
    </div>
    """
    
    existing = Summary.query.filter_by(session_id=session_id).first()
    if existing:
        existing.summary_text = summary
    else:
        new_summary = Summary(user_id=current_user.id, session_id=session_id, summary_text=summary)
        db.session.add(new_summary)
    
    db.session.commit()
    return jsonify({'summary': summary})

@app.route('/api/session_stats/<int:session_id>', methods=['GET'])
@login_required
def session_stats(session_id):
    session = Session.query.get(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if session.status == 'active':
        duration = (datetime.now() - session.start_time).seconds
    else:
        duration = session.duration or 0
    
    return jsonify({
        'duration': duration,
        'words_analyzed': session.words_analyzed or 0,
        'new_terms': session.new_terms or 0,
        'questions_generated': session.questions_generated or 0,
        'points': current_user.points
    })

# ==================== TOPIC DETECTION DATABASE ====================

TOPIC_CATEGORIES = {
    'algorithms': {
        'name': 'Algorithms & Data Structures',
        'icon': '🧠',
        'color': '#4caf50',
        'keywords': ['algorithmus', 'algorithm', 'sort', 'suche', 'search', 'bubble', 'quick', 'merge', 'heap', 'hash', 'baum', 'tree', 'liste', 'list', 'array', 'komplexität', 'complexity', 'effizienz', 'efficiency'],
        'subtopics': ['Sorting Algorithms', 'Search Algorithms', 'Data Structures', 'Complexity Analysis']
    },
    'databases': {
        'name': 'Databases',
        'icon': '🗄️',
        'color': '#2196f3',
        'keywords': ['datenbank', 'database', 'sql', 'nosql', 'tabelle', 'table', 'query', 'join', 'index', 'speicher', 'storage', 'relation', 'transaktion', 'transaction'],
        'subtopics': ['SQL Queries', 'Database Design', 'Indexing', 'Transactions']
    },
    'networking': {
        'name': 'Computer Networks',
        'icon': '🌐',
        'color': '#ff9800',
        'keywords': ['netzwerk', 'network', 'server', 'client', 'ip', 'http', 'https', 'tcp', 'udp', 'router', 'switch', 'firewall', 'dns', 'protocol'],
        'subtopics': ['Network Protocols', 'IP Addressing', 'Routing', 'Network Security']
    },
    'web_development': {
        'name': 'Web Development',
        'icon': '🌍',
        'color': '#9c27b0',
        'keywords': ['web', 'html', 'css', 'javascript', 'js', 'react', 'angular', 'vue', 'api', 'rest', 'frontend', 'backend'],
        'subtopics': ['HTML/CSS', 'JavaScript', 'Frontend Frameworks', 'APIs']
    },
    'programming': {
        'name': 'Programming Basics',
        'icon': '💻',
        'color': '#00bcd4',
        'keywords': ['programmierung', 'programming', 'variable', 'funktion', 'function', 'klasse', 'class', 'objekt', 'object', 'schleife', 'loop', 'if', 'else', 'while', 'for'],
        'subtopics': ['Variables', 'Functions', 'Loops', 'Conditionals', 'OOP']
    },
    'cybersecurity': {
        'name': 'Cybersecurity',
        'icon': '🔒',
        'color': '#f44336',
        'keywords': ['sicherheit', 'security', 'verschlüsselung', 'encryption', 'authentifizierung', 'authentication', 'firewall', 'hacking', 'malware', 'virus'],
        'subtopics': ['Encryption', 'Authentication', 'Network Security', 'Security Best Practices']
    },
    'ai_ml': {
        'name': 'Artificial Intelligence',
        'icon': '🤖',
        'color': '#e91e63',
        'keywords': ['ki', 'ai', 'ml', 'machine learning', 'deep learning', 'neural', 'network', 'training', 'model', 'data science'],
        'subtopics': ['Machine Learning', 'Neural Networks', 'Data Science', 'AI Applications']
    },
    'cloud': {
        'name': 'Cloud Computing',
        'icon': '☁️',
        'color': '#03a9f4',
        'keywords': ['cloud', 'aws', 'azure', 'docker', 'kubernetes', 'container', 'virtualisierung', 'virtualization', 'devops'],
        'subtopics': ['Cloud Services', 'Containers', 'DevOps', 'Serverless']
    },
    'general': {
        'name': 'General IT',
        'icon': '📚',
        'color': '#9e9e9e',
        'keywords': [],
        'subtopics': ['IT Fundamentals', 'Computer Science Basics']
    }
}

def detect_topic_from_text(text):
    text_lower = text.lower()
    
    scores = {}
    matched_keywords = {}
    
    for category, data in TOPIC_CATEGORIES.items():
        score = 0
        keywords_found = []
        for keyword in data['keywords']:
            if keyword in text_lower:
                score += 1
                keywords_found.append(keyword)
        scores[category] = score
        matched_keywords[category] = keywords_found
    
    best_category = max(scores, key=scores.get)
    
    if scores[best_category] == 0:
        best_category = 'general'
    
    max_possible = len(TOPIC_CATEGORIES[best_category]['keywords'])
    confidence = min(100, int((scores[best_category] / max(1, max_possible)) * 100 + 30))
    
    title = generate_title(best_category, matched_keywords[best_category])
    
    return {
        'category': best_category,
        'title': title,
        'display_name': TOPIC_CATEGORIES[best_category]['name'],
        'icon': TOPIC_CATEGORIES[best_category]['icon'],
        'color': TOPIC_CATEGORIES[best_category]['color'],
        'confidence': confidence,
        'keywords': matched_keywords[best_category],
        'subtopics': TOPIC_CATEGORIES[best_category]['subtopics']
    }

def generate_title(category, keywords):
    if category == 'algorithms':
        if any(k in ' '.join(keywords) for k in ['sort', 'bubble', 'quick', 'merge']):
            return 'Introduction to Sorting Algorithms'
        return 'Understanding Algorithms and Data Structures'
    elif category == 'databases':
        return 'Database Fundamentals and SQL'
    elif category == 'networking':
        return 'Computer Networks and Protocols'
    elif category == 'web_development':
        return 'Web Development Basics'
    elif category == 'programming':
        return 'Programming Fundamentals'
    elif category == 'cybersecurity':
        return 'Cybersecurity Essentials'
    elif category == 'ai_ml':
        return 'Introduction to Artificial Intelligence'
    elif category == 'cloud':
        return 'Cloud Computing Concepts'
    else:
        return 'Technical Lecture'

# ==================== COMPETITION API ====================

def get_competitors_list():
    return [
        {"id": 1, "name": "Super AI", "icon": "🧠", "response_time": 0.3, "accuracy": 1.0, "unbeatable": True},
        {"id": 2, "name": "Senior Dev", "icon": "🟣", "response_time": 1.2, "accuracy": 0.95, "unbeatable": False},
        {"id": 3, "name": "Mid Dev", "icon": "🟡", "response_time": 2.5, "accuracy": 0.75, "unbeatable": False},
        {"id": 4, "name": "Junior Dev", "icon": "🟢", "response_time": 4.0, "accuracy": 0.60, "unbeatable": False},
        {"id": 5, "name": "Fast Coder", "icon": "⚡", "response_time": 1.0, "accuracy": 0.50, "unbeatable": False},
        {"id": 6, "name": "Slow Genius", "icon": "🐢", "response_time": 6.0, "accuracy": 0.90, "unbeatable": False},
        {"id": 7, "name": "Polyglot", "icon": "🔄", "response_time": 3.0, "accuracy": 0.80, "unbeatable": False},
        {"id": 8, "name": "Your Rival", "icon": "🤝", "response_time": 2.0, "accuracy": 0.70, "unbeatable": False}
    ]

def get_digital_rival(user_id):
    rival = DigitalRival.query.filter_by(user_id=user_id).first()
    if not rival:
        rival = DigitalRival(user_id=user_id)
        db.session.add(rival)
        db.session.commit()
    return rival

def update_digital_rival(user_id, user_performance):
    rival = get_digital_rival(user_id)
    user_speed = user_performance.get('response_time', 2.0)
    rival.response_speed = max(0.5, user_speed * 0.95)
    user_accuracy = user_performance.get('accuracy', 0.7)
    rival.accuracy = min(0.95, user_accuracy + 0.05)
    rival.last_updated = datetime.now()
    db.session.commit()
    return rival

def check_answer(user_answer, correct_answer):
    if not user_answer or not correct_answer:
        return False
    return user_answer.lower().strip() == correct_answer.lower().strip()

def extract_technical_terms(text):
    terms = []
    patterns = [
        r'[A-Z][a-z]+(?:[A-Z][a-z]+)*',
        r'\b(?:API|HTTP|HTTPS|FTP|SSH|SSL|TLS|JSON|XML|HTML|CSS|JS|SQL|DB|OS)\b',
        r'\b(?:algorithm|function|variable|class|object|method|database|server|client)\b'
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        terms.extend(matches)
    return list(set(terms))

@app.route('/api/competition/start', methods=['POST'])
@login_required
def start_competition():
    data = request.json
    session_id = data.get('session_id')
    
    competition = CompetitionSession(user_id=current_user.id, session_id=session_id)
    db.session.add(competition)
    db.session.commit()
    
    rival = get_digital_rival(current_user.id)
    
    return jsonify({
        'competition_id': competition.id,
        'message': 'Competition started!',
        'digital_rival': {'accuracy': rival.accuracy, 'response_speed': rival.response_speed}
    })

@app.route('/api/competition/submit', methods=['POST'])
@login_required
def submit_competition_answer():
    data = request.json
    session_id = data.get('session_id')
    question = data.get('question')
    user_answer = data.get('answer')
    response_time = data.get('response_time', 0)
    correct_answer = data.get('correct_answer', '')
    
    is_correct = check_answer(user_answer, correct_answer)
    competitors = get_competitors_list()
    
    competitor_results = []
    for comp in competitors:
        comp_correct = random.random() < comp['accuracy']
        comp_time = comp['response_time'] + random.uniform(-0.2, 0.2)
        competitor_results.append({
            'id': comp['id'], 'name': comp['name'], 'icon': comp['icon'],
            'correct': comp_correct, 'time': round(comp_time, 2), 'unbeatable': comp.get('unbeatable', False)
        })
    
    competitor_results.sort(key=lambda x: x['time'])
    user_result = {'correct': is_correct, 'time': response_time, 'name': 'You', 'icon': '👤'}
    all_results = competitor_results + [user_result]
    all_results.sort(key=lambda x: x['time'])
    user_rank = all_results.index(user_result) + 1
    
    points_earned = 0
    if is_correct:
        points_earned = 10
        if response_time < 1.0:
            points_earned += 20
        elif response_time < 2.0:
            points_earned += 10
        beaten_count = len([c for c in competitor_results if c['time'] > response_time])
        points_earned += beaten_count * 2
        
        current_user.points += points_earned
        db.session.commit()
    
    competition = CompetitionSession.query.filter_by(user_id=current_user.id, session_id=session_id, status='active').first()
    if competition and is_correct:
        competition.user_score += points_earned
        db.session.commit()
    
    update_digital_rival(current_user.id, {'response_time': response_time, 'accuracy': 1 if is_correct else 0})
    
    return jsonify({
        'success': True,
        'is_correct': is_correct,
        'user_rank': user_rank,
        'points_earned': points_earned,
        'competitors': competitor_results,
        'total_competitors': len(competitors) + 1
    })

@app.route('/api/competition/indirect', methods=['GET'])
@login_required
def indirect_competition():
    users_at_level = User.query.filter_by(level=current_user.level).count()
    return jsonify({'users_at_level': users_at_level, 'total_users': User.query.count()})

@app.route('/api/competition/analyze_text', methods=['POST'])
@login_required
def analyze_lecture_text():
    data = request.json
    text = data.get('text', '')
    
    technical_terms = extract_technical_terms(text)
    topic = "General IT"
    for key in ['algorithmus', 'datenbank', 'server', 'netzwerk', 'python']:
        if key in text.lower():
            topic = key.capitalize()
            break
    
    questions = []
    if technical_terms:
        questions.append({
            "question": f"What does '{technical_terms[0]}' mean in this context?",
            "options": ["Technical term", "Programming concept", "Hardware component", "Network protocol"],
            "correct": 0,
            "explanation": f"'{technical_terms[0]}' is a technical term."
        })
    
    return jsonify({
        'analysis': {'topic': topic, 'technical_terms': technical_terms[:5], 'quiz_questions': questions},
        'competitors': get_competitors_list(),
        'digital_rival': {'accuracy': 0.7}
    })

# ==================== OTHER APIs ====================
@app.route('/api/fingerprint', methods=['GET'])
@login_required
def get_fingerprint():
    fingerprint = UserFingerprint.query.filter_by(user_id=current_user.id).first()
    if not fingerprint:
        fingerprint = UserFingerprint(user_id=current_user.id)
        db.session.add(fingerprint)
        db.session.commit()
    
    weak_terms = json.loads(fingerprint.weak_terms) if fingerprint.weak_terms else []
    return jsonify({
        'past': {'level': fingerprint.past_level},
        'present': {'level': fingerprint.present_level, 'points': current_user.points},
        'future': {'predicted_level': fingerprint.future_prediction},
        'weak_terms': weak_terms[:10]
    })

@app.route('/api/evolved_self', methods=['GET'])
@login_required
def evolved_self():
    return jsonify({
        'name': f"{current_user.username} (Future You)",
        'level': 'B1',
        'message': f"Hi {current_user.username}! Keep going!"
    })

@app.route('/api/absolute_knower', methods=['POST'])
@login_required
def absolute_knower():
    return jsonify({'prediction': "You seem ready for this section!"})

@app.route('/api/living_lecture/challenge', methods=['POST'])
@login_required
def living_lecture_challenge():
    return jsonify({'text': "That's an interesting question! Let me help you understand."})

@app.route('/api/notebook/add', methods=['POST'])
@login_required
def notebook_add():
    data = request.json
    term = data.get('term')
    translation = data.get('translation', '')
    if term:
        notebook = SmartNotebook(user_id=current_user.id, session_id=data.get('session_id'), term=term, translation=translation)
        db.session.add(notebook)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/focus/update', methods=['POST'])
@login_required
def focus_update():
    data = request.json
    session_id = data.get('session_id')
    focus_score = data.get('focus_score', 100)
    focus = FocusSession.query.filter_by(session_id=session_id).first()
    if focus:
        focus.focus_score = focus_score
        db.session.commit()
    return jsonify({'success': True})

# ==================== GHOST CODER API ====================

ghost_engines = {}
prediction_engines = {}

def get_ghost_engine(user_id):
    if user_id not in ghost_engines:
        from engines.ghost_engine import GhostCoderEngine
        ghost_engines[user_id] = GhostCoderEngine(user_id)
    return ghost_engines[user_id]

def get_prediction_engine(user_id):
    if user_id not in prediction_engines:
        from engines.prediction_engine import PredictionEngine
        prediction_engines[user_id] = PredictionEngine(user_id)
    return prediction_engines[user_id]

@app.route('/api/ghost/predict', methods=['POST'])
@login_required
def ghost_predict():
    data = request.json
    current_code = data.get('code', '')
    
    engine = get_ghost_engine(current_user.id)
    prediction = engine.predict_next_line(current_code)
    
    return jsonify({
        'prediction': prediction,
        'mastery_level': engine.mastery_level
    })

@app.route('/api/ghost/analyze', methods=['POST'])
@login_required
def ghost_analyze():
    data = request.json
    user_code = data.get('code', '')
    
    engine = get_ghost_engine(current_user.id)
    analysis = engine.analyze_user_code(user_code)
    
    return jsonify(analysis)

@app.route('/api/ghost/generate', methods=['POST'])
@login_required
def ghost_generate():
    data = request.json
    user_code = data.get('code', '')
    language = data.get('language', 'python')
    
    engine = get_ghost_engine(current_user.id)
    result = engine.generate_ghost_code(user_code, language)
    
    return jsonify(result)

@app.route('/api/ghost/learn', methods=['POST'])
@login_required
def ghost_learn():
    data = request.json
    user_code = data.get('user_code', '')
    ghost_code = data.get('ghost_code', '')
    corrections = data.get('corrections', [])
    
    engine = get_ghost_engine(current_user.id)
    result = engine.learn_from_user(user_code, ghost_code, corrections)
    
    return jsonify(result)

@app.route('/api/ghost/future', methods=['GET'])
@login_required
def ghost_future():
    language = request.args.get('language', 'python')
    
    engine = get_ghost_engine(current_user.id)
    future_code = engine.generate_future_code(language)
    
    return jsonify(future_code)

@app.route('/api/ghost/room', methods=['GET'])
@login_required
def ghost_room():
    engine = get_ghost_engine(current_user.id)
    room = engine.get_ghost_room()
    
    return jsonify(room)

# ==================== PREDICTION API ====================

@app.route('/api/predict/character', methods=['POST'])
@login_required
def predict_character():
    data = request.json
    current_line = data.get('current_line', '')
    cursor_position = data.get('cursor_position', 0)
    
    engine = get_prediction_engine(current_user.id)
    prediction = engine.predict_next_character(current_line, cursor_position)
    
    return jsonify({'prediction': prediction})

@app.route('/api/predict/compare', methods=['POST'])
@login_required
def predict_compare():
    data = request.json
    user_line = data.get('user_line', '')
    expected_line = data.get('expected_line', '')
    
    engine = get_prediction_engine(current_user.id)
    comparison = engine.compare_line(user_line, expected_line)
    
    return jsonify(comparison)

@app.route('/api/predict/record', methods=['POST'])
@login_required
def predict_record():
    data = request.json
    line = data.get('line', '')
    time_taken = data.get('time_taken', 0)
    was_correct = data.get('was_correct', True)
    
    engine = get_prediction_engine(current_user.id)
    engine.record_typing(line, time_taken, was_correct)
    
    return jsonify({'success': True})

@app.route('/api/predict/preemptive', methods=['POST'])
@login_required
def predict_preemptive():
    data = request.json
    current_line = data.get('current_line', '')
    cursor_position = data.get('cursor_position', 0)
    
    engine = get_prediction_engine(current_user.id)
    correction = engine.preemptive_correction(current_line, cursor_position)
    
    return jsonify(correction)

@app.route('/api/predict/reverse_learn', methods=['POST'])
@login_required
def predict_reverse_learn():
    data = request.json
    user_code = data.get('user_code', '')
    ghost_code = data.get('ghost_code', '')
    user_understood = data.get('user_understood', False)
    
    engine = get_prediction_engine(current_user.id)
    result = engine.reverse_learning(user_code, ghost_code, user_understood)
    
    return jsonify(result)

@app.route('/api/predict/summary', methods=['GET'])
@login_required
def predict_summary():
    engine = get_prediction_engine(current_user.id)
    summary = engine.get_learning_summary()
    
    return jsonify(summary)

# ==================== TOPIC DETECTION API ====================

topic_analyzer = DynamicTopicAnalyzer()

@app.route('/api/topic/detect', methods=['POST'])
@login_required
def detect_topic():
    data = request.json
    text = data.get('text', '')
    
    if not text or len(text) < 50:
        return jsonify({
            'success': False,
            'message': 'Not enough text to analyze. Please record more.',
            'topic': None
        })
    
    try:
        result = topic_analyzer.analyze(text)
        
        return jsonify({
            'success': True,
            'topic': result.get('name', 'Technical Lecture'),
            'confidence': result.get('confidence', 0),
            'keywords': result.get('keywords', []),
            'topic_id': result.get('topic_id', -1)
        })
    except Exception as e:
        print(f"Topic detection error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'topic': None
        })

@app.route('/api/topic/update_session', methods=['POST'])
@login_required
def update_session_topic():
    data = request.json
    session_id = data.get('session_id')
    topic = data.get('topic')
    confidence = data.get('confidence', 0)
    keywords = data.get('keywords', [])
    
    if not session_id:
        return jsonify({'error': 'No session ID'}), 400
    
    session = Session.query.get(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    session.topic_category = topic.lower().replace(' ', '_')
    session.topic_title = topic
    session.topic_confidence = confidence
    session.topic_keywords = json.dumps(keywords)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'topic': topic,
        'confidence': confidence
    })

@app.route('/api/topic/status/<int:session_id>', methods=['GET'])
@login_required
def get_topic_status(session_id):
    session = Session.query.get(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({
        'topic': session.topic_title if session.topic_title else None,
        'confidence': session.topic_confidence or 0,
        'keywords': json.loads(session.topic_keywords) if session.topic_keywords else [],
        'has_topic': bool(session.topic_title)
    })
# ==================== NEW API ENDPOINTS (Info_feature1) ====================

@app.route('/api/smart_analyze', methods=['POST'])
@login_required
def smart_analyze():
    """تحليل ذكي للنص باستخدام كل الطبقات الست"""
    data = request.json
    text = data.get('text', '')
    language = data.get('language', 'en')
    
    if not text or len(text) < 20:
        return jsonify({'error': 'Text too short'}), 400
    
    # الطبقة 1: استخراج المصطلحات
    extraction = get_term_extractor().extract_terms(text, language)
    
    # الطبقة 2: التحويل إلى متجهات
    terms = [t['text'] for t in extraction['terms']]
    embeddings = get_encoder().encode(terms) if terms else []
    
    # الطبقة 5: تحديد الموضوع
    topic = get_topic_detector().get_topic_for_text(text)
    
    # الطبقة 4: البحث في خريطة المعرفة
    relations = []
    for term in terms[:10]:
        path = get_graph_builder().get_learning_path(term)
        if path:
            relations.append({'concept': term, 'learning_path': path})
    
    # الطبقة 6: خريطة التعلم
    roadmap = get_roadmap_gen().generate_roadmap(extraction['terms'])
    
    return jsonify({
        'terms': extraction['terms'],
        'topic': topic,
        'knowledge_relations': relations,
        'roadmap': roadmap,
        'embedding_count': len(embeddings)
    })


@app.route('/api/semantic_search', methods=['POST'])
@login_required
def semantic_search():
    """بحث دلالي عن المفاهيم التقنية"""
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'No query'}), 400
    
    query_emb = get_encoder().encode([query])[0]
    results = get_vector_store().search(query_emb, top_k=10)
    
    return jsonify({
        'query': query,
        'results': [{'id': r.id, 'score': r.score, 'payload': r.payload} for r in results]
    })


@app.route('/api/learning_roadmap', methods=['GET'])
@login_required
def learning_roadmap():
    target = request.args.get('target', '')
    
    if not target:
        return jsonify({'error': 'No target concept'}), 400
    
    path = get_graph_builder().get_learning_path(target)
    
    return jsonify({
        'target': target,
        'learning_path': path,
        'steps': len(path)
    })


# ==================== SELF-ADAPTIVE UNDERSTANDING LAYER ====================

@app.route('/api/smart_analyze_v2', methods=['POST'])
@login_required
def smart_analyze_v2():
    """Self-Adaptive Understanding Layer - fully automatic analysis."""
    data = request.json
    text = data.get('text', '')

    if not text or len(text) < 20:
        return jsonify({'error': 'Text too short for analysis (minimum 20 characters)'}), 400

    try:
        analysis = get_smart_layer().analyze(text)
    except Exception as e:
        logger.exception("smart_analyze_v2 failed")
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    analysis['session_id'] = data.get('session_id')
    analysis['timestamp'] = datetime.now().isoformat()

    return jsonify(analysis)


# ==================== STAGE 2: CODE UNDERSTANDING (Layer 7) ====================

@app.route('/api/code/analyze', methods=['POST'])
@login_required
def code_analyze():
    """Stage 2 Layer 7 — AST-based code understanding via Tree-sitter."""
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    language = data.get('language', 'python')

    if not code or len(code.strip()) < 5:
        return jsonify({'error': 'Code too short for analysis'}), 400

    try:
        result = get_ast_analyzer().analyze(code, language)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("code_analyze failed")
        return jsonify({'error': f'Code analysis failed: {str(e)}'}), 500

    result['session_id'] = data.get('session_id')
    result['timestamp'] = datetime.now().isoformat()

    return jsonify(result)


# ==================== STAGE 2: PERFORMANCE ANALYSIS (Layer 8) ====================

@app.route('/api/code/performance', methods=['POST'])
@login_required
def code_performance():
    """Stage 2 Layer 8 — static performance analysis built on the Layer 7 AST."""
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    language = data.get('language', 'python')

    if not code or len(code.strip()) < 5:
        return jsonify({'error': 'Code too short for analysis'}), 400

    try:
        result = get_performance_analyzer().analyze(code, language)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("code_performance failed")
        return jsonify({'error': f'Performance analysis failed: {str(e)}'}), 500

    result['session_id'] = data.get('session_id')
    result['timestamp'] = datetime.now().isoformat()

    return jsonify(result)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)