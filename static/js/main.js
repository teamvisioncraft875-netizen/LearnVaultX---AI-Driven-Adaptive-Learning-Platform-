// Main JavaScript for LearnVaultX Platform

// Register Service Worker for offline support
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(registration => {
                console.log('Service Worker registered:', registration);
            })
            .catch(error => {
                console.log('Service Worker registration failed:', error);
            });
    });
}

// AI Chatbot functionality
let aiPanelOpen = false;
let speechRecognition;
let isRecognizing = false;
let ttsEnabled = true;
let currentUtterance = null;
let ttsInitialized = false;
let pendingTtsQueue = [];
let wakeEnabled = true; // Auto-enable wake word on load
let wakeRecognizer = null;
let isWakeListening = false;

function toggleAIPanel() {
    console.log('toggleAIPanel called');
    // Try to find AI panel - could be #ai-chatbot or #ai-panel depending on page
    const panel = document.getElementById('ai-chatbot') || document.getElementById('ai-panel');
    const toggleBtn = document.getElementById('ai-toggle-btn');

    console.log('Panel element:', panel);
    console.log('Toggle button:', toggleBtn);

    if (!panel) {
        console.error('AI chatbot panel not found');
        if (typeof toast !== 'undefined') {
            toast.error('AI chatbot is not available on this page', 'Feature Unavailable');
        }
        return;
    }

    // Toggle panel visibility
    const isHidden = panel.classList.contains('hidden') || panel.classList.contains('collapsed');

    if (isHidden) {
        panel.classList.remove('hidden', 'collapsed');
        if (toggleBtn) {
            toggleBtn.classList.add('panel-open');
            toggleBtn.title = '❌ Close AI Chatbot';
        }
        // Save state
        try {
            localStorage.setItem('aiPanelOpen', 'true');
        } catch (e) {
            console.warn('Could not save panel state:', e);
        }
    } else {
        panel.classList.add('collapsed');
        if (toggleBtn) {
            toggleBtn.classList.remove('panel-open');
            toggleBtn.title = '💬 Open AI Chatbot (KyKnoX)';
        }
        // Save state
        try {
            localStorage.setItem('aiPanelOpen', 'false');
        } catch (e) {
            console.warn('Could not save panel state:', e);
        }
    }
}

async function sendAIMessage() {
    const input = document.getElementById('ai-input');
    const prompt = input.value.trim();

    if (!prompt) return;

    const messagesContainer = document.getElementById('ai-messages');

    // Add user message
    const userMessage = document.createElement('div');
    userMessage.className = 'ai-message user';
    userMessage.innerHTML = `<p>${escapeHtml(prompt)}</p>`;
    messagesContainer.appendChild(userMessage);

    // Clear input
    input.value = '';

    // Add loading message
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'ai-message loading';
    loadingMessage.id = 'ai-loading';
    loadingMessage.innerHTML = '<p>Thinking...</p>';
    messagesContainer.appendChild(loadingMessage);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
        const response = await fetch('/api/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt })
        });

        // Handle non-OK responses and show returned error messages
        if (!response.ok) {
            let err = { error: 'AI service error' };
            try { err = await response.json(); } catch (e) { /* ignore JSON parse */ }
            const loading = document.getElementById('ai-loading');
            if (loading) loading.remove();
            const errorMessage = document.createElement('div');
            errorMessage.className = 'ai-message bot';
            const msgText = escapeHtml(err.error || err.detail || 'AI service error. Please try again later.');
            errorMessage.innerHTML = `<p>${msgText}</p>`;
            messagesContainer.appendChild(errorMessage);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            return;
        }

        const data = await response.json();

        // Remove loading message
        const loadingEl = document.getElementById('ai-loading');
        if (loadingEl) loadingEl.remove();

        // Add AI response (rendered HTML from backend includes markdown and math)
        const aiMessage = document.createElement('div');
        aiMessage.className = 'ai-message bot';
        // Don't escape HTML since backend returns rendered markdown
        const providerLabel = data.provider ? `<div class="ai-meta"><small>source: ${escapeHtml(data.provider)}</small></div>` : '';
        aiMessage.innerHTML = `<div class="ai-content">${data.answer}</div>${providerLabel}`;
        messagesContainer.appendChild(aiMessage);

        // Trigger MathJax rendering for math equations
        if (typeof MathJax !== 'undefined' && MathJax.typeset) {
            MathJax.typeset([aiMessage]);
        }

        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Auto-speak AI reply if enabled
        if (ttsEnabled) {
            speakText(stripHtmlTags(data.raw || aiMessage.textContent || ''));
        }

    } catch (error) {
        console.error('Error sending message to AI:', error);

        // Remove loading message
        const loading = document.getElementById('ai-loading');
        if (loading) loading.remove();

        // Add error message with toast notification
        const errorMessage = document.createElement('div');
        errorMessage.className = 'ai-message bot';
        errorMessage.innerHTML = '<p>Sorry, I encountered an error. Please try again.</p>';
        messagesContainer.appendChild(errorMessage);

        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Show toast notification for better visibility
        if (typeof toast !== 'undefined') {
            toast.error('Failed to get AI response. Please try again.', 'AI Error');
        }
    }
}

// Handle Enter key in AI input
document.addEventListener('DOMContentLoaded', () => {
    const aiInput = document.getElementById('ai-input');
    if (aiInput) {
        aiInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendAIMessage();
            }
        });
    }

    // Initialize Web Speech API if available
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        speechRecognition = new SpeechRecognition();
        speechRecognition.lang = 'en-US';
        speechRecognition.interimResults = true;
        speechRecognition.continuous = false;

        speechRecognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            if (aiInput) aiInput.value = transcript.trim();
        };

        speechRecognition.onerror = () => {
            isRecognizing = false;
            setMicActive(false);
        };

        speechRecognition.onend = () => {
            isRecognizing = false;
            setMicActive(false);
            // Auto-send when voice input stops
            const aiInput = document.getElementById('ai-input');
            if (aiInput && aiInput.value.trim()) {
                sendAIMessage();
            }
        };
    }

    // Initialize TTS voices early (some browsers need warm-up)
    initTTS();

    // Reflect default TTS state on the toggle button
    const ttsBtn = document.getElementById('ai-tts-toggle');
    if (ttsBtn && ttsEnabled) {
        ttsBtn.classList.add('enabled');
    }

    // One-time resume to satisfy user-gesture audio policies
    const resumeOnce = () => {
        try { if ('speechSynthesis' in window) window.speechSynthesis.resume(); } catch { }
        window.removeEventListener('click', resumeOnce);
        window.removeEventListener('touchstart', resumeOnce);
    };
    window.addEventListener('click', resumeOnce, { once: true });
    window.addEventListener('touchstart', resumeOnce, { once: true });

    // Initialize wake recognizer if supported
    const SpeechRecognition2 = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition2) {
        wakeRecognizer = new SpeechRecognition2();
        wakeRecognizer.lang = 'en-US';
        wakeRecognizer.interimResults = false;
        wakeRecognizer.continuous = true;
        wakeRecognizer.maxAlternatives = 1;

        wakeRecognizer.onresult = (e) => {
            for (let i = e.resultIndex; i < e.results.length; i++) {
                if (!e.results[i].isFinal) continue;
                const text = e.results[i][0].transcript.toLowerCase().trim();
                // Wake patterns for KyKnoX
                if (text.includes('hey kyknox') || text.includes('hi kyknox') ||
                    text.includes('okay kyknox') || text.includes('ok kyknox') ||
                    text.includes('hello kyknox') || text.includes('hey kai nox')) {
                    handleWakeWord();
                    break;
                }
            }
        };

        wakeRecognizer.onstart = () => {
            isWakeListening = true;
            updateWakeStatus(true);
        };

        wakeRecognizer.onend = () => {
            isWakeListening = false;
            updateWakeStatus(false);
            // Auto-restart when wake is enabled
            if (wakeEnabled) {
                setTimeout(() => {
                    try { wakeRecognizer.start(); } catch { }
                }, 100);
            }
        };

        wakeRecognizer.onerror = (e) => {
            // Suppress normal errors, only log unexpected ones
            if (e.error !== 'no-speech' && e.error !== 'aborted') {
                console.warn('Wake recognizer error:', e.error);
            }
            if (e.error === 'no-speech' || e.error === 'aborted') {
                // Normal - restart
                if (wakeEnabled) {
                    setTimeout(() => {
                        try { wakeRecognizer.start(); } catch { }
                    }, 500);
                }
            }
        };

        // Auto-start wake word listening on load
        const wakeBtn = document.getElementById('ai-wake-toggle');
        if (wakeBtn) wakeBtn.classList.add('enabled');
        setTimeout(() => {
            try { wakeRecognizer.start(); } catch { }
        }, 1000);
    }
});

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function stripHtmlTags(html) {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
}

// Voice input controls
function setMicActive(active) {
    const micBtn = document.getElementById('ai-mic-btn');
    if (micBtn) {
        if (active) {
            micBtn.classList.add('recording');
        } else {
            micBtn.classList.remove('recording');
        }
    }
}

function startVoiceInput() {
    if (!speechRecognition) {
        if (typeof toast !== 'undefined') {
            toast.warning('Voice input is not supported in your browser', 'Feature Unavailable');
        }
        return;
    }
    try {
        speechRecognition.start();
        isRecognizing = true;
        setMicActive(true);
    } catch (e) {
        console.error('Microphone access failed', e);
        if (typeof toast !== 'undefined') {
            toast.error('Microphone access denied. Please allow microphone access in your browser settings.', 'Microphone Error');
        }
    }
}

function stopVoiceInput() {
    if (!speechRecognition || !isRecognizing) return;
    try {
        speechRecognition.stop();
        isRecognizing = false;
        setMicActive(false);
    } catch (e) {
        console.error('Stop recognition failed', e);
    }
}

// TTS controls
window.toggleTTS = function toggleTTS() {
    ttsEnabled = !ttsEnabled;
    const btn = document.getElementById('ai-tts-toggle');
    if (btn) {
        btn.classList.toggle('enabled', ttsEnabled);
    }
    if (!ttsEnabled) {
        stopSpeaking();
        return;
    }
    // User gesture present: resume audio context if paused by browser
    try { if ('speechSynthesis' in window) window.speechSynthesis.resume(); } catch { }
    // Optional confirmation readout so users know it's on
    speakText('Voice enabled');
};

// Wake word toggle
window.toggleWakeWord = function toggleWakeWord() {
    wakeEnabled = !wakeEnabled;
    const btn = document.getElementById('ai-wake-toggle');
    if (btn) btn.classList.toggle('enabled', wakeEnabled);
    if (!wakeRecognizer) return;
    try {
        if (wakeEnabled) {
            wakeRecognizer.start();
        } else {
            wakeRecognizer.stop();
        }
    } catch { }
};

// Wake word handler
function handleWakeWord() {
    // Bring attention to chatbot
    const panel = document.getElementById('ai-chatbot');
    const toggleBtn = document.getElementById('ai-toggle-btn');

    if (panel && panel.classList.contains('hidden')) {
        toggleAIPanel();
    }

    // Flash button to draw attention
    if (toggleBtn) {
        toggleBtn.style.animation = 'pulse 0.5s 3';
        setTimeout(() => {
            toggleBtn.style.animation = '';
        }, 1500);
    }

    // Speak acknowledgment
    speakText('Yes? How can I help you?');
}

// Update wake status indicator
function updateWakeStatus(listening) {
    const wakeBtn = document.getElementById('ai-wake-toggle');
    if (wakeBtn) {
        if (listening) {
            wakeBtn.classList.add('listening');
        } else {
            wakeBtn.classList.remove('listening');
        }
    }
}

// TTS Implementation
function initTTS() {
    if (!('speechSynthesis' in window)) return;

    // Warm up voices (Chrome needs this)
    try {
        const populateVoiceList = () => {
            if (ttsInitialized) return;
            const voices = speechSynthesis.getVoices();
            if (voices.length > 0) {
                ttsInitialized = true;
                // Process any pending messages
                while (pendingTtsQueue.length > 0) {
                    const text = pendingTtsQueue.shift();
                    speakText(text);
                }
            }
        };

        speechSynthesis.onvoiceschanged = populateVoiceList;
        populateVoiceList();
    } catch (e) {
        console.warn('TTS initialization warning:', e);
    }
}

function speakText(text) {
    if (!text || !ttsEnabled) return;

    // If voices aren't ready yet, queue for later
    if (!ttsInitialized) {
        pendingTtsQueue.push(text);
        return;
    }

    stopSpeaking();

    try {
        currentUtterance = new SpeechSynthesisUtterance(text);
        currentUtterance.rate = 1.0;
        currentUtterance.pitch = 1.0;
        currentUtterance.volume = 1.0;

        currentUtterance.onend = () => {
            currentUtterance = null;
        };

        currentUtterance.onerror = () => {
            currentUtterance = null;
        };

        speechSynthesis.speak(currentUtterance);
    } catch (e) {
        console.error('TTS error:', e);
        currentUtterance = null;
    }
}

function stopSpeaking() {
    if (currentUtterance) {
        try {
            speechSynthesis.cancel();
        } catch (e) {
            console.warn('TTS cancel error:', e);
        }
        currentUtterance = null;
    }
}

// Export functions for use in other scripts
window.LearnVaultX = {
    toggleAIPanel,
    sendAIMessage,
    // Voice helpers
    toggleTTS,
    speak: (text) => speakText(text)
};
