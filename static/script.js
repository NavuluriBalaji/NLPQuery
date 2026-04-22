let messageCount = 1;

function updateMsgCount() {
    document.getElementById('msg-count').textContent = `${messageCount} messages`;
}

function getCurrentTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

document.getElementById('init-time').textContent = getCurrentTime();
updateMsgCount();

// Add chat message
function addMessage(text, isUser = false) {
    const chatContainer = document.getElementById('chat-container');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const avatar = isUser ? '👤' : '🤖';
    const avatarClass = isUser ? 'bg-light' : 'bg-dark';
    
    msgDiv.innerHTML = `
        <div class="avatar ${avatarClass}">${avatar}</div>
        <div class="msg-content">
            <div class="bubble">${text}</div>
            <div class="time">${getCurrentTime()}</div>
        </div>
    `;
    
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    messageCount++;
    updateMsgCount();
}

function addSystemMessage(text, id = null) {
    const chatContainer = document.getElementById('chat-container');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message bot-message`;
    if (id) msgDiv.id = id;
    
    msgDiv.innerHTML = `
        <div class="avatar bg-dark">🤖</div>
        <div class="msg-content">
            <div class="querying-bubble">
                ${text} <span class="spinner"></span>
            </div>
        </div>
    `;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return msgDiv;
}

// DB Status
async function checkStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        if (data.connected_db) {
            document.querySelector('.form-card').classList.add('hidden');
            const activeCard = document.getElementById('active-db-card');
            activeCard.classList.remove('hidden');
            document.getElementById('active-db-title').textContent = 'Connected: ' + data.connected_db;
            document.getElementById('active-db-detail').textContent = 'PostgreSQL';
            document.getElementById('active-db-time').textContent = new Date().toLocaleString();
        }
    } catch (e) {
        console.error("Could not fetch DB status");
    }
}
checkStatus();

// Connect DB
document.getElementById('connect-db-btn').addEventListener('click', async () => {
    const host = document.getElementById('db-host').value.trim();
    const port = parseInt(document.getElementById('db-port').value.trim());
    const name = document.getElementById('db-name').value.trim();
    const user = document.getElementById('db-user').value.trim();
    const password = document.getElementById('db-password').value.trim();
    
    if(!host || !port || !name || !user) return;

    const btn = document.getElementById('connect-db-btn');
    const spinner = document.getElementById('db-spinner');
    const errorEl = document.getElementById('db-error');

    btn.disabled = true;
    spinner.classList.remove('hidden');
    errorEl.classList.add('hidden');

    try {
        const response = await fetch('/api/connect_db', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port, name, user, password })
        });
        const data = await response.json();
        
        if (!response.ok || data.error) {
            errorEl.textContent = data.detail || data.error || 'Connection failed.';
            errorEl.classList.remove('hidden');
        } else {
            checkStatus();
            addMessage(`Successfully connected to database '${data.db_name}' and loaded ${data.tables_loaded} tables!`);
        }
    } catch (e) {
        errorEl.textContent = 'Network error or server is down.';
        errorEl.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        spinner.classList.add('hidden');
    }
});

// Chat Send
const inputField = document.getElementById('question');
const sendBtn = document.getElementById('send-btn');

async function handleSend() {
    const question = inputField.value.trim();
    if (!question) return;

    addMessage(question, true);
    inputField.value = '';
    
    sendBtn.disabled = true;
    sendBtn.innerHTML = '⏸';
    sendBtn.classList.add('cancel');

    const sysMsgId = 'sys-' + Date.now();
    addSystemMessage(`Querying Database...`, sysMsgId);

    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        
        const sysMsg = document.getElementById(sysMsgId);
        if (sysMsg) sysMsg.remove();

        const data = await response.json();
        
        if (!response.ok || data.error) {
            addMessage(`Error: ${data.detail || data.error}`);
        } else {
            let reply = ``;
            if (data.generated_sql) {
                reply += `Here is the SQL query for your question:<br><div class="sql-block">${data.generated_sql}</div>`;
            } else {
                reply += `I couldn't generate a SQL query for that.`;
            }
            if (data.explanation) {
                reply += `<br><br><strong>Explanation:</strong> ${data.explanation}`;
            }
            addMessage(reply);
        }
    } catch (e) {
        const sysMsg = document.getElementById(sysMsgId);
        if (sysMsg) sysMsg.remove();
        addMessage('Network error or server is down.');
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '↑';
        sendBtn.classList.remove('cancel');
    }
}

sendBtn.addEventListener('click', handleSend);
inputField.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSend();
    }
});
