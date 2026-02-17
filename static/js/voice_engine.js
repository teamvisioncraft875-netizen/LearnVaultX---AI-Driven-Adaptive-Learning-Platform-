/**
 * voice_engine.js — Browser-Native TTS for AI Tutor
 * Uses the Web Speech API (SpeechSynthesis) for zero-cost voice output.
 * Syncs with LipSyncController + AvatarController for real-time mouth animation.
 */

(function () {
    'use strict';

    // ═══════════════════════════════════════════════
    // CHECK SUPPORT
    // ═══════════════════════════════════════════════
    const isSupported = ('speechSynthesis' in window);

    // ═══════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════
    const VoiceEngine = {
        enabled: false,
        speaking: false,
        rate: 1.0,
        pitch: 1.0,
        volume: 0.9,
        selectedVoiceName: null,
        _voices: [],
        _queue: [],
        _currentUtterance: null,
        _wordTimer: null,

        // ═══════════════════════════════════════════════
        // INIT
        // ═══════════════════════════════════════════════
        init: function () {
            if (!isSupported) {
                console.warn('VoiceEngine: Web Speech API not supported in this browser.');
                return;
            }

            // Restore saved preferences
            this.enabled = localStorage.getItem('kyknoX_voice_enabled') === 'true';
            this.rate = parseFloat(localStorage.getItem('kyknoX_voice_rate') || '1.0');
            this.pitch = parseFloat(localStorage.getItem('kyknoX_voice_pitch') || '1.0');
            this.selectedVoiceName = localStorage.getItem('kyknoX_voice_name') || null;

            // Load available voices (they load async in some browsers)
            this._loadVoices();
            if (speechSynthesis.onvoiceschanged !== undefined) {
                speechSynthesis.onvoiceschanged = () => this._loadVoices();
            }

            // Update UI toggle state
            this._updateToggleUI();
        },

        // ═══════════════════════════════════════════════
        // VOICE LOADING
        // ═══════════════════════════════════════════════
        _loadVoices: function () {
            this._voices = speechSynthesis.getVoices();
            this._populateVoiceSelector();
        },

        _populateVoiceSelector: function () {
            const selector = document.getElementById('voiceSelect');
            if (!selector || this._voices.length === 0) return;

            selector.innerHTML = '';

            // Filter to English voices for education context, but keep all
            const englishVoices = this._voices.filter(v =>
                v.lang.startsWith('en')
            );
            const otherVoices = this._voices.filter(v =>
                !v.lang.startsWith('en')
            );

            // Add English voices first
            if (englishVoices.length > 0) {
                const engGroup = document.createElement('optgroup');
                engGroup.label = 'English';
                englishVoices.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.name;
                    opt.textContent = v.name + (v.localService ? ' (Local)' : ' (Network)');
                    if (this.selectedVoiceName === v.name) opt.selected = true;
                    engGroup.appendChild(opt);
                });
                selector.appendChild(engGroup);
            }

            // Add other voices in a second group
            if (otherVoices.length > 0) {
                const otherGroup = document.createElement('optgroup');
                otherGroup.label = 'Other Languages';
                otherVoices.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.name;
                    opt.textContent = v.name + ' (' + v.lang + ')';
                    if (this.selectedVoiceName === v.name) opt.selected = true;
                    otherGroup.appendChild(opt);
                });
                selector.appendChild(otherGroup);
            }

            // Auto-select a good English voice if no preference
            if (!this.selectedVoiceName && englishVoices.length > 0) {
                // Prefer Google or Microsoft voices for quality
                const preferred = englishVoices.find(v =>
                    v.name.includes('Google') || v.name.includes('Microsoft')
                );
                this.selectedVoiceName = preferred ? preferred.name : englishVoices[0].name;
            }
        },

        _getSelectedVoice: function () {
            if (!this.selectedVoiceName) return null;
            return this._voices.find(v => v.name === this.selectedVoiceName) || null;
        },

        // ═══════════════════════════════════════════════
        // CORE SPEAK
        // ═══════════════════════════════════════════════

        /**
         * Speak the given text using Text-to-Speech.
         * Splits into sentences for natural pacing.
         * @param {string} text - Text to speak
         */
        speak: function (text) {
            if (!isSupported || !this.enabled || !text) return;

            // Stop any current speech
            this.stop();

            // Clean the text for speech (remove markdown artifacts)
            const cleanText = this._cleanForSpeech(text);

            // Split into sentences for natural pausing
            const sentences = this._splitIntoSentences(cleanText);

            // Start avatar talking
            if (window.AvatarController && AvatarController.isReady()) {
                AvatarController.startTalking();
            }

            this.speaking = true;
            this._setStatus('talking', 'Speaking...');

            // Queue all sentences
            sentences.forEach((sentence, index) => {
                const utterance = new SpeechSynthesisUtterance(sentence);

                // Apply settings
                const voice = this._getSelectedVoice();
                if (voice) utterance.voice = voice;
                utterance.rate = this.rate;
                utterance.pitch = this.pitch;
                utterance.volume = this.volume;

                // Word boundary events → drive lip sync in real-time
                utterance.onboundary = (event) => {
                    if (event.name === 'word') {
                        const word = sentence.substr(event.charIndex, event.charLength || 5);
                        this._onWord(word);
                    }
                };

                // First utterance start
                if (index === 0) {
                    utterance.onstart = () => {
                        this.speaking = true;
                    };
                }

                // Last utterance end
                if (index === sentences.length - 1) {
                    utterance.onend = () => {
                        this._onSpeechComplete();
                    };
                    utterance.onerror = (e) => {
                        if (e.error !== 'canceled') {
                            console.warn('VoiceEngine speech error:', e.error);
                        }
                        this._onSpeechComplete();
                    };
                }

                speechSynthesis.speak(utterance);
                this._queue.push(utterance);
            });
        },

        /**
         * Stop all speech immediately.
         */
        stop: function () {
            if (isSupported) {
                speechSynthesis.cancel();
            }
            this._queue = [];
            this._currentUtterance = null;

            if (this._wordTimer) {
                clearTimeout(this._wordTimer);
                this._wordTimer = null;
            }

            if (this.speaking) {
                this._onSpeechComplete();
            }
        },

        /**
         * Toggle voice output on/off.
         */
        toggle: function () {
            this.enabled = !this.enabled;
            localStorage.setItem('kyknoX_voice_enabled', this.enabled.toString());

            if (!this.enabled) {
                this.stop();
            }

            this._updateToggleUI();

            // Show toast notification
            this._showToast(this.enabled ? '🔊 Voice output enabled' : '🔇 Voice output disabled');
        },

        // ═══════════════════════════════════════════════
        // SETTINGS
        // ═══════════════════════════════════════════════
        setRate: function (rate) {
            this.rate = Math.max(0.5, Math.min(2.0, parseFloat(rate)));
            localStorage.setItem('kyknoX_voice_rate', this.rate.toString());
        },

        setPitch: function (pitch) {
            this.pitch = Math.max(0.5, Math.min(2.0, parseFloat(pitch)));
            localStorage.setItem('kyknoX_voice_pitch', this.pitch.toString());
        },

        setVoice: function (voiceName) {
            this.selectedVoiceName = voiceName;
            localStorage.setItem('kyknoX_voice_name', voiceName);
        },

        toggleSettings: function () {
            const panel = document.getElementById('voiceSettingsPanel');
            if (panel) {
                const isVisible = panel.style.display !== 'none';
                panel.style.display = isVisible ? 'none' : 'block';
            }
        },

        // ═══════════════════════════════════════════════
        // INTERNAL — WORD-LEVEL LIP SYNC
        // ═══════════════════════════════════════════════
        _onWord: function (word) {
            if (!window.AvatarController || !AvatarController.isReady()) return;
            if (!word) return;

            // Analyze the word for mouth shape
            const chars = word.toLowerCase().split('');
            const visemeSequence = this._wordToVisemes(chars);

            // Play through the viseme sequence for this word
            let i = 0;
            const charDuration = Math.max(40, 120 / this.rate); // ms per character

            const playNext = () => {
                if (i >= visemeSequence.length || !this.speaking) return;

                AvatarController.setMouthOpen(visemeSequence[i]);
                i++;

                this._wordTimer = setTimeout(playNext, charDuration);
            };

            playNext();
        },

        _wordToVisemes: function (chars) {
            // Map characters to mouth openness values
            const visemeMap = {
                // Wide open vowels
                'a': 0.85, 'e': 0.7, 'i': 0.6, 'o': 0.75, 'u': 0.65,
                // Bilabials (lips together)
                'b': 0.05, 'p': 0.05, 'm': 0.05,
                // Labiodentals (lip tuck)
                'f': 0.2, 'v': 0.2,
                // Dental / alveolar
                't': 0.3, 'd': 0.3, 'n': 0.35, 'l': 0.4,
                's': 0.15, 'z': 0.15,
                // Palatal
                'r': 0.4, 'j': 0.5, 'y': 0.5,
                // Velar
                'k': 0.3, 'g': 0.3,
                // Others
                'h': 0.5, 'w': 0.55,
                'c': 0.3, 'q': 0.35, 'x': 0.2,
                // Th sounds approximation
                'þ': 0.2
            };

            return chars.map(c => visemeMap[c] || 0.3);
        },

        _onSpeechComplete: function () {
            this.speaking = false;

            // Close mouth
            if (window.AvatarController && AvatarController.isReady()) {
                AvatarController.setMouthOpen(0);
                AvatarController.stopTalking();
            }

            this._setStatus('idle', 'Ready to help');
        },

        // ═══════════════════════════════════════════════
        // TEXT CLEANING
        // ═══════════════════════════════════════════════
        _cleanForSpeech: function (text) {
            if (!text) return '';

            return text
                // Remove markdown bold/italic
                .replace(/\*\*(.+?)\*\*/g, '$1')
                .replace(/\*(.+?)\*/g, '$1')
                // Remove code blocks
                .replace(/`([^`]+)`/g, '$1')
                // Remove headers
                .replace(/^#{1,3}\s+/gm, '')
                // Remove list markers
                .replace(/^[-*]\s+/gm, '')
                .replace(/^\d+\.\s+/gm, '')
                // Clean up extra whitespace
                .replace(/\n{2,}/g, '. ')
                .replace(/\n/g, ' ')
                .trim();
        },

        _splitIntoSentences: function (text) {
            // Split on sentence boundaries
            const raw = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text];
            return raw
                .map(s => s.trim())
                .filter(s => s.length > 0);
        },

        // ═══════════════════════════════════════════════
        // UI HELPERS
        // ═══════════════════════════════════════════════
        _updateToggleUI: function () {
            const btn = document.getElementById('voiceToggleBtn');
            if (!btn) return;

            if (this.enabled) {
                btn.classList.add('voice-active');
                btn.title = 'Voice output ON — click to disable';
                btn.innerHTML = '🔊';
            } else {
                btn.classList.remove('voice-active');
                btn.title = 'Voice output OFF — click to enable';
                btn.innerHTML = '🔇';
            }
        },

        _setStatus: function (state, text) {
            const dot = document.getElementById('avatarStatusDot');
            const statusText = document.getElementById('avatarStatusText');
            if (dot) dot.className = 'status-dot ' + state;
            if (statusText) statusText.textContent = text;
        },

        _showToast: function (message) {
            // Try using page-level toast first
            if (typeof showToast === 'function') {
                showToast(message);
                return;
            }

            // Fallback toast
            const existing = document.getElementById('voiceToast');
            if (existing) existing.remove();

            const toast = document.createElement('div');
            toast.id = 'voiceToast';
            toast.style.cssText = `
                position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
                padding: 10px 20px; background: rgba(17, 24, 39, 0.95);
                border: 1px solid rgba(96, 165, 250, 0.3); border-radius: 12px;
                color: #e5e7eb; font-size: 13px; z-index: 1000;
                animation: toastFadeIn 0.3s ease;
                backdrop-filter: blur(8px);
            `;
            toast.textContent = message;
            document.body.appendChild(toast);

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }, 2000);
        },

        // ═══════════════════════════════════════════════
        // PUBLIC INFO
        // ═══════════════════════════════════════════════
        isSupported: function () {
            return isSupported;
        },

        isEnabled: function () {
            return this.enabled;
        },

        isSpeaking: function () {
            return this.speaking;
        }
    };

    window.VoiceEngine = VoiceEngine;

    // Auto-init on DOM ready
    document.addEventListener('DOMContentLoaded', function () {
        VoiceEngine.init();
    });
})();
