/**
 * Cognicare Global Voice System (Vanilla JS)
 * Phase 12: Unified, accessible, client-side Web Speech API controller
 * 
 * Features:
 * - Single global singleton: window.CognicareVoice
 * - Zero external dependencies / 100% browser Web Speech API
 * - Explicit tap/click activation ONLY (strict zero-autoplay policy)
 * - Anti-queue buildup (every utterance cancels ongoing speech first)
 * - Safe iOS/Safari garbage collection retention of active utterance
 * - Dignified, accessible UI (min 44px touch targets, zero emoji, high-contrast states)
 * - Declarative [data-voice-speak] and [data-voice-target] event delegation
 * - Navigation & pagehide auto-cancellation
 */

(function () {
    'use strict';

    // Speaker SVG icon (clean, accessible, professional)
    const SPEAKER_SVG = `<svg class="voice-icon voice-icon-speaker" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>`;

    // Stop SVG icon
    const STOP_SVG = `<svg class="voice-icon voice-icon-stop" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display: none;"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"></rect></svg>`;

    class CognicareVoiceController {
        constructor() {
            this._activeUtterance = null;
            this._activeButton = null;
            this._defaultRate = 0.9;   // Calm, comfortable pacing for elderly users
            this._defaultPitch = 1.0;
            this._defaultLang = 'en-US';

            // Bind lifecycle hooks
            this._initLifecycle();
        }

        /**
         * Checks if the Web Speech API is supported in the current browser
         * @returns {boolean}
         */
        isSupported() {
            return (typeof window !== 'undefined' &&
                    'speechSynthesis' in window &&
                    typeof window.SpeechSynthesisUtterance !== 'undefined');
        }

        /**
         * Checks if speech is currently active
         * @returns {boolean}
         */
        isSpeaking() {
            if (!this.isSupported()) return false;
            return Boolean(window.speechSynthesis.speaking || window.speechSynthesis.pending);
        }

        /**
         * Cancels any active speech and resets active button UI
         */
        stop() {
            if (this.isSupported()) {
                try {
                    window.speechSynthesis.cancel();
                } catch (err) {
                    console.warn('CognicareVoice: error during cancellation', err);
                }
            }
            this._resetActiveButton();
            this._activeUtterance = null;
        }

        /**
         * Speaks the specified text cleanly with cancellation of prior speech.
         * Stores the utterance in `_activeUtterance` to prevent iOS/Safari garbage collection.
         * 
         * @param {string} text - Text to read aloud
         * @param {Object} [options] - Optional configuration
         * @param {number} [options.rate=0.9] - Speed of speech
         * @param {number} [options.pitch=1.0] - Pitch of speech
         * @param {string} [options.lang='en-US'] - Language tag
         * @param {Function} [options.onStart] - Callback on start
         * @param {Function} [options.onEnd] - Callback on completion
         * @param {Function} [options.onError] - Callback on error
         * @returns {boolean} True if speech was queued, false otherwise
         */
        speak(text, options = {}) {
            if (!this.isSupported()) {
                console.info('CognicareVoice: Web Speech API is not supported in this browser.');
                return false;
            }

            const cleanText = (typeof text === 'string') ? text.trim() : '';
            if (!cleanText) {
                return false;
            }

            // Strictly cancel prior speech to prevent audio queue pileups
            this.stop();

            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.rate = (typeof options.rate === 'number') ? options.rate : this._defaultRate;
            utterance.pitch = (typeof options.pitch === 'number') ? options.pitch : this._defaultPitch;
            utterance.lang = options.lang || this._defaultLang;

            // Retain reference on singleton to prevent garbage collection bug in Safari/WebKit
            this._activeUtterance = utterance;

            utterance.onstart = () => {
                if (typeof options.onStart === 'function') {
                    options.onStart();
                }
            };

            utterance.onend = () => {
                this._resetActiveButton();
                this._activeUtterance = null;
                if (typeof options.onEnd === 'function') {
                    options.onEnd();
                }
            };

            utterance.onerror = (event) => {
                // 'canceled' / 'interrupted' errors are expected when user stops or switches
                this._resetActiveButton();
                this._activeUtterance = null;
                if (typeof options.onError === 'function') {
                    options.onError(event);
                }
            };

            try {
                window.speechSynthesis.speak(utterance);
                return true;
            } catch (err) {
                console.error('CognicareVoice: error invoking speak()', err);
                this._resetActiveButton();
                this._activeUtterance = null;
                return false;
            }
        }

        /**
         * Toggles speech on a button:
         * If the button is currently speaking, it stops speech.
         * Otherwise, it speaks the text and sets the button to speaking state.
         * 
         * @param {string} text - Text to read aloud
         * @param {HTMLElement} [button] - Button element triggering speech
         * @param {Object} [options] - Speech options
         * @returns {boolean} True if speaking started, false if stopped
         */
        toggle(text, button = null, options = {}) {
            if (button && this._activeButton === button && this.isSpeaking()) {
                this.stop();
                return false;
            }

            if (button) {
                this._setActiveButton(button);
            }

            const success = this.speak(text, {
                ...options,
                onEnd: () => {
                    this._resetActiveButton();
                    if (options.onEnd) options.onEnd();
                },
                onError: (e) => {
                    this._resetActiveButton();
                    if (options.onError) options.onError(e);
                }
            });

            if (!success && button) {
                this._resetActiveButton();
            }

            return success;
        }

        /**
         * Sets an active button UI to "speaking" state
         * @private
         */
        _setActiveButton(button) {
            if (this._activeButton && this._activeButton !== button) {
                this._resetActiveButton();
            }

            this._activeButton = button;
            button.classList.add('is-speaking');
            button.setAttribute('aria-pressed', 'true');

            // Toggle icon visibility if present
            const speakerIcon = button.querySelector('.voice-icon-speaker');
            const stopIcon = button.querySelector('.voice-icon-stop');
            if (speakerIcon && stopIcon) {
                speakerIcon.style.display = 'none';
                stopIcon.style.display = 'inline-block';
            }

            // Update text label if span is present
            const labelSpan = button.querySelector('.voice-label');
            if (labelSpan) {
                if (!button.dataset.originalLabel) {
                    button.dataset.originalLabel = labelSpan.textContent.trim();
                }
                const stopLabel = button.dataset.voiceStopText || 'Stop';
                labelSpan.textContent = stopLabel;
            }

            // Update aria-label
            const currentAria = button.getAttribute('aria-label');
            if (currentAria) {
                if (!button.dataset.originalAriaLabel) {
                    button.dataset.originalAriaLabel = currentAria;
                }
                button.setAttribute('aria-label', button.dataset.voiceStopAria || 'Stop reading');
            }
        }

        /**
         * Resets the active button UI back to "idle" state
         * @private
         */
        _resetActiveButton() {
            if (!this._activeButton) return;

            const button = this._activeButton;
            button.classList.remove('is-speaking');
            button.setAttribute('aria-pressed', 'false');

            // Restore icons
            const speakerIcon = button.querySelector('.voice-icon-speaker');
            const stopIcon = button.querySelector('.voice-icon-stop');
            if (speakerIcon && stopIcon) {
                speakerIcon.style.display = 'inline-block';
                stopIcon.style.display = 'none';
            }

            // Restore text label
            const labelSpan = button.querySelector('.voice-label');
            if (labelSpan && button.dataset.originalLabel) {
                labelSpan.textContent = button.dataset.originalLabel;
            }

            // Restore aria-label
            if (button.dataset.originalAriaLabel) {
                button.setAttribute('aria-label', button.dataset.originalAriaLabel);
            }

            this._activeButton = null;
        }

        /**
         * Initializes window/document lifecycle event hooks for speech safety
         * @private
         */
        _initLifecycle() {
            if (typeof window === 'undefined') return;

            // Stop speech when user navigates away or unloads the page
            window.addEventListener('pagehide', () => this.stop());
            window.addEventListener('beforeunload', () => this.stop());

            // Stop speech if tab becomes hidden
            if (typeof document !== 'undefined') {
                document.addEventListener('visibilitychange', () => {
                    if (document.hidden) {
                        this.stop();
                    }
                });

                // Attach declarative click listener for [data-voice-speak] buttons
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', () => {
                        this._initDeclarativeButtons();
                    });
                } else {
                    this._initDeclarativeButtons();
                }
            }
        }

        /**
         * Sets up declarative click handler across the document
         * @private
         */
        _initDeclarativeButtons() {
            document.addEventListener('click', (e) => {
                const voiceBtn = e.target.closest('[data-voice-speak], [data-voice-target], .btn-voice, .voice-speak-btn');
                if (!voiceBtn) return;

                // Determine text to speak
                let textToSpeak = '';
                if (voiceBtn.dataset.voiceSpeak) {
                    textToSpeak = voiceBtn.dataset.voiceSpeak;
                } else if (voiceBtn.dataset.voiceTarget) {
                    const targetEl = document.querySelector(voiceBtn.dataset.voiceTarget);
                    if (targetEl) {
                        textToSpeak = targetEl.textContent.trim();
                    }
                } else if (voiceBtn.dataset.speakText) {
                    textToSpeak = voiceBtn.dataset.speakText;
                }

                if (textToSpeak) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.toggle(textToSpeak, voiceBtn);
                }
            });

            // If Web Speech API is not supported, hide or visually indicate fallback
            if (!this.isSupported()) {
                const voiceElements = document.querySelectorAll('.btn-voice, .voice-speak-btn, [data-voice-speak]');
                voiceElements.forEach(el => {
                    el.style.display = 'none';
                    el.setAttribute('aria-hidden', 'true');
                });
            }
        }

        /**
         * Utility to generate clean speaker SVG markup
         * @returns {string}
         */
        getSpeakerSvg() {
            return SPEAKER_SVG;
        }

        /**
         * Utility to generate clean stop SVG markup
         * @returns {string}
         */
        getStopSvg() {
            return STOP_SVG;
        }
    }

    // Expose global singleton instance
    window.CognicareVoice = new CognicareVoiceController();

})();
