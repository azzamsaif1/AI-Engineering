if (window.navigator.mediaDevices) {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            stream.getTracks().forEach(track => track.stop());
            console.log('✅ Microphone ready');
        })
        .catch(err => console.error('Microphone error:', err));
}


// ==================== WAIT FOR PAGE LOAD ====================
document.addEventListener('DOMContentLoaded', function () {
    initSystem();
});

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
        // Force polling only, no websocket
        socket = io({
            transports: ['polling'],  // فقط Polling، بدون WebSocket
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
function joinCompetitionRoom(sessionId) {
    if (!socket) initSocket();
    currentRoom = `comp_${sessionId}`;
    socket.emit('join_competition', { session_id: sessionId, room: currentRoom });
}

function updateCompetitionUI(data) {
    const competitorsDiv = document.getElementById('directCompetitors');
    if (!competitorsDiv) return;

    const rankBadge = document.getElementById('competitionBadge');
    if (rankBadge) {
        rankBadge.textContent = `Rank ${data.user_rank}/${data.total_competitors}`;
        if (data.user_rank === 1) rankBadge.style.background = '#ffd700';
        else if (data.user_rank <= 3) rankBadge.style.background = '#c0c0c0';
        else rankBadge.style.background = '#cd7f32';
    }

    competitorsDiv.innerHTML = '';
    for (let comp of data.competitors) {
        const compDiv = document.createElement('div');
        compDiv.className = 'competitor-card';
        compDiv.innerHTML = `
            <div class="competitor-name">
                <span style="font-size:18px;">${comp.icon}</span>
                <strong>${comp.name}</strong>
                ${comp.unbeatable ? '👑' : ''}
            </div>
            <div>${comp.correct ? '✅' : '❌'} ${comp.time.toFixed(1)}s</div>
        `;
        competitorsDiv.appendChild(compDiv);
    }

    if (data.points_earned > 0) {
        showNotification(`+${data.points_earned} points!`);
        state.userScore += data.points_earned;
        const digitalScoreEl = document.getElementById('digitalScore');
        if (digitalScoreEl) digitalScoreEl.textContent = `${state.userScore} pts`;
    }
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
    state.recognition.interimResults = true;
    state.recognition.lang = 'de-DE';
    state.recognition.maxAlternatives = 1;

    // ✅ إعدادات إضافية للسرعة
    if (state.recognition.audioTrack) {
        state.recognition.audioTrack.enabled = true;
    }

    state.recognition.onstart = function () {
        console.log('🎤 Listening...');
    };

    state.recognition.onresult = function (event) {
        // ✅ معالجة فورية جداً
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            const transcript = result[0].transcript;

            if (result.isFinal) {
                final += transcript + ' ';
            } else {
                interim += transcript;
            }
        }

        // ✅ عرض النص المؤقت فوراً (بدون أي تأخير)
        if (interim) {
            displayInterimImmediately(interim);
        }

        if (final) {
            displayFinalImmediately(final);
        }
    };

    state.recognition.onerror = function (event) {
        console.error('Speech error:', event.error);
        if (event.error === 'no-speech') {
            // واصل الاستماع - لا شيء
        } else if (event.error === 'audio-capture') {
            showNotification('No microphone found.', false);
        } else if (event.error === 'not-allowed') {
            showNotification('Microphone access denied.', false);
        }
    };

    state.recognition.onend = function () {
        console.log('🎤 Stopped listening');
        if (state.isRecording && !state.isPaused) {
            // إعادة التشغيل فوراً
            setTimeout(() => {
                try {
                    state.recognition.start();
                } catch (e) { }
            }, 50);
        }
    };
}

// ✅ عرض فوري أثناء الكلام
let interimDisplay = null;

function displayInterimImmediately(text) {
    if (!transcriptContainer) return;

    // إزالة المؤقت القديم
    if (interimDisplay && interimDisplay.parentNode) {
        interimDisplay.querySelector('.interim-text').innerHTML = `<i class="fas fa-microphone"></i> ${escapeHtml(text)}`;
    } else {
        if (interimDisplay) interimDisplay.remove();

        interimDisplay = document.createElement('div');
        interimDisplay.className = 'transcript-line interim';
        interimDisplay.style.borderLeftColor = '#ff9800';
        interimDisplay.style.background = 'rgba(255, 152, 0, 0.1)';
        interimDisplay.innerHTML = `
            <div class="interim-text" style="color: #ff9800;">
                <i class="fas fa-microphone"></i> ${escapeHtml(text)}
            </div>
        `;
        transcriptContainer.appendChild(interimDisplay);
    }
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function displayFinalImmediately(text) {
    // إزالة السطر المؤقت
    if (interimDisplay) {
        interimDisplay.remove();
        interimDisplay = null;
    }

    // إزالة placeholder
    if (transcriptContainer.innerHTML.includes('Click the microphone')) {
        transcriptContainer.innerHTML = '';
    }

    // إضافة السطر النهائي
    const line = document.createElement('div');
    line.className = 'transcript-line final';
    line.innerHTML = `
        <div class="transcript-text">${escapeHtml(text)}</div>
        <div class="transcript-actions" style="display: inline-block; margin-left: 10px;">
            <i class="fas fa-language" onclick="event.stopPropagation(); translateLine('${escapeHtml(text)}')" style="cursor:pointer; margin:0 5px;"></i>
            <i class="fas fa-book" onclick="event.stopPropagation(); addToNotebook('${escapeHtml(text)}')" style="cursor:pointer; margin:0 5px;"></i>
        </div>
    `;
    line.addEventListener('click', () => translateLine(text));
    transcriptContainer.appendChild(line);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;

    // ✅ الترجمة الفورية
    translateText(text, state.targetLang).then(translation => {
        if (translation) {
            addTranslationLineFast(translation);
        }
    });

    // ✅ استخراج المصطلحات
    extractTerms(text);
    updateDashboard();

    // ✅ حفظ للخادم
    if (state.currentSessionId) {
        fetch('/api/save_transcript', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.currentSessionId,
                text: text,
                is_final: true
            })
        });
        state.recordedText += text;
    }
}

// ✅ ترجمة سريعة جداً
function addTranslationLineFast(text) {
    if (!translationContainer) return;

    if (translationContainer.innerHTML.includes('Translations will appear')) {
        translationContainer.innerHTML = '';
    }

    const line = document.createElement('div');
    line.className = 'transcript-line final';
    line.style.borderLeftColor = '#4caf50';
    line.innerHTML = `<div class="transcript-text">🌍 ${escapeHtml(text)}</div>`;
    translationContainer.appendChild(line);
    translationContainer.scrollTop = translationContainer.scrollHeight;
}
// ✅ متغيرات للتحديث السريع
let lastInterimText = '';
let interimUpdateTimer = null;

function updateInterimDisplay(text) {
    if (!transcriptContainer) return;

    lastInterimText = text;

    // تحديث فوري بدون تأخير
    if (interimLine && interimLine.parentNode) {
        interimLine.querySelector('.transcript-text').innerHTML = `<i class="fas fa-microphone"></i> ${escapeHtml(text)}`;
    } else {
        // إزالة السطر المؤقت القديم إذا وجد
        if (interimLine && interimLine.parentNode) {
            interimLine.remove();
        }

        // إنشاء سطر مؤقت جديد
        interimLine = document.createElement('div');
        interimLine.className = 'transcript-line interim';
        interimLine.innerHTML = `
            <div class="transcript-text" style="color: #ff9800; font-style: italic; border-left: 3px solid #ff9800;">
                <i class="fas fa-microphone"></i> ${escapeHtml(text)}
            </div>
            <div class="transcript-actions" style="opacity:0.5;">
                <i class="fas fa-language" style="font-size:11px;"></i>
            </div>
        `;
        transcriptContainer.appendChild(interimLine);
    }
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function processFinalText(text) {
    // إزالة السطر المؤقت
    if (interimLine && interimLine.parentNode) {
        interimLine.remove();
        interimLine = null;
    }

    // إزالة placeholder
    if (transcriptContainer.innerHTML.includes('Click the microphone')) {
        transcriptContainer.innerHTML = '';
    }

    // إضافة السطر النهائي
    const line = document.createElement('div');
    line.className = 'transcript-line final';
    line.innerHTML = `
        <div class="transcript-text">${escapeHtml(text)}</div>
        <div class="transcript-actions">
            <i class="fas fa-language" onclick="event.stopPropagation(); translateLine('${escapeHtml(text)}')" title="Translate"></i>
            <i class="fas fa-question-circle" onclick="event.stopPropagation(); generateQuestionFromLine('${escapeHtml(text)}')" title="Question"></i>
            <i class="fas fa-book" onclick="event.stopPropagation(); addToNotebook('${escapeHtml(text)}')" title="Notebook"></i>
        </div>
    `;
    line.addEventListener('click', () => translateLine(text));
    transcriptContainer.appendChild(line);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;

    // ترجمة فورية
    translateText(text, state.targetLang).then(translation => {
        if (translation) addTranslationLine(translation);
    });

    // استخراج المصطلحات
    extractTerms(text);
    updateDashboard();

    // حفظ في الخادم
    if (state.currentSessionId) {
        fetch('/api/save_transcript', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.currentSessionId,
                text: text,
                is_final: true
            })
        });
        state.recordedText += text;
    }
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
// تبسيط دالة addTranslationLine لتكون سريعة
function addTranslationLine(text) {
    if (!translationContainer) return;

    if (translationContainer.innerHTML.includes('Translations will appear')) {
        translationContainer.innerHTML = '';
    }

    const line = document.createElement('div');
    line.className = 'transcript-line final';
    line.style.opacity = '0';
    line.innerHTML = `<div class="transcript-text">🌍 ${escapeHtml(text)}</div>`;
    translationContainer.appendChild(line);

    // تأثير تلاشي سريع
    setTimeout(() => { line.style.opacity = '1'; }, 10);
    translationContainer.scrollTop = translationContainer.scrollHeight;
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
        /\b(?:API|HTTP|HTTPS|FTP|SSH|SSL|TLS|JSON|XML|HTML|CSS|JS|SQL|DB|OS|RAM|CPU|GPU|AI|ML)\b/gi,
        /\b(?:algorithm|function|variable|class|object|method|property|database|server|client|interface|protocol)\b/gi
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
// ==================== TOPIC DETECTION ====================

let topicDetected = false;

function initTopicDetection() {
    if (!socket) {
        initSocket();
    }

    socket.on('topic_detected', function (data) {
        console.log('Topic detected:', data);
        displayTopicCard(data);
        topicDetected = true;

        const competitionBadge = document.getElementById('competitionBadge');
        if (competitionBadge) {
            competitionBadge.textContent = `Topic: ${data.display_name}`;
            competitionBadge.style.background = data.color;
        }
    });
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

    if (topicCard) {
        topicCard.style.display = 'flex';
        topicCard.classList.add('topic-detected');

        if (topicIcon) topicIcon.innerHTML = topic.icon;
        if (topicTitle) topicTitle.innerHTML = topic.title;
        if (topicCategory) topicCategory.innerHTML = topic.display_name;
        if (confidenceFill) confidenceFill.style.width = `${topic.confidence}%`;
        if (confidenceValue) confidenceValue.innerHTML = `${topic.confidence}%`;
        if (topicStatus) {
            topicStatus.innerHTML = topic.confidence > 70 ? '✓ Confirmed' : 'Analyzing...';
            topicStatus.style.color = topic.confidence > 70 ? '#4caf50' : '#ff9800';
        }

        if (topicKeywords && topic.keywords && topic.keywords.length > 0) {
            topicKeywords.innerHTML = topic.keywords.map(kw =>
                `<span class="topic-keyword">${escapeHtml(kw)}</span>`
            ).join('');
        } else if (topicKeywords) {
            topicKeywords.innerHTML = '<span class="topic-keyword">No keywords detected yet</span>';
        }

        if (topicSubtopics && topic.subtopics) {
            topicSubtopics.innerHTML = topic.subtopics.map(sub =>
                `<span class="topic-subtopic">${escapeHtml(sub)}</span>`
            ).join('');
        }

        generateChallengesFromTopic(topic);

        showNotification(`🎯 Topic detected: ${topic.title} (${topic.confidence}% confidence)`);
    }
}

async function generateChallengesFromTopic(topic) {
    try {
        const response = await fetch('/api/competition/generate_from_topic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                category: topic.category,
                topic: topic.title,
                keywords: topic.keywords
            })
        });
        const data = await response.json();

        if (data.code_challenge) {
            displayCodeChallenge(data.code_challenge);
        }

        if (data.quiz_questions) {
            displayQuizQuestions(data.quiz_questions);
        }

    } catch (error) {
        console.error('Failed to generate challenges:', error);
    }
}

async function startCompetition() {
    if (!state.currentSessionId) {
        showNotification('Start a recording session first!', false);
        return;
    }

    if (!topicDetected) {
        showNotification('Waiting for topic detection. Please record more content.', false);
        return;
    }

    try {
        const response = await fetch(`/api/session_topic/${state.currentSessionId}`);
        const topic = await response.json();

        showNotification(`🎯 Starting competition on: ${topic.title}`);

        const compStart = await fetch('/api/competition/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId })
        });

        state.competitionActive = true;

        await generateChallengesFromTopic(topic);

    } catch (error) {
        console.error('Failed to start competition:', error);
        showNotification('Failed to start competition', false);
    }
}

async function getSessionTopic() {
    if (!state.currentSessionId) return null;

    try {
        const response = await fetch(`/api/session_topic/${state.currentSessionId}`);
        return await response.json();
    } catch (error) {
        console.error('Failed to get topic:', error);
        return null;
    }
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
                state.recordedText = '';

                if (recordBtn) recordBtn.classList.add('recording');

                // تنظيف سريع
                if (transcriptContainer) transcriptContainer.innerHTML = '';
                if (translationContainer) translationContainer.innerHTML = '';
                if (termList) termList.innerHTML = '';

                // إعادة تعيين المتغيرات
                if (interimDisplay) interimDisplay = null;

                // ✅ بدء التعرف مباشرة
                if (state.recognition) {
                    try { state.recognition.stop(); } catch (e) { }
                }
                initSpeechRecognition();
                state.recognition.start();

                showNotification('🎤 Recording started! Speak anything...');
            }
        })
        .catch(error => showNotification('Failed to start recording', false));
}
function stopRecording() {
    if (!state.isRecording) return;
    state.isRecording = false;
    if (recordBtn) recordBtn.classList.remove('recording');
    if (state.recognition) state.recognition.stop();

    // ✅ STOP TOPIC ANALYSIS
    if (topicAnalysisInterval) {
        clearInterval(topicAnalysisInterval);
        topicAnalysisInterval = null;
    }

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

// ==================== COMPETITION ====================// ==================== COMPETITION SYSTEM ====================

let currentCompetitionActive = false;
let currentQuestion = null;
let currentCodeChallenge = null;
let competitionTimer = null;
let timeLeft = 30;

async function startCompetition() {
    if (!state.currentSessionId) {
        showNotification('Start a recording session first!', false);
        return;
    }

    if (!state.recordedText || state.recordedText.length < 20) {
        showNotification('Need more lecture content. Please record more.', false);
        return;
    }

    showNotification('🎯 Analyzing lecture and starting competition...');

    try {
        // Analyze the lecture text to generate challenges
        const response = await fetch('/api/competition/analyze_text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: state.recordedText })
        });
        const data = await response.json();

        // Start competition session
        const compStart = await fetch('/api/competition/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId })
        });
        const compData = await compStart.json();

        currentCompetitionActive = true;
        state.competitionActive = true;

        // Load competitors UI
        loadCompetitorsUI(data.competitors);

        // Display topic and start challenges
        displayTopicInfo(data.analysis.topic, data.analysis.technical_terms);

        // Start first challenge
        if (data.analysis.quiz_questions && data.analysis.quiz_questions.length > 0) {
            startQuizChallenge(data.analysis.quiz_questions[0]);
        } else {
            startCodeChallenge();
        }

    } catch (error) {
        console.error('Competition error:', error);
        showNotification('Failed to start competition', false);
    }
}

function loadCompetitorsUI(competitors) {
    const container = document.getElementById('directCompetitors');
    if (!container) return;

    container.innerHTML = '';
    for (let comp of competitors) {
        const div = document.createElement('div');
        div.className = 'competitor-card';
        div.id = `comp_${comp.id}`;
        div.innerHTML = `
            <div class="competitor-name">
                <span style="font-size:20px;">${comp.icon}</span>
                    <strong>${comp.name}</strong>
                    ${comp.unbeatable ? '👑' : ''}
                </div>
                <div class="competitor-score" id="score_${comp.id}">0 pts</div>
                <div class="competitor-status" id="status_${comp.id}" style="font-size:10px;">Ready</div>
            `;
        container.appendChild(div);
    }
}

function displayTopicInfo(topic, terms) {
    const quizContainer = document.getElementById('competitionQuiz');
    if (!quizContainer) return;

    quizContainer.innerHTML = `
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 15px; border-radius: 15px; margin: 15px 0;">
            <div style="color: #00d4ff; font-size: 14px;">📚 TOPIC DETECTED</div>
            <div style="font-size: 20px; font-weight: bold;">${topic}</div>
            <div style="font-size: 12px; margin-top: 8px;">
                ${terms.map(t => `<span style="background:#00d4ff22; padding:3px 8px; border-radius:15px; margin:3px; display:inline-block;">${t}</span>`).join('')}
            </div>
        </div>
    `;
}

function startQuizChallenge(question) {
    currentQuestion = question;
    timeLeft = 15;

    const quizContainer = document.getElementById('competitionQuiz');
    if (!quizContainer) return;

    quizContainer.innerHTML += `
        <div style="background: rgba(0,0,0,0.5); padding: 20px; border-radius: 15px; margin-top: 15px;">
            <div style="color: #ff9800; font-size: 12px;">⚔️ CHALLENGE</div>
            <div style="font-size: 18px; margin: 15px 0;">${escapeHtml(question.question)}</div>
            <div id="quizOptions">
                ${question.options.map((opt, idx) => `
                    <div class="quiz-option" onclick="submitQuizAnswer(${idx}, '${escapeHtml(opt)}')" 
                         style="padding: 12px; margin: 8px 0; background: rgba(255,255,255,0.1); border-radius: 10px; cursor: pointer; transition: 0.2s;">
                        ${String.fromCharCode(65 + idx)}. ${escapeHtml(opt)}
                    </div>
                `).join('')}
            </div>
            <div id="quizTimer" style="text-align: center; margin-top: 15px; color: #ff9800;">⏱️ ${timeLeft} seconds</div>
        </div>
    `;

    startTimer();
}

function startCodeChallenge() {
    currentCodeChallenge = {
        language: 'python',
        description: 'Write a function that solves the problem related to the lecture topic.',
        starterCode: 'def solve():\n    # Your code here\n    pass'
    };

    const quizContainer = document.getElementById('competitionQuiz');
    if (!quizContainer) return;

    quizContainer.innerHTML += `
        <div style="background: rgba(0,0,0,0.5); padding: 20px; border-radius: 15px; margin-top: 15px;">
            <div style="color: #4caf50; font-size: 12px;">💻 CODE CHALLENGE</div>
            <div style="font-size: 16px; margin: 15px 0;">${currentCodeChallenge.description}</div>
            <div style="background: #1e1e1e; padding: 15px; border-radius: 10px; font-family: monospace;">
                <pre id="codeEditor" contenteditable="true" style="background:#1e1e1e; color:#d4d4d4; border:none; outline:none; font-family: monospace;">${currentCodeChallenge.starterCode}</pre>
            </div>
            <button onclick="submitCodeChallenge()" style="margin-top: 15px; background: #4caf50; border: none; padding: 10px 20px; border-radius: 8px; color: white; cursor: pointer;">⚡ Submit Code</button>
            <div id="codeTimer" style="text-align: center; margin-top: 15px; color: #ff9800;">⏱️ 60 seconds</div>
        </div>
    `;

    timeLeft = 60;
    startTimer();
}

function startTimer() {
    if (competitionTimer) clearInterval(competitionTimer);

    competitionTimer = setInterval(() => {
        timeLeft--;
        const timerEl = document.getElementById('quizTimer') || document.getElementById('codeTimer');
        if (timerEl) timerEl.textContent = `⏱️ ${timeLeft} seconds`;

        if (timeLeft <= 0) {
            clearInterval(competitionTimer);
            timerEl.textContent = '⏰ Time\'s up!';
            if (currentQuestion) {
                showAnswerAndNext();
            } else if (currentCodeChallenge) {
                showCodeResult(false);
            }
        }
    }, 1000);
}

async function submitQuizAnswer(selectedIndex, selectedText) {
    if (!currentQuestion) return;
    if (competitionTimer) clearInterval(competitionTimer);

    const isCorrect = (selectedIndex === currentQuestion.correct);
    const responseTime = 15 - timeLeft;

    // Update competitors in real-time
    updateCompetitorsResponse(isCorrect, responseTime);

    // Submit to server
    try {
        const response = await fetch('/api/competition/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.currentSessionId,
                question: currentQuestion.question,
                answer: selectedText,
                response_time: responseTime,
                correct_answer: currentQuestion.options[currentQuestion.correct]
            })
        });
        const data = await response.json();

        showNotification(`${isCorrect ? '✅ Correct!' : '❌ Incorrect!'} +${data.points_earned || 0} points`, isCorrect);

        // Update user points display
        const userScoreEl = document.getElementById('userScore');
        if (userScoreEl) {
            let currentScore = parseInt(userScoreEl.textContent) || 0;
            userScoreEl.textContent = currentScore + (data.points_earned || 0);
        }

    } catch (error) {
        console.error('Submit error:', error);
    }

    // Show result and next challenge
    const quizContainer = document.getElementById('competitionQuiz');
    if (quizContainer) {
        quizContainer.innerHTML += `
            <div style="margin-top:15px; padding:15px; border-radius:10px; background:${isCorrect ? '#4caf5022' : '#f4433622'};">
                ${isCorrect ? '🎉 Correct!' : '❌ Incorrect!'}
                ${currentQuestion.explanation ? `<div style="font-size:12px; margin-top:5px;">${escapeHtml(currentQuestion.explanation)}</div>` : ''}
            </div>
        `;
    }

    // Load next challenge
    setTimeout(() => {
        loadNextChallenge();
    }, 3000);
}

async function submitCodeChallenge() {
    const codeEditor = document.getElementById('codeEditor');
    const code = codeEditor ? codeEditor.innerText : '';

    if (competitionTimer) clearInterval(competitionTimer);

    // Simple code validation
    const isValid = code.length > 20 && code.includes('def') || code.includes('function') || code.includes('return');
    const executionTime = 60 - timeLeft;

    updateCompetitorsCodeResponse(isValid, executionTime);

    try {
        const response = await fetch('/api/competition/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.currentSessionId,
                question: currentCodeChallenge.description,
                answer: code,
                response_time: executionTime,
                correct_answer: 'Valid code',
                type: 'code'
            })
        });
        const data = await response.json();

        showNotification(`${isValid ? '✅ Code accepted!' : '❌ Code has errors!'} +${data.points_earned || 0} points`, isValid);

    } catch (error) {
        console.error('Code submit error:', error);
    }

    showCodeResult(isValid);

    setTimeout(() => {
        loadNextChallenge();
    }, 3000);
}

function updateCompetitorsResponse(userCorrect, userTime) {
    const competitors = document.querySelectorAll('.competitor-card');
    const competitorStatuses = ['✅', '❌', '✅', '❌', '✅', '❌', '✅', '🤝'];
    const competitorTimes = [0.3, 1.2, 2.5, 4.0, 1.0, 6.0, 3.0, 2.0];

    competitors.forEach((comp, idx) => {
        const statusEl = comp.querySelector('.competitor-status');
        const scoreEl = comp.querySelector('.competitor-score');

        if (statusEl) {
            const isCorrect = Math.random() > 0.3;
            statusEl.innerHTML = isCorrect ? '✅ answered' : '❌ missed';
        }

        if (idx === 7 && userCorrect) {
            if (scoreEl) {
                let currentScore = parseInt(scoreEl.textContent) || 0;
                scoreEl.textContent = currentScore + 10;
            }
        }
    });
}

function updateCompetitorsCodeResponse(userValid, userTime) {
    const competitors = document.querySelectorAll('.competitor-card');

    competitors.forEach((comp, idx) => {
        const statusEl = comp.querySelector('.competitor-status');
        if (statusEl) {
            const isValid = Math.random() > 0.4;
            statusEl.innerHTML = isValid ? '✅ code valid' : '❌ code error';
        }
    });
}

function showAnswerAndNext() {
    const quizContainer = document.getElementById('competitionQuiz');
    if (quizContainer && currentQuestion) {
        quizContainer.innerHTML += `
            <div style="margin-top:15px; padding:15px; background:#2196f322; border-radius:10px;">
                📖 Correct answer: ${currentQuestion.options[currentQuestion.correct]}
                <div style="font-size:12px; margin-top:5px;">${currentQuestion.explanation || ''}</div>
            </div>
        `;
    }
    setTimeout(() => loadNextChallenge(), 3000);
}

function showCodeResult(isValid) {
    const quizContainer = document.getElementById('competitionQuiz');
    if (quizContainer) {
        quizContainer.innerHTML += `
            <div style="margin-top:15px; padding:15px; border-radius:10px; background:${isValid ? '#4caf5022' : '#f4433622'};">
                ${isValid ? '🎉 Code executed successfully!' : '❌ Code needs debugging'}
            </div>
        `;
    }
}

async function loadNextChallenge() {
    // Clear current challenge
    currentQuestion = null;
    currentCodeChallenge = null;

    // Get next challenge from server
    try {
        const response = await fetch('/api/competition/analyze_text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: state.recordedText.slice(-300) })
        });
        const data = await response.json();

        const quizContainer = document.getElementById('competitionQuiz');
        if (quizContainer) {
            // Keep only topic info, remove old challenge
            const topicDiv = quizContainer.querySelector('[style*="background: linear-gradient"]');
            quizContainer.innerHTML = '';
            if (topicDiv) quizContainer.appendChild(topicDiv);
        }

        if (data.analysis.quiz_questions && data.analysis.quiz_questions.length > 0) {
            startQuizChallenge(data.analysis.quiz_questions[0]);
        } else if (Math.random() > 0.5) {
            startCodeChallenge();
        } else {
            // End competition
            endCompetition();
        }

    } catch (error) {
        console.error('Next challenge error:', error);
        endCompetition();
    }
}

async function endCompetition() {
    currentCompetitionActive = false;
    state.competitionActive = false;
    if (competitionTimer) clearInterval(competitionTimer);

    const quizContainer = document.getElementById('competitionQuiz');
    if (quizContainer) {
        quizContainer.innerHTML += `
            <div style="background: #4caf50; padding: 20px; border-radius: 15px; margin-top: 15px; text-align: center;">
                🏆 COMPETITION COMPLETE! 🏆
                <div style="margin-top: 10px;">You earned ${state.userScore} points!</div>
            </div>
        `;
    }

    showNotification('Competition ended! Great job!');
}

async function loadCompetitors() {
    try {
        const response = await fetch('/api/competition/analyze_text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: state.recordedText || 'Sample lecture text' })
        });
        const data = await response.json();
        const competitorsDiv = document.getElementById('directCompetitors');
        if (competitorsDiv && data.competitors) {
            competitorsDiv.innerHTML = '';
            for (let comp of data.competitors) {
                const compDiv = document.createElement('div');
                compDiv.className = 'competitor-card';
                compDiv.innerHTML = `<div class="competitor-name">${comp.icon} <strong>${comp.name}</strong> ${comp.unbeatable ? '👑' : ''}</div><div class="competitor-score">Ready</div>`;
                competitorsDiv.appendChild(compDiv);
            }
        }
    } catch (error) {
        console.error('Failed to load competitors:', error);
    }
}

async function generateChallengeFromTranscript() {
    if (!state.recordedText) return;
    try {
        const response = await fetch('/api/competition/analyze_text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: state.recordedText.slice(-500) })
        });
        const data = await response.json();
        if (data.analysis && data.analysis.quiz_questions && data.analysis.quiz_questions.length > 0) {
            displayQuizQuestion(data.analysis.quiz_questions[0]);
        }
    } catch (error) {
        console.error('Failed to generate challenge:', error);
    }
}

function displayQuizQuestion(question) {
    const quizContainer = document.getElementById('competitionQuiz');
    if (!quizContainer) return;

    quizContainer.innerHTML = `
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 15px; margin: 15px 0;">
            <div style="font-size: 14px; margin-bottom: 10px;">🎯 CHALLENGE</div>
            <div style="font-size: 16px; margin-bottom: 15px;">${escapeHtml(question.question)}</div>
            <div id="quizOptions">
                ${question.options.map((opt, idx) => `
                    <div class="quiz-option" onclick="submitQuizAnswer(${idx}, '${escapeHtml(opt)}')" 
                         style="padding: 10px; margin: 8px 0; background: rgba(255,255,255,0.1); border-radius: 10px; cursor: pointer;">
                        ${String.fromCharCode(65 + idx)}. ${escapeHtml(opt)}
                    </div>
                `).join('')}
            </div>
            <div id="quizTimer" style="text-align: center; margin-top: 10px; font-size: 12px;">⏱️ 10 seconds remaining</div>
        </div>
    `;

    let timeLeft = 10;
    const timerEl = document.getElementById('quizTimer');
    const timer = setInterval(() => {
        timeLeft--;
        if (timerEl) timerEl.textContent = `⏱️ ${timeLeft} seconds remaining`;
        if (timeLeft <= 0) {
            clearInterval(timer);
            timerEl.textContent = '⏰ Time\'s up!';
        }
    }, 1000);

    window.currentQuizTimer = timer;
    window.currentQuizQuestion = question;
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

    setTimeout(() => { generateChallengeFromTranscript(); }, 3000);
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
// ==================== AI TOPIC DETECTION ====================

let topicAnalysisInterval = null;
let lastAnalyzedText = '';
let isAnalyzingTopic = false;

function startTopicAnalysis() {
    if (topicAnalysisInterval) clearInterval(topicAnalysisInterval);

    topicAnalysisInterval = setInterval(async () => {
        // Only analyze if recording and have enough text
        if (!state.isRecording || !state.currentSessionId) return;
        if (isAnalyzingTopic) return;

        // Get recent text (last 200 chars or recorded text)
        const textToAnalyze = state.recordedText.slice(-800);
        if (textToAnalyze.length < 100) return;
        if (textToAnalyze === lastAnalyzedText) return;

        lastAnalyzedText = textToAnalyze;
        isAnalyzingTopic = true;

        try {
            const response = await fetch('/api/topic/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: textToAnalyze })
            });
            const data = await response.json();

            if (data.success && data.topic && data.confidence > 40) {
                // Update session with detected topic
                await fetch('/api/topic/update_session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: state.currentSessionId,
                        topic: data.topic,
                        confidence: data.confidence,
                        keywords: data.keywords
                    })
                });

                // Display topic card. Icon/colour come from the backend
                // UnifiedIntentEngine (semantic) — no keyword classification here.
                displayTopicCard({
                    title: data.display_name || data.topic,
                    confidence: data.confidence,
                    keywords: data.keywords,
                    icon: data.icon || '📚',
                    color: data.color || getTopicColor(data.confidence)
                });
            }
        } catch (error) {
            console.error('Topic analysis error:', error);
        } finally {
            isAnalyzingTopic = false;
        }
    }, 8000); // Analyze every 8 seconds
}

// NOTE: topic icons are now provided by the backend UnifiedIntentEngine
// (semantic classification). The old keyword-based getTopicIcon() was removed
// to guarantee zero keyword-based classification on the frontend.

function getTopicColor(confidence) {
    if (confidence >= 80) return '#4caf50';
    if (confidence >= 60) return '#ff9800';
    return '#00d4ff';
}

function displayTopicCard(topicData) {
    const topicCard = document.getElementById('topicCard');
    const topicTitle = document.getElementById('topicTitle');
    const confidenceFill = document.getElementById('confidenceFill');
    const confidenceValue = document.getElementById('confidenceValue');
    const topicKeywords = document.getElementById('topicKeywords');
    const topicIcon = document.getElementById('topicIcon');
    const topicStatus = document.getElementById('topicStatus');

    if (!topicCard) return;

    topicCard.style.display = 'flex';
    topicCard.classList.add('topic-detected');

    if (topicIcon) topicIcon.innerHTML = topicData.icon || '📚';
    if (topicTitle) topicTitle.innerHTML = topicData.title || 'Technical Lecture';
    if (confidenceFill) confidenceFill.style.width = `${topicData.confidence || 0}%`;
    if (confidenceValue) confidenceValue.innerHTML = `${topicData.confidence || 0}%`;

    if (topicStatus) {
        const confidence = topicData.confidence || 0;
        topicStatus.innerHTML = confidence >= 70 ? '✓ Confirmed' : 'Analyzing...';
        topicStatus.style.color = confidence >= 70 ? '#4caf50' : '#ff9800';
    }

    if (topicKeywords && topicData.keywords && topicData.keywords.length > 0) {
        topicKeywords.innerHTML = topicData.keywords.slice(0, 5).map(kw =>
            `<span class="topic-keyword">${escapeHtml(kw)}</span>`
        ).join('');
    }

    // Update competition badge
    const competitionBadge = document.getElementById('competitionBadge');
    if (competitionBadge && topicData.title) {
        competitionBadge.textContent = `Topic: ${topicData.title.substring(0, 20)}`;
    }

    showNotification(`🎯 Topic detected: ${topicData.title} (${topicData.confidence}% confidence)`);
}

// Add topic analysis to startRecording
function startRecordingWithTopic() {
    // Call original startRecording first (modify your existing startRecording)
    // Add this line after state.currentSessionId is set:
    // startTopicAnalysis();
}

// Modify your existing startRecording function - add startTopicAnalysis()
// Find your startRecording function and add:
// startTopicAnalysis();
// after state.currentSessionId is assigned

// ==================== EXPOSE FUNCTIONS GLOBALLY ====================
window.translateLine = translateLine;
window.answerQuestion = answerQuestion;
window.speakText = speakText;
window.copyToClipboard = copyToClipboard;
window.addToNotebook = addToNotebook;
window.submitQuizAnswer = submitQuizAnswer;