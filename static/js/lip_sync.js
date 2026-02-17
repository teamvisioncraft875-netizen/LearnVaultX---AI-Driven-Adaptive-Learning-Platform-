/**
 * lip_sync.js — Enhanced Lip Sync Controller for AI Tutor Avatar
 * Provides three sync modes:
 *   1. Sine-wave simulation (fallback)
 *   2. Text-driven phoneme analysis
 *   3. SpeechSynthesis word-boundary sync (when VoiceEngine active)
 */

(function () {
    'use strict';

    // ═══════════════════════════════════════════════
    // PHONEME MAP — English letters to mouth openness
    // ═══════════════════════════════════════════════
    const VISEME_MAP = {
        // Wide open vowels
        'a': 0.85, 'e': 0.7, 'i': 0.6, 'o': 0.75, 'u': 0.65,
        // Bilabials (lips pressed together)
        'b': 0.05, 'p': 0.05, 'm': 0.05,
        // Labiodentals
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
        // Space / punctuation → brief close
        ' ': 0.08, '.': 0.0, ',': 0.05, '!': 0.0, '?': 0.0,
        '-': 0.05, ':': 0.05, ';': 0.05
    };

    // Common digraphs with special mouth shapes
    const DIGRAPH_MAP = {
        'th': 0.2, 'sh': 0.15, 'ch': 0.3,
        'oo': 0.55, 'ee': 0.45, 'ou': 0.6,
        'ai': 0.7, 'ea': 0.65, 'oa': 0.7,
        'ng': 0.25, 'ph': 0.2, 'wh': 0.45
    };

    // ═══════════════════════════════════════════════
    // LIP SYNC CONTROLLER
    // ═══════════════════════════════════════════════
    const LipSync = {
        isActive: false,
        startTime: 0,
        duration: 0,
        interval: null,
        text: '',
        visemeSequence: [],    // Pre-computed [{value, time}]
        currentVisemeIdx: 0,

        // ─── SINE WAVE MODE (fallback) ───────────
        /**
         * Start lip sync animation for a given text.
         * Uses enhanced phoneme analysis for more realistic mouth movement.
         * @param {string} text - The text being "spoken"
         * @param {number} [wordsPerMinute=180] - Speed of speech
         */
        start: function (text, wordsPerMinute) {
            if (!window.AvatarController || !AvatarController.isReady()) return;

            this.stop(); // Clear any previous session

            this.text = text || '';
            this.isActive = true;
            this.startTime = Date.now();

            const wpm = wordsPerMinute || 180;
            const wordCount = text.split(/\s+/).length;
            this.duration = (wordCount / wpm) * 60 * 1000; // ms
            this.duration = Math.max(this.duration, 1500);  // Minimum 1.5s
            this.duration = Math.min(this.duration, 15000); // Max 15s

            // Pre-compute the viseme sequence for the entire text
            this.visemeSequence = this._textToVisemeTimeline(text, this.duration);
            this.currentVisemeIdx = 0;

            AvatarController.startTalking();

            // Update mouth at 30fps using pre-computed timeline
            this.interval = setInterval(() => {
                if (!this.isActive) {
                    this._cleanup();
                    return;
                }

                const elapsed = Date.now() - this.startTime;
                if (elapsed > this.duration) {
                    this.stop();
                    return;
                }

                // Find the current viseme value from the timeline
                const mouthOpen = this._getVisemeAtTime(elapsed);

                // Apply envelope for natural fade in/out
                const progress = elapsed / this.duration;
                const envelope = Math.sin(progress * Math.PI);
                AvatarController.setMouthOpen(mouthOpen * envelope);
            }, 33); // ~30fps

            this._setStatus('talking', 'Speaking...');
        },

        /**
         * Stop lip sync animation.
         */
        stop: function () {
            this.isActive = false;
            this._cleanup();

            if (window.AvatarController && AvatarController.isReady()) {
                AvatarController.stopTalking();
            }

            this._setStatus('idle', 'Ready to help');
        },

        // ─── WORD BOUNDARY MODE (for VoiceEngine TTS) ──
        /**
         * Animate a single word's phonemes.
         * Called by VoiceEngine on each SpeechSynthesis word boundary event.
         * @param {string} word - The current word being spoken
         * @param {number} [charDurationMs=80] - Duration per character in ms
         */
        animateWord: function (word, charDurationMs) {
            if (!window.AvatarController || !AvatarController.isReady()) return;
            if (!word) return;

            const charDur = charDurationMs || 80;
            const visemes = this._wordToVisemes(word.toLowerCase());

            let i = 0;
            const playNext = () => {
                if (i >= visemes.length) return;
                AvatarController.setMouthOpen(visemes[i]);
                i++;
                if (i < visemes.length) {
                    setTimeout(playNext, charDur);
                }
            };

            playNext();
        },

        // ─── AUDIO PLAYBACK MODE ────────────────
        /**
         * Play using actual audio (for future TTS integration).
         * @param {string} audioUrl - URL to audio file
         * @param {string} [visemeUrl] - URL to viseme timing data
         */
        playAudio: function (audioUrl, visemeUrl) {
            if (!audioUrl) return;

            const audio = new Audio(audioUrl);
            audio.addEventListener('play', () => {
                this.isActive = true;
                AvatarController.startTalking();
                this._setStatus('talking', 'Speaking...');
            });
            audio.addEventListener('ended', () => {
                this.stop();
            });
            audio.addEventListener('error', () => {
                this.stop();
            });

            // If viseme data available, use precise timing
            if (visemeUrl) {
                fetch(visemeUrl)
                    .then(r => r.json())
                    .then(visemes => {
                        this._playWithVisemes(audio, visemes);
                    })
                    .catch(() => {
                        audio.play().catch(() => { });
                        this.start('', 180);
                    });
            } else {
                audio.play().catch(() => { });
                // Fallback: sine-wave driven by audio current time
                this.interval = setInterval(() => {
                    if (audio.paused || audio.ended) {
                        this.stop();
                        return;
                    }
                    const t = audio.currentTime * 1000;
                    const mouth = (Math.sin(t * 0.015) * 0.5 + 0.5) * 0.7;
                    AvatarController.setMouthOpen(mouth);
                }, 33);
            }
        },

        // ═══════════════════════════════════════════════
        // INTERNAL — PHONEME ANALYSIS
        // ═══════════════════════════════════════════════

        /**
         * Convert a word to an array of viseme values (0-1).
         * Handles digraphs for more accurate mouth shapes.
         */
        _wordToVisemes: function (word) {
            const result = [];
            const chars = word.split('');
            let i = 0;

            while (i < chars.length) {
                // Check for digraphs first (2-char combinations)
                if (i < chars.length - 1) {
                    const digraph = chars[i] + chars[i + 1];
                    if (DIGRAPH_MAP[digraph] !== undefined) {
                        result.push(DIGRAPH_MAP[digraph]);
                        i += 2;
                        continue;
                    }
                }

                // Single character
                const c = chars[i];
                result.push(VISEME_MAP[c] !== undefined ? VISEME_MAP[c] : 0.3);
                i++;
            }

            return result;
        },

        /**
         * Convert full text to a timed viseme timeline.
         * Each entry has {time: ms, value: 0-1}.
         */
        _textToVisemeTimeline: function (text, totalDurationMs) {
            const timeline = [];
            const cleanText = text.toLowerCase().replace(/[^a-z0-9\s.,!?;:-]/g, '');
            const chars = cleanText.split('');

            if (chars.length === 0) return [{ time: 0, value: 0 }];

            const msPerChar = totalDurationMs / chars.length;
            let currentTime = 0;
            let i = 0;

            while (i < chars.length) {
                let value = 0.3;

                // Check for digraphs
                if (i < chars.length - 1) {
                    const digraph = chars[i] + chars[i + 1];
                    if (DIGRAPH_MAP[digraph] !== undefined) {
                        value = DIGRAPH_MAP[digraph];
                        timeline.push({ time: currentTime, value: value });
                        currentTime += msPerChar * 2;
                        i += 2;
                        continue;
                    }
                }

                // Single character lookup
                value = VISEME_MAP[chars[i]] !== undefined ? VISEME_MAP[chars[i]] : 0.3;
                timeline.push({ time: currentTime, value: value });
                currentTime += msPerChar;
                i++;
            }

            // Add final close
            timeline.push({ time: totalDurationMs, value: 0 });

            return timeline;
        },

        /**
         * Look up the interpolated viseme value at a given time.
         */
        _getVisemeAtTime: function (timeMs) {
            const tl = this.visemeSequence;
            if (tl.length === 0) return 0;

            // Find the surrounding keyframes
            let lo = 0;
            let hi = tl.length - 1;

            // Advance the cached index
            while (this.currentVisemeIdx < tl.length - 1 &&
                tl[this.currentVisemeIdx + 1].time <= timeMs) {
                this.currentVisemeIdx++;
            }

            lo = this.currentVisemeIdx;
            hi = Math.min(lo + 1, tl.length - 1);

            if (lo === hi) return tl[lo].value;

            // Lerp between keyframes
            const loEntry = tl[lo];
            const hiEntry = tl[hi];
            const t = (timeMs - loEntry.time) / (hiEntry.time - loEntry.time);
            return loEntry.value + (hiEntry.value - loEntry.value) * t;
        },

        _playWithVisemes: function (audio, visemes) {
            // visemes format: [{time: ms, value: 0-1}, ...]
            audio.play().catch(() => { });
            let vIdx = 0;
            this.interval = setInterval(() => {
                if (audio.paused || audio.ended) {
                    this.stop();
                    return;
                }
                const currentMs = audio.currentTime * 1000;
                while (vIdx < visemes.length - 1 && visemes[vIdx + 1].time <= currentMs) {
                    vIdx++;
                }
                if (vIdx < visemes.length) {
                    AvatarController.setMouthOpen(visemes[vIdx].value);
                }
            }, 16); // 60fps for viseme precision
        },

        _cleanup: function () {
            if (this.interval) {
                clearInterval(this.interval);
                this.interval = null;
            }
            this.visemeSequence = [];
            this.currentVisemeIdx = 0;
        },

        _setStatus: function (state, text) {
            const dot = document.getElementById('avatarStatusDot');
            const statusText = document.getElementById('avatarStatusText');
            if (dot) {
                dot.className = 'status-dot ' + state;
            }
            if (statusText) {
                statusText.textContent = text;
            }
        }
    };

    window.LipSyncController = LipSync;
})();
