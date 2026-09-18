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

            // Auto-cleanup on navigation and tab visibility
            if (typeof window !== 'undefined') {
                window.addEventListener('beforeunload', () => this.abort());
                window.addEventListener('pagehide', () => this.abort());
            }
            if (typeof document !== 'undefined') {
                document.addEventListener('visibilitychange', () => {
                    if (document.hidden) {
                        this.abort();
                    }
                });
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
         * Starts listening and targets the specified input element or callback.
         * NEVER called automatically; only invoked through explicit user interaction.
         * 
         * Signatures:
         * - start(targetInput, button, customLang)
         * - start(callbackFn, button, customLang)
         * - start({ target, button, lang, onResult, onStart, onEnd, onError })
         */
        start(targetInput, button = null, customLang = null) {
            let options = {};
            let target = targetInput;

            if (targetInput && typeof targetInput === 'object' && typeof targetInput.nodeType !== 'number' && typeof targetInput.addEventListener !== 'function') {
                options = targetInput;
                target = options.target || options.onResult || null;
                button = options.button || button;
                customLang = options.lang || customLang;
            }

            if (!this.isSupported()) {
                const msgs = this.getMessages();
                if (typeof options.onError === 'function') {
                    options.onError('unsupported', msgs.unsupported);
                }
                if (button) {
                    this._displayMessage(button, msgs.unsupported, 'warning');
                }
                return;
            }

            // Stop any existing session
            this.abort();

            if (!target && typeof options.onResult !== 'function') {
                console.warn('CognicareSpeech: target input or onResult callback not found.');
                return;
            }

            const targetLang = customLang || this.resolveLanguage();
            const msgs = this.getMessages();

            try {
                const recognition = new this._SpeechRecognitionClass();
                recognition.continuous = false;
                recognition.interimResults = true;
                recognition.maxAlternatives = 1;
                recognition.lang = targetLang;

                this._recognition = recognition;
                this._activeTarget = target;
                this._activeButton = button;
                this._activeOptions = options;
                this._activeTargetLang = targetLang;

                let lastTranscript = '';
                let hasInserted = false;

                recognition.onaudiostart = () => {
                    console.log('[CognicareSpeech] onaudiostart: Audio hardware capture began');
                };

                recognition.onspeechstart = () => {
                    console.log('[CognicareSpeech] onspeechstart: Speech sound detected by browser');
                };

                recognition.onspeechend = () => {
                    console.log('[CognicareSpeech] onspeechend: Speech sound ended');
                };

                recognition.onaudioend = () => {
                    console.log('[CognicareSpeech] onaudioend: Audio hardware capture stopped');
                };

                recognition.onstart = () => {
                    console.log('[CognicareSpeech] onstart: Speech recognition active, lang =', recognition.lang);
                    this._isListening = true;
                    if (button) {
                        this._updateButtonUI(button, true);
                    }
                    if (typeof options.onStart === 'function') {
                        options.onStart();
                    }
                };

                recognition.onresult = (event) => {
                    const resultsLen = event.results ? event.results.length : 0;
                    console.log('[CognicareSpeech] onresult: event.results.length =', resultsLen);
                    if (!event.results || resultsLen === 0) return;

                    let fullTranscript = '';
                    let isFinal = false;

                    for (let i = 0; i < event.results.length; i++) {
                        const res = event.results[i];
                        if (res && res[0] && res[0].transcript) {
                            const piece = res[0].transcript;
                            console.log(`[CognicareSpeech] result[${i}]: "${piece}", isFinal = ${res.isFinal}`);
                            fullTranscript += (fullTranscript && !fullTranscript.endsWith(' ') && !piece.startsWith(' ') ? ' ' : '') + piece;
                            if (res.isFinal) {
                                isFinal = true;
                            }
                        }
                    }

                    const cleanTranscript = fullTranscript.trim();
                    console.log('[CognicareSpeech] final aggregated transcript:', cleanTranscript, 'isFinal:', isFinal);
                    if (cleanTranscript) {
                        lastTranscript = cleanTranscript;
                        const isTargetFn = typeof target === 'function';
                        console.log('[CognicareSpeech] invoking target callback, isFunction =', isTargetFn);
                        if (isTargetFn) {
                            target(cleanTranscript, isFinal);
                        } else if (target && typeof target.nodeType === 'number') {
                            if (isFinal) {
                                this._insertText(target, cleanTranscript);
                                hasInserted = true;
                            }
                        }
                        if (typeof options.onResult === 'function' && !isTargetFn) {
                            options.onResult(cleanTranscript, isFinal);
                        }
                    }
                };

                recognition.onerror = (event) => {
                    console.warn('[CognicareSpeech] onerror: event.error =', event.error);
                    let userMsg = msgs.errorOccurred;
                    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                        userMsg = msgs.permissionDenied;
                    } else if (event.error === 'language-not-supported') {
                        userMsg = targetLang === 'as-IN' ? msgs.langUnsupported : msgs.errorOccurred;
                    } else if (event.error === 'no-speech') {
                        userMsg = msgs.noSpeech || 'No speech was detected';
                    }

                    if (userMsg && button) {
                        this._displayMessage(button, userMsg, 'info');
                    }

                    if (typeof options.onError === 'function') {
                        options.onError(event.error, userMsg);
                    }

                    this.abort();
                };

                recognition.onend = () => {
                    console.log('[CognicareSpeech] onend: recognition finished, lastTranscript =', lastTranscript);
                    // Fallback text insertion for DOM inputs if isFinal was never flagged before end
                    if (target && typeof target.nodeType === 'number' && !hasInserted && lastTranscript) {
                        this._insertText(target, lastTranscript);
                        hasInserted = true;
                    }

                    if (typeof options.onEnd === 'function') {
                        options.onEnd(lastTranscript);
                    }
                    this.abort();
                };

                recognition.start();
            } catch (err) {
                console.warn('CognicareSpeech: failed to start recognition', err);
                this.abort();
                if (button) {
                    this._displayMessage(button, msgs.errorOccurred, 'info');
                }
                if (typeof options.onError === 'function') {
                    options.onError('exception', msgs.errorOccurred);
                }
            }
        }

        /**
         * Cancels active recognition session immediately without waiting for results.
         * Used for tab backgrounding, unload, and cleanup.
         */
        abort() {
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
                this._activeButton = null;
            }
            this._isListening = false;
            this._activeTarget = null;
            this._activeOptions = null;
        }

        /**
         * Stops active listening session gracefully, allowing pending audio to finalize.
         */
        stop() {
            if (this._recognition && this._isListening) {
                try {
                    this._recognition.stop();
                } catch (e) {
                    this.abort();
                }
            } else {
                this.abort();
            }
        }

        /**
         * Toggles speech recognition for a specific target and trigger button.
         */
        toggle(targetInput, button = null, customLang = null) {
            if (this._isListening && (this._activeButton === button || (!button && !this._activeButton))) {
                this.stop();
                return false;
            } else {
                this.start(targetInput, button, customLang);
                return true;
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
            const speakText = button.getAttribute('data-txt-speak') || msgs.speak;
            const listeningText = button.getAttribute('data-txt-listening') || msgs.listening;

            if (isListening) {
                button.setAttribute('aria-pressed', 'true');
                button.classList.add('is-listening');
                button.style.borderColor = '#dc2626';
                button.style.backgroundColor = '#fef2f2';
                button.style.color = '#dc2626';
                button.innerHTML = `${MIC_LISTENING_SVG} <span class="speech-label">${listeningText}</span>`;
            } else {
                button.setAttribute('aria-pressed', 'false');
                button.classList.remove('is-listening');
                button.style.borderColor = '';
                button.style.backgroundColor = '';
                button.style.color = '';
                button.innerHTML = `${MIC_SVG} <span class="speech-label">${speakText}</span>`;
            }
        }

        /**
         * Displays a polite temporary banner near the button for feedback.
         */
        _displayMessage(button, message, type) {
            if (!button || !message) return;
            const container = button.parentElement || button;
            let msgBox = container.querySelector('.speech-feedback-message');
            if (!msgBox) {
                msgBox = document.createElement('div');
                msgBox.className = 'speech-feedback-message';
                msgBox.style.cssText = 'font-size: 0.85rem; margin-top: 6px; padding: 6px 10px; border-radius: 6px; line-height: 1.4;';
                container.appendChild(msgBox);
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
            msgBox.setAttribute('aria-live', 'polite');

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

            const isSupp = this.isSupported();
            const msgs = this.getMessages();

            button.setAttribute('type', 'button');
            button.setAttribute('aria-label', button.getAttribute('aria-label') || msgs.micAriaLabel);
            button.setAttribute('aria-pressed', 'false');

            if (!isSupp) {
                button.setAttribute('data-speech-supported', 'false');
                button.classList.add('speech-unsupported');
            }

            // Render initial button state
            this._updateButtonUI(button, false);

            button.addEventListener('click', (e) => {
                e.preventDefault();
                if (!this.isSupported()) {
                    this._displayMessage(button, msgs.unsupported, 'warning');
                    return;
                }
                this.toggle(input, button, lang);
            });
        }

        /**
         * Automatically binds all elements with data-speech-target attribute.
         * Usage: <button type="button" class="btn-speech" data-speech-target="id_title">...</button>
         */
        autoBind() {
            const isSupp = this.isSupported();
            const msgs = this.getMessages();
            const buttons = document.querySelectorAll('[data-speech-target]');
            buttons.forEach((btn) => {
                const targetId = btn.getAttribute('data-speech-target');
                const targetInput = document.getElementById(targetId);
                if (btn && targetInput) {
                    btn.setAttribute('type', 'button');
                    btn.setAttribute('aria-label', btn.getAttribute('aria-label') || msgs.micAriaLabel);
                    btn.setAttribute('aria-pressed', 'false');

                    if (!isSupp) {
                        btn.setAttribute('data-speech-supported', 'false');
                        btn.classList.add('speech-unsupported');
                    }

                    this._updateButtonUI(btn, false);

                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        if (!this.isSupported()) {
                            this._displayMessage(btn, msgs.unsupported, 'warning');
                            return;
                        }
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
