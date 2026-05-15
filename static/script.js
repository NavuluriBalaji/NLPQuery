const HISTORY_KEY = 'askdb_history';
const questionInput = document.getElementById('question');
const sendBtn = document.getElementById('send-btn');
const sendIcon = document.getElementById('send-icon');
const chatContainer = document.getElementById('chat-container');
const msgCountSpan = document.getElementById('msg-count');
const historyList = document.getElementById('history-list');

let dbConfig = null;

// ─── Modal Handling ───────────────────────────────────────────────────────
const dbModal = document.getElementById('db-modal');
document.getElementById('open-db-modal-btn').addEventListener('click', () => {
    dbModal.classList.remove('hidden');
});
document.getElementById('close-db-modal').addEventListener('click', () => {
    dbModal.classList.add('hidden');
});

// ─── Custom Dropdown Handling ─────────────────────────────────────────────
const modelDropdown = document.getElementById('model-dropdown');
const dropdownSelected = document.querySelector('.dropdown-selected');
const dropdownOptionsBox = document.getElementById('dropdown-options');
const selectedModelText = document.getElementById('selected-model-text');
const dropdownOptions = document.querySelectorAll('.dropdown-option');

let currentModelId = 'nvidia/nemotron-4-340b-instruct'; // Default selected

if (dropdownSelected) {
    dropdownSelected.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownOptionsBox.classList.toggle('hidden');
    });

    dropdownOptions.forEach(option => {
        option.addEventListener('click', () => {
            dropdownOptions.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            selectedModelText.textContent = option.textContent;
            currentModelId = option.getAttribute('data-value');
            dropdownOptionsBox.classList.add('hidden');
        });
    });

    document.addEventListener('click', (e) => {
        if (!modelDropdown.contains(e.target)) {
            dropdownOptionsBox.classList.add('hidden');
        }
    });
}

// ─── Helpers ──────────────────────────────────────────────────────────────
let messageCount = 0;

function updateMessageCount() {
    messageCount++;
    msgCountSpan.textContent = `${messageCount} messages`;
}

function escapeHtml(unsafe) {
    return (unsafe || '').toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function formatTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

window.copySql = function(btn) {
    const text = btn.previousElementSibling.innerText;
    navigator.clipboard.writeText(text).then(() => {
        btn.innerText = "Copied!";
        btn.classList.add("copied");
        setTimeout(() => {
            btn.innerText = "Copy";
            btn.classList.remove("copied");
        }, 2000);
    });
};

window.showToast = function(message, type = "error") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        document.body.appendChild(container);
    }
    
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    const icon = type === "error" 
        ? `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
        : `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
        
    toast.innerHTML = `${icon} <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    
    requestAnimationFrame(() => toast.classList.add("show"));
    
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};

// ─── Chat UI ──────────────────────────────────────────────────────────────
function appendUserMessage(text) {
    const timeStr = formatTime();
    const msgHtml = `
        <div class="message">
            <div class="msg-header">
                <div class="avatar user-avatar"></div>
                <span class="sender-name">User</span>
                <span class="msg-time">${timeStr}</span>
            </div>
            <div class="msg-body">${escapeHtml(text)}</div>
        </div>
    `;
    chatContainer.insertAdjacentHTML('beforeend', msgHtml);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    updateMessageCount();
}

function appendBotMessage(data) {
    const timeStr = formatTime();
    let bodyHtml = "";

    if (data.error) {
        bodyHtml = `<div style="color: #ef4444;"> Error: ${escapeHtml(data.error)}</div>`;
    } else {
        const sqlText = escapeHtml(data.generated_sql || '-- No SQL generated');
        const explText = escapeHtml(data.explanation || 'No explanation provided.');
        
        bodyHtml += `
            <div>I've generated the SQL query for you. Here is the result:</div>
            <div class="sql-container">
                <div class="sql-block">${sqlText}</div>
                <button class="copy-btn" onclick="copySql(this)">Copy</button>
            </div>
            <div class="explanation-block">
                <div class="explanation-label">Explanation</div>
                <div class="explanation-text">${explText}</div>
            </div>
        `;

        if (data.follow_up_questions && data.follow_up_questions.length > 0) {
            bodyHtml += '<div class="followup-block"><div class="followup-label">Suggested follow-ups</div><div class="followup-chips">';
            data.follow_up_questions.forEach(q => {
                const safeQ = escapeHtml(q);
                bodyHtml += '<div class="followup-chip" data-question="' + safeQ + '" onclick="askFollowUp(this)">' + safeQ + '</div>';
            });
            bodyHtml += '</div></div>';
        }
    }

    const msgHtml = `
        <div class="message">
            <div class="msg-header">
                <div class="avatar bot-avatar">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                </div>
                <span class="sender-name">Agent</span>
                <span class="msg-time">${timeStr}</span>
            </div>
            <div class="msg-body bot-body">
                ${bodyHtml}
            </div>
        </div>
    `;
    chatContainer.insertAdjacentHTML('beforeend', msgHtml);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    updateMessageCount();
}

function appendSystemMessage(text) {
    const timeStr = formatTime();
    const msgHtml = `
        <div class="message">
            <div class="msg-header">
                <div class="avatar bot-avatar">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                </div>
                <span class="sender-name">System</span>
                <span class="msg-time">${timeStr}</span>
            </div>
            <div class="msg-body bot-body" style="color:var(--text-muted)">
                ${text}
            </div>
        </div>
    `;
    chatContainer.insertAdjacentHTML('beforeend', msgHtml);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

let typingIndicatorId = null;

function showTypingIndicator() {
    const timeStr = formatTime();
    const id = 'typing-' + Date.now();
    typingIndicatorId = id;
    const msgHtml = `
        <div class="message" id="${id}">
            <div class="msg-header">
                <div class="avatar bot-avatar">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                </div>
                <span class="sender-name">Agent</span>
                <span class="msg-time">${timeStr}</span>
            </div>
            <div class="msg-body bot-body" style="padding: 1rem 1.5rem; display: inline-block;">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        </div>
    `;
    chatContainer.insertAdjacentHTML('beforeend', msgHtml);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeTypingIndicator() {
    if (typingIndicatorId) {
        const el = document.getElementById(typingIndicatorId);
        if (el) el.remove();
        typingIndicatorId = null;
    }
}

function setQueryingState(isQuerying) {
    if (isQuerying) {
        // Replace button content only — never replace the button itself
        sendBtn.innerHTML = '<div class="spinner"></div> Sending...';
        sendBtn.disabled = true;
        questionInput.disabled = true;
    } else {
        sendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Send';
        sendBtn.disabled = false;
        questionInput.disabled = false;
        questionInput.focus();
    }
}

// ─── API Calls ────────────────────────────────────────────────────────────
// Expose handleSend globally so inline onclick and follow-up chips can reach it
window.askFollowUp = function(el) {
    const question = el.getAttribute('data-question');
    if (!question || !question.trim()) return;

    // Decode any HTML entities (browsers encode & → &amp; in data attributes)
    const txt = document.createElement('textarea');
    txt.innerHTML = question;
    const decoded = txt.value;

    questionInput.value = decoded;
    questionInput.disabled = false; // ensure not stuck in disabled state

    // Small delay so value is committed before handleSend reads it
    setTimeout(() => handleSend(), 0);
};

async function handleSend() {
    const q = questionInput.value.trim();
    if (!q) return;

    if (!dbConfig) {
        showToast("Please connect your database first!", "error");
        dbModal.classList.remove('hidden');
        return;
    }

    appendUserMessage(q);
    questionInput.value = '';
    setQueryingState(true);
    showTypingIndicator();

    try {
        const res = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q, workspace: currentModelId })
        });
        const data = await res.json();
        
        removeTypingIndicator();
        appendBotMessage(data);
        saveHistory(q);
    } catch (err) {
        removeTypingIndicator();
        appendBotMessage({ error: "Failed to connect to backend API." });
    } finally {
        setQueryingState(false);
    }
}

document.getElementById('connect-db-btn').addEventListener('click', async () => {
    const host = document.getElementById('db-host').value;
    const port = document.getElementById('db-port').value;
    const name = document.getElementById('db-name').value;
    const user = document.getElementById('db-user').value;
    const password = document.getElementById('db-password').value;
    const errText = document.getElementById('db-error');
    const spinner = document.getElementById('db-spinner');
    
    if(!host || !port || !name || !user) {
        errText.textContent = "Please fill all fields";
        errText.classList.remove('hidden');
        return;
    }

    spinner.classList.remove('hidden');
    errText.classList.add('hidden');
    document.getElementById('connect-db-btn').disabled = true;

    try {
        const res = await fetch('/api/connect_db', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port: parseInt(port), name, user, password })
        });
        const data = await res.json();
        
        if (data.status === "success") {
            dbConfig = { host, port, name, user };
            dbModal.classList.add('hidden');
            document.getElementById('db-status-text').textContent = `Connected: ${name}`;
            appendSystemMessage(`Successfully connected to database <b>${name}</b>.`);
            showToast(`Connected to ${name}`, "success");
        } else {
            errText.textContent = data.detail || "Connection failed";
            errText.classList.remove('hidden');
        }
    } catch (err) {
        errText.textContent = "API error. Check server logs.";
        errText.classList.remove('hidden');
    } finally {
        spinner.classList.add('hidden');
        document.getElementById('connect-db-btn').disabled = false;
    }
});

// ─── History panel ────────────────────────────────────────────────────────
function saveHistory(query) {
    let hist = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    hist.unshift(query);
    if(hist.length > 20) hist = hist.slice(0, 20);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(hist));
    renderHistory();
}

function renderHistory() {
    let hist = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    historyList.innerHTML = '';
    
    if (hist.length === 0) {
        historyList.innerHTML = '<div style="color:var(--text-light); font-size:0.8rem;">No recent queries.</div>';
        return;
    }

    hist.forEach(q => {
        const el = document.createElement('div');
        el.className = 'history-item';
        el.textContent = q;
        el.title = q;
        el.onclick = () => {
            questionInput.value = q;
            questionInput.focus();
        };
        historyList.appendChild(el);
    });
}

window.clearHistory = function() {
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
};

// ─── Voice Input (Web Speech API) ─────────────────────────────────────────
const voiceBtn = document.getElementById('voice-btn');
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognitionAPI && voiceBtn) {
    let recognition = null;
    let isRecording = false;

    function stopRecording() {
        isRecording = false;
        voiceBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> Voice`;
        voiceBtn.style.color = '';
        voiceBtn.style.borderColor = '';
        questionInput.placeholder = "Ask me anything...";
        recognition = null; // discard used instance
    }

    function startRecording() {
        // Always create a fresh instance – reusing a completed instance throws InvalidStateError
        recognition = new SpeechRecognitionAPI();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = function() {
            isRecording = true;
            voiceBtn.innerHTML = '🔴 Listening...';
            voiceBtn.style.color = '#ef4444';
            voiceBtn.style.borderColor = '#ef4444';
            questionInput.placeholder = "Listening...";
        };

        recognition.onresult = function(event) {
            let interimTranscript = '';
            let finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }
            questionInput.value = finalTranscript || interimTranscript;
        };

        recognition.onerror = function(event) {
            console.error("Speech recognition error:", event.error);
            stopRecording();
        };

        recognition.onend = function() {
            const capturedText = questionInput.value.trim();
            stopRecording();
            if (capturedText.length > 0) {
                questionInput.value = capturedText; // restore in case cleared
                handleSend();
            }
        };

        try {
            questionInput.value = '';
            recognition.start();
        } catch (err) {
            console.error("Could not start recognition:", err);
            stopRecording();
        }
    }

    voiceBtn.addEventListener('click', () => {
        if (isRecording && recognition) {
            recognition.stop(); // onend will fire and clean up
        } else {
            startRecording();
        }
    });

} else if (voiceBtn) {
    voiceBtn.addEventListener('click', () => {
        showToast("Voice recognition is not supported in this browser. Try Chrome or Edge.", "error");
    });
}

// ─── Initialization ───────────────────────────────────────────────────────
sendBtn.addEventListener('click', handleSend);
questionInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSend();
});

renderHistory();
appendSystemMessage("Hello! How can I assist you today? Please connect your database first.");
