/**
 * Cognicare Global Speech-to-Text System (Vanilla JS)
 * Phase 13C-2: Browser-Native Web Speech Recognition Controller
 * 
 * Features:
 * - Single global singleton: window.CognicareSpeech
 * - Zero external dependencies / 100% browser Web Speech API
 * - Explicit click activation ONLY (strict zero-autoplay / zero-autolisten policy)
 * - Safe audio privacy (no audio uploaded, no audio recorded, no server transmission)
 * - Dignified, accessible UI (min 44px touch targets, zero emoji, high-contrast states)
 * - Multi-lingual aware: resolves 'en-US' for English and 'as-IN' for Assamese
 * - Graceful fallback with clear notification if language or API is unsupported
 * - Non-destructive text insertion (appends text cleanly, preserves existing input)
 */

(function () {
    'use strict';

    // SVG icons for microphone states
    const MIC_SVG = `<svg class="speech-icon speech-icon-mic" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="22"></line></svg>`;
    const MIC_LISTENING_SVG = `<svg class="speech-icon speech-icon-listening" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="6" fill="#dc2626"></circle><path d="M19 10v2a7 7 0 0 1-14 0v-2" fill="none"></path><line x1="12" y1="19" x2="12" y2="22" fill="none"></line></svg>`;

    class CognicareSpeechController {
        constructor() {
            this._recognition = null;
            this._isListening = false;
            this._activeButton = null;
            this._activeInput = null;
            this._activeConfig = null;
            this._bindings = [];

            // Detect speech recognition constructor
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
            this._SpeechRecognitionClass = SpeechRecognition;

            // Auto-cleanup on navigation
            if (typeof window !== 'undefined') {
                window.addEventListener('beforeunload', () => this.stop());
                window.addEventListener('pagehide', () => this.stop());
            }
        }

        /**
         * Checks if the Web Speech Recognition API is supported in this browser.
         * @returns {boolean}
         */
        isSupported() {
            return Boolean(this._SpeechRecognitionClass);
        }

        /**
         * Returns whether speech recognition is actively listening.
         * @returns {boolean}
         */
        isListening() {
            return this._isListening;
        }

        /**
         * Resolves the BCP 47 language tag based on the document's language.
         * @returns {string} 'en-US' or 'as-IN'
         */
        resolveLanguage() {
            const docLang = (document.documentElement && document.documentElement.lang) || 'en';
            if (docLang.toLowerCase().startsWith('as')) {
                return 'as-IN';
            }
            return 'en-US';
        }

        /**
         * Returns user-facing status text localized for English and Assamese.
         */
        getMessages() {
            const isAssamese = this.resolveLanguage() === 'as-IN';
            if (isAssamese) {
                return {
                    speak: 'কওক',
                    listening: 'শুনি থকা হৈছে...',
                    stop: 'বন্ধ কৰক',
                    unsupported: 'আপোনাৰ ব্ৰাউজাৰত কণ্ঠ চিনাক্তকৰণ সুবিধা সমৰ্থিত নহয়। অনুগ্ৰহ কৰি কীবৰ্ড ব্যৱহাৰ কৰক।',
                    langUnsupported: 'আপোনাৰ ব্ৰাউজাৰত অসমীয়া কণ্ঠ চিনাক্তকৰণ সমৰ্থিত নহয়। অনুগ্ৰহ কৰি লিখি প্ৰৱেশ কৰক।',
                    permissionDenied: 'মাইক্ৰ’ফোনৰ অনুমতি প্ৰত্যাখ্যান কৰা হৈছে। অনুগ্ৰহ কৰি ব্ৰাউজাৰ ছেটিংছ পৰীক্ষা কৰক।',
                    errorOccurred: 'কণ্ঠ চিনাক্তকৰণত সমস্যা হৈছে। অনুগ্ৰহ কৰি পুনৰ চেষ্টা কৰক বা কীবৰ্ড ব্যৱহাৰ কৰক।',
                    micAriaLabel: 'কণ্ঠৰ দ্বাৰা লিখক'
                };
            }
            return {
                speak: 'Speak',
                listening: 'Listening...',
                stop: 'Stop',
                unsupported: 'Speech recognition is not supported in your browser. Please use standard typing.',
                langUnsupported: 'Assamese voice recognition is not supported on this browser/device. Please type instead.',
                permissionDenied: 'Microphone access was denied. Please allow microphone permissions in browser settings.',
                errorOccurred: 'Speech recognition encountered an issue. Please try again or type manually.',
                micAriaLabel: 'Speak into field'
            };
        }

        /**
         * Starts listening and targets the specified input element.
         * NEVER called automatically; only invoked through explicit user interaction.
         */
        start(targetInput, button, customLang) {
            if (!this.isSupported()) {
                const msgs = this.getMessages();
                this._displayMessage(button, msgs.unsupported, 'warning');
                return;
            }

            // Stop any existing session
            this.stop();

            if (!targetInput) {
                console.warn('CognicareSpeech: target input not found.');
                return;
            }

            const targetLang = customLang || this.resolveLanguage();
            const msgs = this.getMessages();

            try {
                const recognition = new this._SpeechRecognitionClass();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.maxAlternatives = 1;
                recognition.lang = targetLang;

                this._recognition = recognition;
                this._activeInput = targetInput;
                this._activeButton = button;
                this._activeTargetLang = targetLang;

                recognition.onstart = () => {
                    this._isListening = true;
                    this._updateButtonUI(button, true);
                };

                recognition.onresult = (event) => {
                    if (event.results && event.results.length > 0) {
                        const transcript = event.results[0][0].transcript;
                        if (transcript && transcript.trim()) {
                            this._insertText(targetInput, transcript.trim());
                        }
                    }
                };

                recognition.onerror = (event) => {
                    console.info('CognicareSpeech error:', event.error);
                    let userMsg = msgs.errorOccurred;
                    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                        userMsg = msgs.permissionDenied;
                    } else if (event.error === 'language-not-supported') {
                        userMsg = targetLang === 'as-IN' ? msgs.langUnsupported : msgs.errorOccurred;
                    } else if (event.error === 'no-speech') {
                        // User remained silent; no need for error banner
                        userMsg = null;
                    }
                    if (userMsg) {
                        this._displayMessage(button, userMsg, 'info');
                    }
                    this.stop();
                };

                recognition.onend = () => {
                    this.stop();
                };

                recognition.start();
            } catch (err) {
                console.warn('CognicareSpeech: failed to start recognition', err);
                this.stop();
                this._displayMessage(button, msgs.errorOccurred, 'info');
            }
        }

        /**
         * Stops active listening session and restores UI.
         */
        stop() {
            if (this._recognition) {
                try {
                    this._recognition.abort();
                } catch (e) {
                    // Ignore abort errors
                }
                this._recognition = null;
            }
            if (this._activeButton) {
                this._updateButtonUI(this._activeButton, false);
            }
            this._isListening = false;
            this._activeButton = null;
            this._activeInput = null;
        }

        /**
         * Toggles speech recognition for a specific target and trigger button.
         */
        toggle(targetInput, button, customLang) {
            if (this._isListening && this._activeButton === button) {
                this.stop();
            } else {
                this.start(targetInput, button, customLang);
            }
        }

        /**
         * Non-destructively inserts text into an input or textarea element.
         * Appends with clean whitespace or inserts at selection range.
         */
        _insertText(inputEl, text) {
            if (!inputEl) return;

            const existingVal = inputEl.value || '';
            const startPos = inputEl.selectionStart;
            const endPos = inputEl.selectionEnd;

            if (typeof startPos === 'number' && typeof endPos === 'number' && startPos >= 0) {
                // Insert at cursor position
                const before = existingVal.substring(0, startPos);
                const after = existingVal.substring(endPos);
                const prefix = (before.length > 0 && !before.endsWith(' ') && !before.endsWith('\n')) ? ' ' : '';
                const suffix = (after.length > 0 && !after.startsWith(' ') && !after.startsWith('\n')) ? ' ' : '';
                const newVal = before + prefix + text + suffix + after;
                inputEl.value = newVal;

                // Move cursor to after inserted text
                const newPos = before.length + prefix.length + text.length + suffix.length;
                inputEl.setSelectionRange(newPos, newPos);
            } else {
                // Append at end
                const prefix = (existingVal.length > 0 && !existingVal.endsWith(' ') && !existingVal.endsWith('\n')) ? ' ' : '';
                inputEl.value = existingVal + prefix + text;
            }

            // Trigger change/input events for any listeners or validation
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
            inputEl.dispatchEvent(new Event('change', { bubbles: true }));
            inputEl.focus();
        }

        /**
         * Updates button visual and ARIA states.
         */
        _updateButtonUI(button, isListening) {
            if (!button) return;
            const msgs = this.getMessages();

            if (isListening) {
                button.setAttribute('aria-pressed', 'true');
                button.classList.add('is-listening');
                button.style.borderColor = '#dc2626';
                button.style.backgroundColor = '#fef2f2';
                button.style.color = '#dc2626';
                button.innerHTML = `${MIC_LISTENING_SVG} <span class="speech-label">${msgs.listening}</span>`;
            } else {
                button.setAttribute('aria-pressed', 'false');
                button.classList.remove('is-listening');
                button.style.borderColor = '';
                button.style.backgroundColor = '';
                button.style.color = '';
                button.innerHTML = `${MIC_SVG} <span class="speech-label">${msgs.speak}</span>`;
            }
        }

        /**
         * Displays a polite temporary banner near the button for feedback.
         */
        _displayMessage(button, message, type) {
            if (!button || !message) return;
            let msgBox = button.parentElement.querySelector('.speech-feedback-message');
            if (!msgBox) {
                msgBox = document.createElement('div');
                msgBox.className = 'speech-feedback-message';
                msgBox.style.cssText = 'font-size: 0.85rem; margin-top: 6px; padding: 6px 10px; border-radius: 6px; line-height: 1.4;';
                button.parentElement.appendChild(msgBox);
            }

            if (type === 'warning' || type === 'info') {
                msgBox.style.backgroundColor = '#fef3c7';
                msgBox.style.color = '#92400e';
                msgBox.style.border = '1px solid #fde68a';
            } else {
                msgBox.style.backgroundColor = '#f3f4f6';
                msgBox.style.color = '#374151';
                msgBox.style.border = '1px solid #e5e7eb';
            }

            msgBox.textContent = message;
            msgBox.setAttribute('role', 'status');

            // Fade out after 5 seconds
            setTimeout(() => {
                if (msgBox && msgBox.parentElement) {
                    msgBox.remove();
                }
            }, 5000);
        }

        /**
         * Binds a microphone button to an input field.
         * Configuration: { buttonId, inputId, lang }
         */
        bind({ buttonId, inputId, lang }) {
            const button = document.getElementById(buttonId);
            const input = document.getElementById(inputId);

            if (!button || !input) return;

            button.setAttribute('type', 'button');
            button.setAttribute('aria-label', this.getMessages().micAriaLabel);
            button.setAttribute('aria-pressed', 'false');

            // Render initial button state
            this._updateButtonUI(button, false);

            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggle(input, button, lang);
            });
        }

        /**
         * Automatically binds all elements with data-speech-target attribute.
         * Usage: <button type="button" class="btn-speech" data-speech-target="id_title">...</button>
         */
        autoBind() {
            const buttons = document.querySelectorAll('[data-speech-target]');
            buttons.forEach((btn) => {
                const targetId = btn.getAttribute('data-speech-target');
                const targetInput = document.getElementById(targetId);
                if (btn && targetInput) {
                    btn.setAttribute('type', 'button');
                    btn.setAttribute('aria-label', this.getMessages().micAriaLabel);
                    btn.setAttribute('aria-pressed', 'false');
                    this._updateButtonUI(btn, false);

                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        this.toggle(targetInput, btn);
                    });
                }
            });
        }
    }

    // Initialize singleton on window
    window.CognicareSpeech = new CognicareSpeechController();

    // Auto-bind on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.CognicareSpeech.autoBind());
    } else {
        window.CognicareSpeech.autoBind();
    }
})();
