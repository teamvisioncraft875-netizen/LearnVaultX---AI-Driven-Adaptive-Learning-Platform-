/**
 * ai_tutor_ui.js — Chat Logic + Panel Rendering for AI Tutor Page
 * Handles: message sending, learning summary, quick prompts, actions panel
 */

(function () {
    'use strict';

    // ═══════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════
    let isWaitingForResponse = false;
    let learningData = null;
    let micRecognition = null;
    let isMicActive = false;

    // ═══════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', function () {
        loadLearningSummary();
        loadChatHistory();
        autoResizeInput();
    });

    // ═══════════════════════════════════════════════
    // LEARNING SUMMARY
    // ═══════════════════════════════════════════════
    function loadLearningSummary() {
        fetch('/api/student/learning_summary')
            .then(r => r.json())
            .then(data => {
                if (!data.success) return;
                learningData = data.data;
                renderSummaryChips(learningData);
            })
            .catch(err => console.error('Failed to load learning summary:', err));
    }

    function renderSummaryChips(data) {
        const chipProgress = document.getElementById('chipProgress');
        const chipQuizzes = document.getElementById('chipQuizzes');
        const chipAvgScore = document.getElementById('chipAvgScore');
        const chipNextModule = document.getElementById('chipNextModule');
        const chipNextText = document.getElementById('chipNextText');

        if (chipProgress) chipProgress.textContent = data.overall_progress + '%';
        if (chipQuizzes) chipQuizzes.textContent = data.total_attempts;
        if (chipAvgScore) chipAvgScore.textContent = data.average_score + '%';

        if (data.next_recommended_module && chipNextModule && chipNextText) {
            chipNextModule.style.display = 'flex';
            chipNextText.textContent = data.next_recommended_module.module_title || 'N/A';
        }
    }

    // ═══════════════════════════════════════════════
    // CHAT HISTORY
    // ═══════════════════════════════════════════════
    function loadChatHistory() {
        fetch('/api/tutor/history')
            .then(r => r.json())
            .then(data => {
                if (!data.success || !data.history || data.history.length === 0) return;

                // Remove welcome state
                const welcome = document.getElementById('welcomeState');
                if (welcome) welcome.style.display = 'none';

                data.history.forEach(entry => {
                    appendMessage('user', entry.message, false);
                    appendMessage('ai', entry.response, false);
                });

                scrollToBottom();
            })
            .catch(() => { }); // Silent fail
    }

    // ═══════════════════════════════════════════════
    // SEND MESSAGE
    // ═══════════════════════════════════════════════
    window.sendMessage = function () {
        const input = document.getElementById('chatInput');
        const text = (input.value || '').trim();
        if (!text || isWaitingForResponse) return;

        input.value = '';
        input.style.height = 'auto';

        // Hide welcome
        const welcome = document.getElementById('welcomeState');
        if (welcome) welcome.style.display = 'none';

        // Add user message
        appendMessage('user', text);

        // Show typing
        showTyping();

        // Set avatar thinking state
        setAvatarStatus('thinking', 'Thinking...');

        isWaitingForResponse = true;
        updateSendButton();

        fetch('/api/tutor/respond', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        })
            .then(r => r.json())
            .then(data => {
                hideTyping();
                isWaitingForResponse = false;
                updateSendButton();

                if (!data.success) {
                    appendMessage('ai', '❌ Sorry, I encountered an error. Please try again.');
                    setAvatarStatus('idle', 'Ready to help');
                    return;
                }

                // Update avatar
                if (window.AvatarController && AvatarController.isReady()) {
                    if (data.emotion) AvatarController.setEmotion(data.emotion);
                    if (data.gesture === 'nod') AvatarController.triggerNod();
                }

                // Start lip sync
                if (window.LipSyncController) {
                    LipSyncController.start(data.text);
                }

                // Display AI response with typing effect
                appendMessage('ai', data.text, true);

                // Update recommended actions
                if (data.recommended_actions && data.recommended_actions.length) {
                    renderActions(data.recommended_actions);
                }

                // Speak the response aloud if voice is enabled
                if (window.VoiceEngine && VoiceEngine.isEnabled()) {
                    // VoiceEngine handles its own lip sync via word boundary events
                    if (window.LipSyncController) LipSyncController.stop();
                    VoiceEngine.speak(data.text);
                }
            })
            .catch(err => {
                hideTyping();
                isWaitingForResponse = false;
                updateSendButton();
                appendMessage('ai', '❌ Connection error. Please check your network and try again.');
                setAvatarStatus('idle', 'Ready to help');
                console.error('Tutor API error:', err);
            });
    };

    // ═══════════════════════════════════════════════
    // QUICK PROMPTS
    // ═══════════════════════════════════════════════
    window.sendQuickPrompt = function (btn) {
        const text = btn.textContent.replace(/^[^\s]+\s/, '').trim(); // Remove emoji prefix
        const input = document.getElementById('chatInput');
        if (input) input.value = text;
        window.sendMessage();
    };

    // ═══════════════════════════════════════════════
    // KEYBOARD HANDLER
    // ═══════════════════════════════════════════════
    window.handleChatKey = function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            window.sendMessage();
        }
    };

    // ═══════════════════════════════════════════════
    // VOICE INPUT (Speech-to-Text)
    // ═══════════════════════════════════════════════
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    window.toggleMicInput = function () {
        if (!SpeechRecognition) {
            _voiceToast('🚫 Speech recognition is not supported in this browser.');
            return;
        }

        // Stop any ongoing TTS before listening
        if (window.VoiceEngine && VoiceEngine.isSpeaking()) {
            VoiceEngine.stop();
        }

        if (isMicActive && micRecognition) {
            micRecognition.stop();
            return;
        }

        micRecognition = new SpeechRecognition();
        micRecognition.lang = 'en-US';
        micRecognition.interimResults = true;
        micRecognition.continuous = false;
        micRecognition.maxAlternatives = 1;

        const micBtn = document.getElementById('micToggleBtn');
        const statusLabel = document.getElementById('voiceStatusLabel');
        const chatInput = document.getElementById('chatInput');

        micRecognition.onstart = function () {
            isMicActive = true;
            if (micBtn) micBtn.classList.add('mic-recording');
            if (statusLabel) {
                statusLabel.textContent = '🔴 Listening...';
                statusLabel.classList.add('listening');
            }
        };

        micRecognition.onresult = function (event) {
            let finalTranscript = '';
            let interimTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            // Show live transcript in input
            if (chatInput) {
                chatInput.value = finalTranscript || interimTranscript;
            }

            // Auto-submit on final result
            if (finalTranscript.trim()) {
                setTimeout(() => {
                    window.sendMessage();
                }, 400); // Brief delay so user can see what was recognized
            }
        };

        micRecognition.onerror = function (event) {
            console.warn('Speech recognition error:', event.error);
            if (event.error === 'not-allowed') {
                _voiceToast('🎤 Microphone access denied. Please allow mic in browser settings.');
            } else if (event.error !== 'aborted') {
                _voiceToast('🎤 Could not recognize speech. Please try again.');
            }
            _stopMicUI();
        };

        micRecognition.onend = function () {
            _stopMicUI();
        };

        micRecognition.start();
    };

    function _stopMicUI() {
        isMicActive = false;
        const micBtn = document.getElementById('micToggleBtn');
        const statusLabel = document.getElementById('voiceStatusLabel');
        if (micBtn) micBtn.classList.remove('mic-recording');
        if (statusLabel) {
            statusLabel.textContent = '';
            statusLabel.classList.remove('listening');
        }
    }

    function _voiceToast(message) {
        if (window.VoiceEngine && VoiceEngine._showToast) {
            VoiceEngine._showToast(message);
            return;
        }
        // Fallback
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
            padding: 10px 20px; background: rgba(17,24,39,0.95);
            border: 1px solid rgba(96,165,250,0.3); border-radius: 12px;
            color: #e5e7eb; font-size: 13px; z-index: 1000;
            backdrop-filter: blur(8px);
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; setTimeout(() => toast.remove(), 300); }, 2500);
    }

    // ═══════════════════════════════════════════════
    // MESSAGE RENDERING
    // ═══════════════════════════════════════════════
    function appendMessage(role, text, animate) {
        const container = document.getElementById('chatMessages');
        if (!container) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'chat-msg ' + (role === 'user' ? 'user-msg' : 'ai-msg');

        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';

        if (role === 'ai') {
            bubble.innerHTML = renderMarkdown(text);
        } else {
            bubble.textContent = text;
        }

        const time = document.createElement('div');
        time.className = 'msg-time';
        time.textContent = formatTime(new Date());

        wrapper.appendChild(bubble);
        wrapper.appendChild(time);
        container.appendChild(wrapper);

        scrollToBottom();
    }

    function showTyping() {
        const container = document.getElementById('chatMessages');
        if (!container) return;

        // Remove any existing typing indicator
        hideTyping();

        const typing = document.createElement('div');
        typing.className = 'chat-msg ai-msg';
        typing.id = 'typingIndicator';

        typing.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;

        container.appendChild(typing);
        scrollToBottom();
    }

    function hideTyping() {
        const typing = document.getElementById('typingIndicator');
        if (typing) typing.remove();
    }

    // ═══════════════════════════════════════════════
    // RECOMMENDED ACTIONS
    // ═══════════════════════════════════════════════
    function renderActions(actions) {
        const panel = document.getElementById('actionsPanel');
        const list = document.getElementById('actionsList');
        if (!panel || !list) return;

        list.innerHTML = '';
        actions.forEach(action => {
            const item = document.createElement('div');
            item.className = 'action-item';
            item.innerHTML = `<span class="action-icon">→</span><span>${escapeHtml(action)}</span>`;
            item.onclick = function () {
                // Send the action as a message
                const input = document.getElementById('chatInput');
                if (input) {
                    input.value = 'Tell me more about: ' + action;
                    window.sendMessage();
                }
            };
            list.appendChild(item);
        });

        panel.style.display = 'block';
    }

    // ═══════════════════════════════════════════════
    // AVATAR STATUS
    // ═══════════════════════════════════════════════
    function setAvatarStatus(state, text) {
        const dot = document.getElementById('avatarStatusDot');
        const statusText = document.getElementById('avatarStatusText');
        if (dot) dot.className = 'status-dot ' + state;
        if (statusText) statusText.textContent = text;
    }

    // ═══════════════════════════════════════════════
    // UTILITIES
    // ═══════════════════════════════════════════════
    function renderMarkdown(text) {
        if (!text) return '';

        let html = escapeHtml(text);

        // Bold **text**
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic *text*
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // Code `text`
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Headers
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        // Unordered lists
        html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
        // Fix nested ul
        html = html.replace(/<\/ul>\s*<ul>/g, '');
        // Ordered lists
        html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
        // Paragraphs - convert double newlines
        html = html.replace(/\n\n/g, '</p><p>');
        // Single newlines to <br>
        html = html.replace(/\n/g, '<br>');

        return '<p>' + html + '</p>';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function scrollToBottom() {
        const container = document.getElementById('chatMessages');
        if (container) {
            requestAnimationFrame(() => {
                container.scrollTop = container.scrollHeight;
            });
        }
    }

    function updateSendButton() {
        const btn = document.getElementById('chatSendBtn');
        if (btn) btn.disabled = isWaitingForResponse;
    }

    function autoResizeInput() {
        const input = document.getElementById('chatInput');
        if (!input) return;

        input.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }

})();
