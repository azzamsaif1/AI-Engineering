// ==================== WAIT FOR PAGE LOAD ====================
document.addEventListener('DOMContentLoaded', function () {
    initSystem();
});
// اختبار ظهور بطاقة الموضوع بعد 2 ثانية
setTimeout(function () {
    console.log('🔍 Testing topic card display...');
    const testTopic = {
        title: 'Algorithms and Data Structures',
        confidence: 92,
        keywords: ['algorithm', 'sort', 'search', 'bubble', 'quick'],
        icon: '🧠',
        color: '#4caf50',
        display_name: 'Computer Science'
    };

    const topicCard = document.getElementById('topicCard');
    if (topicCard) {
        topicCard.style.display = 'flex';
        document.getElementById('topicTitle').innerHTML = testTopic.title;
        document.getElementById('confidenceFill').style.width = testTopic.confidence + '%';
        document.getElementById('confidenceValue').innerHTML = testTopic.confidence + '%';
        document.getElementById('topicIcon').innerHTML = testTopic.icon;
        document.getElementById('topicStatus').innerHTML = testTopic.confidence >= 70 ? '✓ Confirmed' : 'Analyzing...';

        const keywordsContainer = document.getElementById('topicKeywords');
        if (keywordsContainer) {
            keywordsContainer.innerHTML = testTopic.keywords.map(kw =>
                `<span style="background:rgba(0,212,255,0.15); padding:4px 12px; border-radius:20px; font-size:11px; margin:3px; display:inline-block;">${kw}</span>`
            ).join('');
        }

        console.log('✅ Topic card displayed!');
        showNotification('Topic card test: ' + testTopic.title);
    } else {
        console.error('❌ topicCard element not found!');
    }
}, 2000);
// ==================== SOCKET.IO CONNECTION ====================
let socket = null;
let currentCompetitionId = null;
let currentRoom = null;

// ==================== PAGE ELEMENTS ====================
const recordBtn = document.getElementById('recordBtn');
const pauseBtn = document.getElementById('pauseBtn');
const stopBtn = document.getElementById('stopBtn');
const videoBtn = document.getElementById('videoBtn');
const downloadBtn = document.getElementById('downloadBtn');
const transcriptContainer = document.getElementById('transcript');
const translationContainer = document.getElementById('translation');
const termList = document.getElementById('termList');
const questionList = document.getElementById('questionList');
const learningRecs = document.getElementById('learningRecs');
const translationPopup = document.getElementById('translationPopup');
const overlay = document.getElementById('overlay');
const closePopup = document.getElementById('closePopup');
const originalText = document.getElementById('originalText');
const translatedText = document.getElementById('translatedText');
const questionInput = document.getElementById('questionInput');
const generateBtn = document.getElementById('generateBtn');
const languageOptions = document.querySelectorAll('.lang-option');
const audioVisualizer = document.getElementById('audioVisualizer');
const summaryContainer = document.getElementById('summaryContainer');
const summaryContent = document.getElementById('summaryContent');
const loginButton = document.getElementById('loginButton');
const registerButton = document.getElementById('registerButton');
const logoutBtn = document.getElementById('logoutBtn');
const userInfo = document.getElementById('userInfo');
const usernameDisplay = document.getElementById('usernameDisplay');
const userPointsSpan = document.getElementById('userPoints');
const loginModal = document.getElementById('loginModal');
const registerModal = document.getElementById('registerModal');
const submitLogin = document.getElementById('submitLogin');
const submitRegister = document.getElementById('submitRegister');
const cancelLogin = document.getElementById('cancelLogin');
const cancelRegister = document.getElementById('cancelRegister');
const loginUsername = document.getElementById('loginUsername');
const loginPassword = document.getElementById('loginPassword');
const registerUsername = document.getElementById('registerUsername');
const registerPassword = document.getElementById('registerPassword');
const loginError = document.getElementById('loginError');
const registerError = document.getElementById('registerError');
const notification = document.getElementById('notification');
const notificationMessage = document.getElementById('notificationMessage');
const notificationIcon = document.getElementById('notificationIcon');
const volumeControl = document.getElementById('volumeControl');
const speedControl = document.getElementById('speedControl');
const manualText = document.getElementById('manualText');
const manualTranslateBtn = document.getElementById('manualTranslateBtn');
const startCompetitionBtn = document.getElementById('startCompetitionBtn');
const askLectureBtn = document.getElementById('askLectureBtn');
const lectureQuestion = document.getElementById('lectureQuestion');
const speakNotebookBtn = document.getElementById('speakNotebookBtn');

// ==================== SYSTEM STATE ====================
let state = {
    isRecording: false,
    isPaused: false,
    currentLang: 'de',
    targetLang: 'ar',
    recordedText: '',
    wordsAnalyzed: 0,
    termsFound: new Set(),
    questionsGenerated: 0,
    currentSessionId: null,
    sessionStart: null,
    timerInterval: null,
    recognition: null,
    videoStream: null,
    isVideoRecording: false,
    digitalScore: 0,
    userScore: 0,
    competitionActive: false
};

let interimLine = null;
let focusInterval = null;

// ==================== HELPER FUNCTIONS ====================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showNotification(message, isSuccess = true) {
    if (!notification || !notificationMessage || !notificationIcon) return;
    notificationMessage.textContent = message;
    notificationIcon.className = isSuccess ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
    notificationIcon.style.color = isSuccess ? '#4caf50' : '#ff4b2b';
    notification.style.display = 'block';
    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

function showError(element, message) {
    if (!element) return;
    element.textContent = message;
    element.style.display = 'block';
    setTimeout(() => {
        element.style.display = 'none';
    }, 3000);
}

// ==================== SOCKET.IO ====================
function initSocket() {
    try {
        socket = io({
            transports: ['polling'],
            upgrade: false,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000
        });

        socket.on('connect', function () {
            console.log('✅ Socket connected (polling mode)');
        });

        socket.on('topic_detected', function (data) {
            console.log('📡 Topic detected:', data);
            displayTopicCard(data);
        });

        socket.on('disconnect', function () {
            console.log('❌ Socket disconnected');
        });

    } catch (error) {
        console.error('Failed to initialize socket:', error);
    }
}

function displayTopicCard(topic) {
    const topicCard = document.getElementById('topicCard');
    const topicTitle = document.getElementById('topicTitle');
    const topicCategory = document.getElementById('topicCategory');
    const confidenceFill = document.getElementById('confidenceFill');
    const confidenceValue = document.getElementById('confidenceValue');
    const topicKeywords = document.getElementById('topicKeywords');
    const topicSubtopics = document.getElementById('topicSubtopics');
    const topicIcon = document.getElementById('topicIcon');
    const topicStatus = document.getElementById('topicStatus');

    if (!topicCard) return;

    topicCard.style.display = 'flex';
    topicCard.classList.add('topic-detected');

    if (topicIcon) topicIcon.innerHTML = topic.icon || '📚';
    if (topicTitle) topicTitle.innerHTML = topic.title || 'Technical Lecture';
    if (topicCategory) topicCategory.innerHTML = topic.display_name || '';
    if (confidenceFill) confidenceFill.style.width = `${topic.confidence || 0}%`;
    if (confidenceValue) confidenceValue.innerHTML = `${topic.confidence || 0}%`;

    if (topicStatus) {
        topicStatus.innerHTML = (topic.confidence || 0) >= 70 ? '✓ Confirmed' : 'Analyzing...';
        topicStatus.style.color = (topic.confidence || 0) >= 70 ? '#4caf50' : '#ff9800';
    }

    if (topicKeywords && topic.keywords && topic.keywords.length > 0) {
        topicKeywords.innerHTML = topic.keywords.slice(0, 5).map(kw =>
            `<span class="topic-keyword">${escapeHtml(kw)}</span>`
        ).join('');
    }

    showNotification(`🎯 Topic: ${topic.title}`);
}

// ==================== SPEECH RECOGNITION ====================
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showNotification('Speech recognition not supported. Please use Chrome.', false);
        return;
    }

    state.recognition = new SpeechRecognition();
    state.recognition.continuous = true;
    state.recognition.interimResults = true;  // ✅ مهم جداً للسرعة
    state.recognition.lang = 'de-DE';
    state.recognition.maxAlternatives = 1;

    state.recognition.onstart = function () {
        console.log('🎤 Speech recognition started');
    };

    state.recognition.onresult = function (event) {
        let interimText = '';
        let finalText = '';

        // ✅ معالجة سريعة للنتائج فوراً
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalText += transcript + ' ';
            } else {
                interimText += transcript;
            }
        }

        // ✅ عرض النص المؤقت فوراً (أثناء الكلام)
        if (interimText) {
            showImmediateText(interimText);
        }

        // ✅ النص النهائي
        if (finalText) {
            addFinalTranscriptLine(finalText, true);
            translateText(finalText, state.targetLang).then(translation => {
                if (translation) addTranslationLine(translation);
            });
            extractTerms(finalText);
            updateDashboard();

            if (state.currentSessionId) {
                fetch('/api/save_transcript', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: state.currentSessionId,
                        text: finalText,
                        is_final: true
                    })
                });
                state.recordedText += finalText;
            }
        }
    };

    state.recognition.onerror = function (event) {
        console.error('Speech error:', event.error);
        if (event.error === 'no-speech') {
            // لا تفعل شيئاً، فقط واصل الاستماع
        } else if (event.error === 'audio-capture') {
            showNotification('No microphone found. Please check your microphone.', false);
        } else if (event.error === 'not-allowed') {
            showNotification('Microphone access denied.', false);
        }
    };

    state.recognition.onend = function () {
        console.log('🎤 Speech recognition ended');
        // إذا كان التسجيل لا يزال نشطاً، أعد التشغيل
        if (state.isRecording && !state.isPaused) {
            state.recognition.start();
        }
    };
}

// ✅ دالة جديدة لعرض النص فوراً أثناء الكلام
let pendingText = '';
let pendingTimeout = null;

function showImmediateText(text) {
    if (!transcriptContainer) return;

    // تجميع النص المؤقت
    pendingText = text;

    // تأخير بسيط لتجميع الكلمات
    if (pendingTimeout) clearTimeout(pendingTimeout);

    pendingTimeout = setTimeout(() => {
        // إزالة السطر المؤقت السابق
        if (interimLine && interimLine.parentNode) {
            interimLine.remove();
        }

        // إنشاء سطر مؤقت جديد
        interimLine = document.createElement('div');
        interimLine.className = 'transcript-line interim';
        interimLine.innerHTML = `
            <div class="transcript-text" style="color: #ff9800; font-style: italic; border-left: 3px solid #ff9800;">
                <i class="fas fa-microphone"></i> ${escapeHtml(pendingText)}
            </div>
            <div class="transcript-actions">
                <i class="fas fa-language" style="opacity:0.5; font-size:12px;"></i>
            </div>
        `;
        transcriptContainer.appendChild(interimLine);
        transcriptContainer.scrollTop = transcriptContainer.scrollHeight;

        pendingText = '';
    }, 100);
}

function addFinalTranscriptLine(text, isFinal) {
    if (!transcriptContainer) return;

    // إزالة السطر المؤقت
    if (interimLine && interimLine.parentNode) {
        interimLine.remove();
        interimLine = null;
    }
    if (pendingTimeout) clearTimeout(pendingTimeout);

    // إزالة placeholder
    if (transcriptContainer.innerHTML.includes('Click the microphone')) {
        transcriptContainer.innerHTML = '';
    }

    const line = document.createElement('div');
    line.className = `transcript-line final`;
    line.style.cursor = 'pointer';
    line.innerHTML = `
        <div class="transcript-text">${escapeHtml(text)}</div>
        <div class="transcript-actions">
            <i class="fas fa-language" onclick="event.stopPropagation(); translateLine('${escapeHtml(text)}')" title="Translate"></i>
            <i class="fas fa-question-circle" onclick="event.stopPropagation(); generateQuestionFromLine('${escapeHtml(text)}')" title="Generate Question"></i>
            <i class="fas fa-book" onclick="event.stopPropagation(); addToNotebook('${escapeHtml(text)}')" title="Add to Notebook"></i>
        </div>
    `;
    line.addEventListener('click', () => translateLine(text));

    transcriptContainer.appendChild(line);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function showInterimText(text) {
    if (!transcriptContainer) return;
    if (interimLine && interimLine.parentNode) interimLine.remove();
    interimLine = document.createElement('div');
    interimLine.className = 'transcript-line interim';
    interimLine.innerHTML = `<div class="transcript-text" style="color:#ff9800;">🎤 ${escapeHtml(text)}</div>`;
    transcriptContainer.appendChild(interimLine);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function addTranscriptLine(text, isFinal) {
    if (!transcriptContainer) return;
    if (interimLine && interimLine.parentNode) interimLine.remove();
    if (transcriptContainer.innerHTML.includes('Click the microphone')) transcriptContainer.innerHTML = '';

    const line = document.createElement('div');
    line.className = `transcript-line ${isFinal ? 'final' : 'interim'}`;
    line.style.cursor = 'pointer';
    line.innerHTML = `<div class="transcript-text">${escapeHtml(text)}</div>`;
    line.addEventListener('click', () => translateLine(text));
    transcriptContainer.appendChild(line);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function addTranslationLine(text) {
    if (!translationContainer) return;
    if (translationContainer.innerHTML.includes('Translations will appear')) translationContainer.innerHTML = '';
    const line = document.createElement('div');
    line.className = 'transcript-line final';
    line.innerHTML = `<div class="transcript-text">🌍 ${escapeHtml(text)}</div>`;
    translationContainer.appendChild(line);
    translationContainer.scrollTop = translationContainer.scrollHeight;
}

async function translateText(text, targetLang) {
    if (!text.trim()) return '';
    try {
        const response = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, target_lang: targetLang })
        });
        const data = await response.json();
        return data.translated_text || '';
    } catch (error) {
        return '';
    }
}

function translateLine(text) {
    translateText(text, state.targetLang).then(translation => {
        if (originalText && translatedText) {
            originalText.innerHTML = text;
            translatedText.innerHTML = translation || 'Translation failed';
            translationPopup.style.display = 'block';
            overlay.style.display = 'block';
        }
    });
}

// ==================== TERMS EXTRACTION ====================
function extractTerms(text) {
    const patterns = [
        /[A-Z][a-z]+(?:[A-Z][a-z]+)*/g,
        /\b(?:API|HTTP|HTTPS|FTP|SSH|SSL|TLS|JSON|XML|HTML|CSS|JS|SQL|DB|OS)\b/gi,
        /\b(?:algorithm|function|variable|class|object|method|database|server|client|interface)\b/gi
    ];

    let foundTerms = [];
    patterns.forEach(pattern => {
        const matches = text.match(pattern);
        if (matches) foundTerms.push(...matches);
    });

    foundTerms = [...new Set(foundTerms)];
    foundTerms = foundTerms.filter(term => term.length > 2 && !state.termsFound.has(term.toLowerCase()));

    for (let term of foundTerms.slice(0, 10)) {
        state.termsFound.add(term.toLowerCase());
        addTermToSidebar(term);
        if (state.currentSessionId) {
            fetch('/api/save_term', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: state.currentSessionId, term: term })
            });
        }
    }
    updateDashboard();
}

function addTermToSidebar(term) {
    if (!termList) return;
    if (termList.innerHTML === '') termList.innerHTML = '';
    const termCard = document.createElement('div');
    termCard.className = 'term-card';
    termCard.style.cursor = 'pointer';
    termCard.innerHTML = `${escapeHtml(term)} <i class="fas fa-volume-up" onclick="speakText('${escapeHtml(term)}')"></i>`;
    termCard.onclick = () => translateLine(term);
    termList.appendChild(termCard);
}

// ==================== RECORDING FUNCTIONS ====================
function toggleRecording() {
    if (state.isRecording) stopRecording();
    else startRecording();
}

function startRecording() {
    if (!currentUser) {
        showNotification('Please login first', false);
        loginModal.style.display = 'flex';
        return;
    }

    fetch('/api/start_session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(res => res.json())
        .then(data => {
            if (data.session_id) {
                state.currentSessionId = data.session_id;
                state.isRecording = true;
                state.isPaused = false;
                if (recordBtn) recordBtn.classList.add('recording');
                if (transcriptContainer) transcriptContainer.innerHTML = '';
                if (translationContainer) translationContainer.innerHTML = '';
                if (termList) termList.innerHTML = '';

                if (state.recognition) {
                    try {
                        state.recognition.stop();
                    } catch (e) { }
                }
                initSpeechRecognition();
                state.recognition.start();

                showNotification('Recording started! Speak clearly.');
            }
        })
        .catch(error => showNotification('Failed to start recording', false));
}
function generateQuestionFromLine(text) {
    const question = `What does "${text.substring(0, 50)}..." mean?`;
    addQuestionToSidebar(question);
    state.questionsGenerated++;
    updateDashboard();
    showNotification('Question generated from selected text');
}
function stopRecording() {
    if (!state.isRecording) return;
    state.isRecording = false;
    if (recordBtn) recordBtn.classList.remove('recording');
    if (state.recognition) state.recognition.stop();
    if (state.currentSessionId) {
        fetch(`/api/stop_session/${state.currentSessionId}`, { method: 'POST' });
        generateSummary();
    }
    showNotification('Recording stopped');
}

function togglePause() {
    if (!state.isRecording) return;
    state.isPaused = !state.isPaused;
    if (state.isPaused) {
        state.recognition.stop();
        pauseBtn.querySelector('i').className = 'fas fa-play';
    } else {
        state.recognition.start();
        pauseBtn.querySelector('i').className = 'fas fa-pause';
    }
}

function toggleVideoRecording() {
    if (!state.isVideoRecording) {
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(stream => {
                state.videoStream = stream;
                const videoPreview = document.getElementById('videoPreview');
                if (videoPreview) videoPreview.srcObject = stream;
                document.getElementById('videoPreviewContainer').style.display = 'block';
                state.isVideoRecording = true;
                if (videoBtn) videoBtn.style.background = '#ff4b2b';
            })
            .catch(() => showNotification('Camera access denied', false));
    } else {
        if (state.videoStream) state.videoStream.getTracks().forEach(track => track.stop());
        document.getElementById('videoPreviewContainer').style.display = 'none';
        state.isVideoRecording = false;
        if (videoBtn) videoBtn.style.background = '';
    }
}

function downloadTranscript() {
    const lines = document.querySelectorAll('#transcript .transcript-line.final .transcript-text');
    let text = '';
    lines.forEach(line => { text += line.textContent + '\n'; });
    if (!text) { showNotification('No transcript to download', false); return; }
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcript_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showNotification('Transcript downloaded');
}

// ==================== QUESTIONS ====================
function generateQuestion() {
    const q = questionInput?.value.trim();
    if (!q) { showNotification('Enter a question first', false); return; }
    addQuestionToSidebar(q);
    if (questionInput) questionInput.value = '';
    state.questionsGenerated++;
    updateDashboard();
    if (state.currentSessionId) {
        fetch('/api/save_question', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId, question_text: q })
        });
    }
}

function addQuestionToSidebar(q) {
    if (!questionList) return;
    const card = document.createElement('div');
    card.className = 'question-card';
    card.style.cursor = 'pointer';
    card.innerHTML = `<div class="question-text">${escapeHtml(q)}</div><div class="question-actions"><button onclick="answerQuestion('${escapeHtml(q)}')">Answer</button><button onclick="translateLine('${escapeHtml(q)}')">Translate</button></div>`;
    card.onclick = (e) => { if (e.target.tagName !== 'BUTTON') translateLine(q); };
    questionList.prepend(card);
}

function answerQuestion(q) {
    showNotification('Generating answer...');
    setTimeout(() => {
        originalText.innerHTML = `<strong>Question:</strong><br>${escapeHtml(q)}`;
        translatedText.innerHTML = `<strong>Answer:</strong><br>Based on the lecture, this is a technical concept.`;
        translationPopup.style.display = 'block';
        overlay.style.display = 'block';
    }, 500);
}

// ==================== SUMMARY ====================
async function generateSummary() {
    if (!state.currentSessionId) return;
    try {
        const res = await fetch(`/api/generate_summary/${state.currentSessionId}`);
        const data = await res.json();
        if (summaryContent) summaryContent.innerHTML = data.summary;
        summaryContainer.style.display = 'block';
    } catch (e) { console.error(e); }
}

function updateDashboard() {
    const w = document.getElementById('wordsAnalyzed');
    const t = document.getElementById('newTerms');
    const q = document.getElementById('questionsGenerated');
    if (w) w.textContent = state.wordsAnalyzed;
    if (t) t.textContent = state.termsFound.size;
    if (q) q.textContent = state.questionsGenerated;
}

// ==================== NOTEBOOK ====================
async function addToNotebook(term) {
    const trans = await translateText(term, 'ar');
    const entry = document.createElement('div');
    entry.className = 'notebook-entry';
    entry.setAttribute('data-term', term);
    entry.style.cursor = 'pointer';
    entry.innerHTML = `<div><strong>${escapeHtml(term)}</strong><br><small>${escapeHtml(trans)}</small></div><button onclick="speakText('${escapeHtml(term)}')"><i class="fas fa-volume-up"></i></button>`;
    entry.onclick = (e) => { if (e.target.tagName !== 'BUTTON') translateLine(term); };
    document.getElementById('notebookEntries')?.prepend(entry);
    if (state.currentSessionId) {
        await fetch('/api/notebook/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId, term: term, translation: trans })
        });
    }
}

function speakAllNotebook() {
    const entries = document.querySelectorAll('.notebook-entry');
    let text = '';
    entries.forEach(e => { const t = e.getAttribute('data-term'); if (t) text += t + '. '; });
    if (text) speakText(text);
}

// ==================== COMPETITION ====================
// ==================== COMPETITION ====================

async function startCompetition() {
    console.log('Start competition clicked');

    if (!state.currentSessionId) {
        showNotification('Please start a recording session first!', false);
        return;
    }

    if (!state.recordedText || state.recordedText.length < 50) {
        showNotification('Please record more lecture content first (at least 50 characters).', false);
        return;
    }

    showNotification('🎯 Analyzing lecture and starting competition...');

    try {
        // تحليل النص المسجل
        const analyzeResponse = await fetch('/api/competition/analyze_text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: state.recordedText })
        });
        const analyzeData = await analyzeResponse.json();

        console.log('Analysis result:', analyzeData);

        // بدء جلسة المنافسة
        const startResponse = await fetch('/api/competition/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId })
        });
        const startData = await startResponse.json();

        console.log('Competition started:', startData);

        state.competitionActive = true;

        // عرض المنافسين في الواجهة
        if (analyzeData.competitors) {
            displayCompetitors(analyzeData.competitors);
        }

        // عرض السؤال الأول إذا وجد
        if (analyzeData.analysis && analyzeData.analysis.quiz_questions && analyzeData.analysis.quiz_questions.length > 0) {
            displayQuizQuestion(analyzeData.analysis.quiz_questions[0]);
        } else {
            // إنشاء سؤال افتراضي
            displayDefaultQuizQuestion();
        }

        showNotification('✅ Competition started! Answer the question to earn points!');

    } catch (error) {
        console.error('Competition error:', error);
        showNotification('Failed to start competition: ' + error.message, false);

        // عرض سؤال افتراضي كبديل
        displayDefaultQuizQuestion();
        state.competitionActive = true;
    }
}

function displayCompetitors(competitors) {
    const container = document.getElementById('directCompetitors');
    if (!container) return;

    container.innerHTML = '<div style="margin-bottom: 10px; color: #00d4ff;">🏆 COMPETITORS 🏆</div>';

    for (let comp of competitors) {
        const div = document.createElement('div');
        div.className = 'competitor-card';
        div.innerHTML = `
            <div class="competitor-name">
                <span style="font-size: 18px;">${comp.icon || '👤'}</span>
                <strong>${comp.name}</strong>
                ${comp.unbeatable ? '👑' : ''}
            </div>
            <div class="competitor-score">Ready</div>
        `;
        container.appendChild(div);
    }
}

function displayQuizQuestion(question) {
    const quizContainer = document.getElementById('competitionQuiz');
    if (!quizContainer) return;

    const optionsHtml = question.options.map((opt, idx) => `
        <div class="quiz-option" onclick="submitQuizAnswer(${idx}, '${escapeHtml(opt)}')" 
             style="padding: 12px; margin: 8px 0; background: rgba(255,255,255,0.1); border-radius: 10px; cursor: pointer; transition: 0.2s;">
            ${String.fromCharCode(65 + idx)}. ${escapeHtml(opt)}
        </div>
    `).join('');

    quizContainer.innerHTML = `
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; border-radius: 15px; margin: 15px 0;">
            <div style="color: #ff9800; font-size: 12px;">⚔️ CHALLENGE ⚔️</div>
            <div style="font-size: 18px; margin: 15px 0;">${escapeHtml(question.question)}</div>
            <div id="quizOptions">
                ${optionsHtml}
            </div>
            <div id="quizTimer" style="text-align: center; margin-top: 15px; color: #ff9800;">⏱️ 10 seconds remaining</div>
        </div>
    `;

    // بدء المؤقت
    let timeLeft = 10;
    const timerEl = document.getElementById('quizTimer');
    window.currentQuizTimer = setInterval(() => {
        timeLeft--;
        if (timerEl) timerEl.textContent = `⏱️ ${timeLeft} seconds remaining`;
        if (timeLeft <= 0) {
            clearInterval(window.currentQuizTimer);
            timerEl.textContent = '⏰ Time\'s up!';
            quizContainer.innerHTML += '<div style="color:#ff9800; margin-top:10px;">No answer submitted. Next question...</div>';
            setTimeout(() => loadNextCompetitionQuestion(), 2000);
        }
    }, 1000);

    window.currentQuizQuestion = question;
}

function displayDefaultQuizQuestion() {
    const quizContainer = document.getElementById('competitionQuiz');
    if (!quizContainer) return;

    const defaultQuestion = {
        question: "What is the main topic of this lecture?",
        options: ["Algorithms", "Databases", "Networks", "Web Development"],
        correct: 0,
        explanation: "Based on the lecture content analysis."
    };
    displayQuizQuestion(defaultQuestion);
}

function loadNextCompetitionQuestion() {
    // تحميل سؤال تالي أو إنهاء المنافسة
    const quizContainer = document.getElementById('competitionQuiz');
    if (quizContainer) {
        quizContainer.innerHTML += `
            <div style="background: #4caf50; padding: 20px; border-radius: 15px; margin-top: 15px; text-align: center;">
                🏆 Round Complete! 🏆
                <div style="margin-top: 10px;">You earned ${state.userScore} points!</div>
                <button onclick="startCompetition()" style="margin-top: 10px; padding: 8px 20px; background: #00d4ff; border: none; border-radius: 8px; cursor: pointer;">Start New Competition</button>
            </div>
        `;
    }
    state.competitionActive = false;
}

function submitQuizAnswer(selectedIndex, selectedText) {
    if (!window.currentQuizQuestion) return;
    if (window.currentQuizTimer) clearInterval(window.currentQuizTimer);

    const isCorrect = (selectedIndex === window.currentQuizQuestion.correct);
    const pointsEarned = isCorrect ? 20 : 0;

    if (isCorrect) {
        state.userScore += pointsEarned;
        showNotification(`✅ Correct! +${pointsEarned} points!`);
        updateDashboard();
    } else {
        showNotification(`❌ Incorrect! The correct answer is: ${window.currentQuizQuestion.options[window.currentQuizQuestion.correct]}`, false);
    }

    const quizContainer = document.getElementById('competitionQuiz');
    if (quizContainer) {
        quizContainer.innerHTML += `
            <div style="margin-top:15px; padding:15px; border-radius:10px; background:${isCorrect ? '#4caf5022' : '#f4433622'};">
                ${isCorrect ? '✅ Correct!' : '❌ Incorrect!'}
                ${window.currentQuizQuestion.explanation ? `<div style="font-size:12px; margin-top:5px;">${escapeHtml(window.currentQuizQuestion.explanation)}</div>` : ''}
            </div>
        `;
    }

    // تحديث نتيجة المنافس الرقمي
    const digitalScoreEl = document.getElementById('digitalScore');
    if (digitalScoreEl) {
        digitalScoreEl.textContent = `${state.userScore} pts`;
    }

    setTimeout(() => {
        loadNextCompetitionQuestion();
    }, 3000);
}

// ==================== AUTHENTICATION ====================
function updateUserUI() {
    if (currentUser && userInfo) {
        userInfo.style.display = 'flex';
        if (loginButton) loginButton.style.display = 'none';
        if (registerButton) registerButton.style.display = 'none';
        if (usernameDisplay) usernameDisplay.textContent = currentUser.username;
    } else if (userInfo) {
        userInfo.style.display = 'none';
        if (loginButton) loginButton.style.display = 'flex';
        if (registerButton) registerButton.style.display = 'flex';
    }
}

async function loginUser() {
    const u = loginUsername.value.trim();
    const p = loginPassword.value.trim();
    if (!u || !p) { showError(loginError, 'Fill all fields'); return; }
    const res = await fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u, password: p }) });
    const data = await res.json();
    if (data.success) location.reload();
    else showError(loginError, data.error);
}

async function registerUser() {
    const u = registerUsername.value.trim();
    const p = registerPassword.value.trim();
    if (!u || !p) { showError(registerError, 'Fill all fields'); return; }
    const res = await fetch('/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u, password: p }) });
    const data = await res.json();
    if (data.success) location.reload();
    else showError(registerError, data.error);
}

async function logoutUser() {
    await fetch('/logout');
    location.reload();
}

function manualTranslate() {
    const text = manualText?.value.trim();
    if (text) { translateLine(text); if (manualText) manualText.value = ''; }
    else showNotification('Enter text to translate', false);
}

function closeTranslationPopup() {
    translationPopup.style.display = 'none';
    overlay.style.display = 'none';
}

function speakText(text) {
    if (!window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'de-DE';
    u.rate = 0.9;
    window.speechSynthesis.speak(u);
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
    showNotification('Copied!');
}

async function askLivingLecture() {
    const q = lectureQuestion?.value.trim();
    if (!q) return;
    const msgDiv = document.getElementById('lectureMessage');
    if (msgDiv) msgDiv.innerHTML = `<i class="fas fa-comment-dots"></i> Interesting question about "${q.substring(0, 50)}..."`;
    if (lectureQuestion) lectureQuestion.value = '';
}

// ==================== FOCUS TRACKING ====================
function startFocusTracking() {
    if (focusInterval) clearInterval(focusInterval);
    focusInterval = setInterval(() => {
        if (!state.isRecording) return;
        const score = Math.floor(Math.random() * 30) + 70;
        const focusEl = document.getElementById('focusScore');
        if (focusEl) focusEl.textContent = `${score}%`;
    }, 5000);
}

function initAudioVisualizer() {
    if (!audioVisualizer) return;
    audioVisualizer.innerHTML = '';
    for (let i = 0; i < 50; i++) {
        const bar = document.createElement('div');
        bar.className = 'audio-bar';
        bar.style.height = '3px';
        audioVisualizer.appendChild(bar);
    }
    setInterval(() => {
        if (!state.isRecording) return;
        const bars = audioVisualizer.querySelectorAll('.audio-bar');
        bars.forEach(bar => { bar.style.height = `${Math.random() * 40 + 5}px`; });
    }, 100);
}

async function loadCompetitionStats() {
    try {
        const res = await fetch('/api/competition/indirect');
        const data = await res.json();
        const statsDiv = document.getElementById('indirectStats');
        if (statsDiv) statsDiv.innerHTML = `<i class="fas fa-globe"></i> ${data.users_at_level || 0} users at your level`;
    } catch (e) { }
}

// ==================== INITIALIZATION ====================
function initSystem() {
    updateUserUI();
    initSpeechRecognition();
    initAudioVisualizer();
    startFocusTracking();
    updateDashboard();
    loadCompetitionStats();
    initSocket();

    if (recordBtn) recordBtn.addEventListener('click', toggleRecording);
    if (pauseBtn) pauseBtn.addEventListener('click', togglePause);
    if (stopBtn) stopBtn.addEventListener('click', stopRecording);
    if (videoBtn) videoBtn.addEventListener('click', toggleVideoRecording);
    if (downloadBtn) downloadBtn.addEventListener('click', downloadTranscript);
    if (generateBtn) generateBtn.addEventListener('click', generateQuestion);
    if (manualTranslateBtn) manualTranslateBtn.addEventListener('click', manualTranslate);
    if (startCompetitionBtn) startCompetitionBtn.addEventListener('click', startCompetition);
    if (askLectureBtn) askLectureBtn.addEventListener('click', askLivingLecture);
    if (speakNotebookBtn) speakNotebookBtn.addEventListener('click', speakAllNotebook);

    document.getElementById('closePopup')?.addEventListener('click', closeTranslationPopup);
    document.getElementById('overlay')?.addEventListener('click', closeTranslationPopup);

    languageOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            languageOptions.forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            state.currentLang = opt.dataset.lang;
            if (state.recognition) state.recognition.lang = `${opt.dataset.lang}-${opt.dataset.lang.toUpperCase()}`;
            showNotification(`Language: ${opt.dataset.lang.toUpperCase()}`);
        });
    });

    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.targetLang = btn.dataset.target;
            showNotification(`Target: ${btn.dataset.target.toUpperCase()}`);
        });
    });

    if (loginButton) loginButton.addEventListener('click', () => loginModal.style.display = 'flex');
    if (registerButton) registerButton.addEventListener('click', () => registerModal.style.display = 'flex');
    if (logoutBtn) logoutBtn.addEventListener('click', logoutUser);
    if (cancelLogin) cancelLogin.addEventListener('click', () => loginModal.style.display = 'none');
    if (cancelRegister) cancelRegister.addEventListener('click', () => registerModal.style.display = 'none');
    if (submitLogin) submitLogin.addEventListener('click', loginUser);
    if (submitRegister) submitRegister.addEventListener('click', registerUser);

    if (manualText) manualText.addEventListener('keypress', (e) => { if (e.key === 'Enter') manualTranslate(); });

    if (currentUser) showNotification(`Welcome ${currentUser.username}!`);
    console.log('TechLingua Mentor Ready');
}

// ==================== EXPOSE FUNCTIONS GLOBALLY ====================
window.translateLine = translateLine;
window.answerQuestion = answerQuestion;
window.speakText = speakText;
window.copyToClipboard = copyToClipboard;
window.addToNotebook = addToNotebook;
window.generateQuestionFromLine = generateQuestionFromLine;
window.submitQuizAnswer = submitQuizAnswer;

function generateQuestionFromLine(text) {
    const question = `What does "${text.substring(0, 50)}..." mean?`;
    addQuestionToSidebar(question);
    state.questionsGenerated++; s
    updateDashboard();
    showNotification('Question generated from selected text');
}
function submitQuizAnswer(selectedIndex, selectedText) {
    if (!window.currentQuizQuestion) return;
    if (window.currentQuizTimer) clearInterval(window.currentQuizTimer);

    const isCorrect = (selectedIndex === window.currentQuizQuestion.correct);
    const responseTime = 10 - (parseInt(document.getElementById('quizTimer')?.textContent.match(/\d+/) || [10])[0]);

    if (socket && state.currentSessionId) {
        socket.emit('submit_answer', {
            session_id: state.currentSessionId,
            question: window.currentQuizQuestion.question,
            answer: selectedText,
            response_time: responseTime,
            correct_answer: window.currentQuizQuestion.options[window.currentQuizQuestion.correct],
            type: 'quiz'
        });
    }

    const quizContainer = document.getElementById('competitionQuiz');
    if (quizContainer) {
        quizContainer.innerHTML += `<div style="margin-top:15px;padding:10px;border-radius:10px;background:${isCorrect ? '#4caf5022' : '#f4433622'};">${isCorrect ? '✅ Correct!' : '❌ Incorrect!'}</div>`;
    }

    setTimeout(() => {
        if (typeof generateChallengeFromTranscript === 'function') {
            generateChallengeFromTranscript();
        }
    }, 3000);
}

function generateQuestionFromLine(text) {
    const question = `What does "${text.substring(0, 50)}..." mean?`;
    addQuestionToSidebar(question);
    state.questionsGenerated++;
    updateDashboard();
    showNotification('Question generated from selected text');
}

window.submitQuizAnswer = submitQuizAnswer;
window.generateQuestionFromLine = generateQuestionFromLine;
