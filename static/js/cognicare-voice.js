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
            this._activeTargetElement = null;
            this._highlightSupported = (
                typeof CSS !== 'undefined' &&
                typeof CSS.highlights !== 'undefined' &&
                typeof Highlight !== 'undefined'
            );
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
            return Boolean(this._activeUtterance || window.speechSynthesis.speaking || window.speechSynthesis.pending);
        }

        /**
         * Cancels any active speech, clears text highlights, and resets active button UI
         */
        stop() {
            this._clearHighlight();
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
         * Resolves current UI language ('as-IN' or 'en-US') based on document lang
         * @returns {string}
         */
        resolveLanguage() {
            if (typeof document !== 'undefined' && document.documentElement && document.documentElement.lang) {
                const docLang = document.documentElement.lang.toLowerCase();
                if (docLang.startsWith('as')) {
                    return 'as-IN';
                }
            }
            return 'en-US';
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
         * @param {HTMLElement|null} [options.targetElement] - Visible DOM element to highlight
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

            // Strictly cancel prior speech and previous highlights to prevent audio pileups
            this.stop();

            let targetElement = options.targetElement || null;
            const triggerButton = options.button || this._activeButton || null;
            if (!targetElement && triggerButton && triggerButton.dataset) {
                const sel = triggerButton.dataset.voiceTarget || triggerButton.dataset.target;
                if (sel) {
                    try {
                        targetElement = document.querySelector(sel);
                    } catch (e) {
                        targetElement = null;
                    }
                }
            }
            this._activeTargetElement = targetElement;
            if (this._activeTargetElement) {
                this._activeTargetElement.classList.add('is-reading-target');
            }

            const utterance = new SpeechSynthesisUtterance(cleanText);
            utterance.rate = (typeof options.rate === 'number') ? options.rate : this._defaultRate;
            utterance.pitch = (typeof options.pitch === 'number') ? options.pitch : this._defaultPitch;
            utterance.lang = options.lang || this.resolveLanguage() || this._defaultLang;

            // Retain reference on singleton to prevent garbage collection bug in Safari/WebKit
            this._activeUtterance = utterance;

            utterance.onstart = () => {
                if (this._activeTargetElement && !this._activeTargetElement.classList.contains('is-reading-target')) {
                    this._activeTargetElement.classList.add('is-reading-target');
                }
                if (typeof options.onStart === 'function') {
                    options.onStart();
                }
            };

            utterance.onboundary = (event) => {
                this._handleBoundary(event, targetElement, cleanText);
            };

            utterance.onend = () => {
                this._clearHighlight();
                this._resetActiveButton();
                this._activeUtterance = null;
                if (typeof options.onEnd === 'function') {
                    options.onEnd();
                }
            };

            utterance.onerror = (event) => {
                // 'canceled' / 'interrupted' errors are expected when user stops or switches
                this._clearHighlight();
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
                this._clearHighlight();
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

            const success = this.speak(text, {
                ...options,
                button: button,
                onEnd: () => {
                    this._resetActiveButton();
                    if (options.onEnd) options.onEnd();
                },
                onError: (e) => {
                    this._resetActiveButton();
                    if (options.onError) options.onError(e);
                }
            });

            if (success && button) {
                this._setActiveButton(button);
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
         * Handles speech synthesis onboundary event to highlight the spoken word.
         * Defensively validates target and character indices without throwing exceptions.
         * 
         * @private
         * @param {SpeechSynthesisEvent} event
         * @param {HTMLElement|null} targetElement
         * @param {string} fullText
         */
        _handleBoundary(event, targetElement, fullText) {
            if (!targetElement || !fullText) return;
            if (!event || typeof event.charIndex !== 'number' || event.charIndex < 0) return;

            const charIndex = event.charIndex;
            if (charIndex >= fullText.length) return;

            const charLength = (typeof event.charLength === 'number' && event.charLength > 0) ? event.charLength : null;
            const wordEnd = this._calculateWordEnd(fullText, charIndex, charLength);

            if (wordEnd <= charIndex) return;

            const range = this._createRangeForOffsets(targetElement, charIndex, wordEnd, fullText);
            if (range) {
                this._applyHighlight(range, targetElement);
            }
        }

        /**
         * Calculates end of word starting from charIndex, preserving Unicode graphemes
         * and respecting Assamese characters, punctuation, and delimiters.
         * 
         * @private
         * @param {string} text
         * @param {number} charIndex
         * @param {number|null} charLength
         * @returns {number}
         */
        _calculateWordEnd(text, charIndex, charLength) {
            if (typeof charLength === 'number' && charLength > 0) {
                return Math.min(text.length, charIndex + charLength);
            }

            // Punctuation and whitespace delimiters (including Assamese daari U+0964 and double daari U+0965)
            const delimiterRegex = /[\s\.,!?;:।॥—–"'\(\)\[\]{}]/;
            let endIndex = charIndex;

            while (endIndex < text.length && !delimiterRegex.test(text[endIndex])) {
                endIndex++;
            }

            // If charIndex pointed to a delimiter itself, advance by at least 1
            if (endIndex === charIndex && endIndex < text.length) {
                endIndex++;
            }

            return endIndex;
        }

        /**
         * Safely creates a DOM Range within targetElement corresponding to [startChar, endChar]
         * in fullText without modifying DOM innerHTML or textContent.
         * 
         * @private
         * @param {HTMLElement} targetElement
         * @param {number} startChar
         * @param {number} endChar
         * @param {string} fullText
         * @returns {Range|null}
         */
        _createRangeForOffsets(targetElement, startChar, endChar, fullText) {
            if (!targetElement || typeof startChar !== 'number' || typeof endChar !== 'number') {
                return null;
            }

            const domText = targetElement.textContent || '';
            if (!domText) return null;

            // Locate where fullText begins in domText
            let textOffset = domText.indexOf(fullText);
            if (textOffset === -1) {
                const trimmedDom = domText.trim();
                const trimmedOffset = domText.indexOf(trimmedDom);
                textOffset = trimmedOffset >= 0 ? trimmedOffset : 0;
            }

            const absStart = textOffset + startChar;
            const absEnd = textOffset + endChar;

            if (absStart >= domText.length) return null;

            let walker;
            try {
                walker = document.createTreeWalker(
                    targetElement,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
            } catch (e) {
                return null;
            }

            let currentNode = walker.nextNode();
            let accumulated = 0;
            let startNode = null;
            let startNodeOffset = 0;
            let endNode = null;
            let endNodeOffset = 0;

            while (currentNode) {
                const len = currentNode.nodeValue ? currentNode.nodeValue.length : 0;
                const nextAccumulated = accumulated + len;

                if (!startNode && absStart >= accumulated && absStart < nextAccumulated) {
                    startNode = currentNode;
                    startNodeOffset = absStart - accumulated;
                }

                if (absEnd > accumulated && absEnd <= nextAccumulated) {
                    endNode = currentNode;
                    endNodeOffset = absEnd - accumulated;
                    break;
                }

                accumulated = nextAccumulated;
                currentNode = walker.nextNode();
            }

            // If absEnd reached or exceeded the last text node boundary
            if (startNode && !endNode && absEnd >= accumulated) {
                endNode = currentNode || startNode;
                endNodeOffset = endNode.nodeValue ? endNode.nodeValue.length : 0;
            }

            if (startNode && endNode) {
                try {
                    const range = document.createRange();
                    range.setStart(startNode, Math.min(startNodeOffset, startNode.nodeValue.length));
                    range.setEnd(endNode, Math.min(endNodeOffset, endNode.nodeValue.length));
                    return range;
                } catch (err) {
                    console.warn('CognicareVoice: failed creating Range', err);
                    return null;
                }
            }

            return null;
        }

        /**
         * Applies the highlight to the given range using the CSS Custom Highlight API.
         * Falls back gracefully if unsupported.
         * 
         * @private
         * @param {Range} range
         * @param {HTMLElement} targetElement
         */
        _applyHighlight(range, targetElement) {
            if (!range) return;

            if (this._highlightSupported) {
                try {
                    const highlight = new Highlight(range);
                    CSS.highlights.set('tts-word', highlight);
                } catch (e) {
                    // Fail silently, speech continues
                }
            }

            if (targetElement && !targetElement.classList.contains('is-reading-target')) {
                targetElement.classList.add('is-reading-target');
            }
        }

        /**
         * Completely clears active CSS highlights and container reading indicators.
         * @private
         */
        _clearHighlight() {
            if (this._highlightSupported) {
                try {
                    if (CSS.highlights.has('tts-word')) {
                        CSS.highlights.delete('tts-word');
                    }
                } catch (e) {
                    // Ignore deletion error
                }
            }

            if (this._activeTargetElement) {
                try {
                    this._activeTargetElement.classList.remove('is-reading-target');
                } catch (e) {
                    // Ignore classList error
                }
                this._activeTargetElement = null;
            }
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

                // Determine text to speak and optional target element
                let textToSpeak = '';
                let targetElement = null;

                if (voiceBtn.dataset.voiceTarget) {
                    targetElement = document.querySelector(voiceBtn.dataset.voiceTarget);
                    if (targetElement) {
                        textToSpeak = targetElement.textContent.trim();
                    }
                }

                // If no voiceTarget or text wasn't extracted from it, check voiceSpeak
                if (!textToSpeak && voiceBtn.dataset.voiceSpeak) {
                    textToSpeak = voiceBtn.dataset.voiceSpeak;
                    if (!targetElement && voiceBtn.dataset.target) {
                        targetElement = document.querySelector(voiceBtn.dataset.target);
                    }
                } else if (!textToSpeak && voiceBtn.dataset.speakText) {
                    textToSpeak = voiceBtn.dataset.speakText;
                }

                if (textToSpeak) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.toggle(textToSpeak, voiceBtn, { targetElement });
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
