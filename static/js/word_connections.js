/**
 * Cognicare Word Connections Engine (Vanilla JS)
 * Phase 10: Semantic Memory & Contextual Association Cognitive Activity
 * 
 * Features:
 * - Touch-accessible large word cards with clear visual highlights
 * - Tremor-tolerant: changing selection has ZERO penalty before confirmation
 * - Silent latency recording (no visible ticking clock or countdown pressure)
 * - Server-side validation via CSRF-protected JSON endpoint
 * - Dignified, calm, supportive feedback screen explaining connections
 * - Web Speech API synthesis hooks for future-ready accessibility
 */

(function () {
    'use strict';

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const metaElem = document.getElementById('game-metadata');
    if (!metaElem) {
        return; // Not on active Word Connections game page
    }

    const txt = (k, fallback) => (metaElem && metaElem.dataset && metaElem.dataset[k]) || fallback;

    const sessionId = metaElem.dataset.sessionId;
    let currentRound = parseInt(metaElem.dataset.currentRound, 10) || 1;
    const totalRounds = parseInt(metaElem.dataset.totalRounds, 10) || 3;
    const submitUrl = metaElem.dataset.submitUrl;
    const completeUrl = metaElem.dataset.completeUrl;
    const resultsUrl = metaElem.dataset.resultsUrl;

    // DOM elements
    const roundIndicator = document.getElementById('round-indicator');
    const associationStage = document.getElementById('association-stage');
    const feedbackStage = document.getElementById('feedback-stage');

    // Concept elements
    const questionHeading = document.getElementById('question-heading');
    const conceptTheme = document.getElementById('concept-theme');
    const conceptTitle = document.getElementById('concept-title');
    const conceptClue = document.getElementById('concept-clue');
    const btnSpeakPrompt = document.getElementById('btn-speak-prompt');
    const wordChipGrid = document.getElementById('word-chip-grid');
    const btnConfirmSelection = document.getElementById('btn-confirm-selection');

    // Feedback elements
    const feedbackIconContainer = document.getElementById('feedback-icon-container');
    const feedbackHeading = document.getElementById('feedback-message-heading');
    const feedbackText = document.getElementById('feedback-text');
    const btnSpeakFeedback = document.getElementById('btn-speak-feedback');
    const feedbackTheme = document.getElementById('feedback-theme');
    const feedbackConceptTitle = document.getElementById('feedback-concept-title');
    const feedbackTargetWord = document.getElementById('feedback-target-word');
    const btnNextAction = document.getElementById('btn-next-action');

    // State variables
    let selectedWordId = null;
    let roundStartTime = Date.now();
    let isSubmitting = false;
    let nextRoundDataCache = null;
    let currentRoundData = null;

    // Read initial round data from JSON script if present
    const initialRoundScript = document.getElementById('initial-round-data');
    if (initialRoundScript) {
        try {
            currentRoundData = JSON.parse(initialRoundScript.textContent);
        } catch (e) {
            currentRoundData = null;
        }
    }

    /**
     * Attaches click handlers to word cards and speech buttons
     */
    function attachCardListeners() {
        if (!wordChipGrid) return;
        const cards = wordChipGrid.querySelectorAll('.word-card');
        cards.forEach(card => {
            card.addEventListener('click', function (e) {
                // If user clicked the audio icon specifically, play audio instead of changing selection
                if (e.target.closest('.word-card-audio-btn')) {
                    e.stopPropagation();
                    const audioBtn = e.target.closest('.word-card-audio-btn');
                    const speakText = card.dataset.wordText;
                    if (window.CognicareVoice && speakText) {
                        window.CognicareVoice.toggle(speakText, audioBtn);
                    }
                    return;
                }
                const wordId = this.dataset.wordId;
                selectWordCard(wordId);
            });
        });
    }

    /**
     * Updates UI when a word card is selected (penalty-free)
     */
    function selectWordCard(wordId) {
        selectedWordId = wordId;
        const cards = wordChipGrid.querySelectorAll('.word-card');
        cards.forEach(card => {
            const isSelected = (card.dataset.wordId === wordId);
            card.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
            if (isSelected) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });

        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = false;
        }
    }

    // Voice Read-Aloud Listeners
    if (btnSpeakPrompt) {
        btnSpeakPrompt.addEventListener('click', function () {
            const title = conceptTitle ? conceptTitle.textContent.trim() : '';
            const clue = conceptClue ? conceptClue.textContent.trim() : '';
            const fullText = (title ? title + '. ' : '') + clue;
            if (window.CognicareVoice) {
                window.CognicareVoice.toggle(fullText, btnSpeakPrompt);
            }
        });
    }

    if (btnSpeakFeedback) {
        btnSpeakFeedback.addEventListener('click', function () {
            const heading = feedbackHeading ? feedbackHeading.textContent.trim() : '';
            const msg = feedbackText ? feedbackText.textContent.trim() : '';
            const word = feedbackTargetWord ? feedbackTargetWord.textContent.trim() : '';
            const fullText = (heading ? heading + '. ' : '') + (word ? 'The connection was ' + word + '. ' : '') + msg;
            if (window.CognicareVoice) {
                window.CognicareVoice.toggle(fullText.trim(), btnSpeakFeedback);
            }
        });
    }

    /**
     * Submits selected word to server for authoritative validation
     */
    async function submitSelection() {
        if (!selectedWordId || isSubmitting) return;
        if (window.CognicareVoice) window.CognicareVoice.stop();

        isSubmitting = true;
        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = true;
            btnConfirmSelection.textContent = txt('txtSaving', 'Saving...');
        }

        const responseTimeMs = Math.max(0, Date.now() - roundStartTime);
        const payload = {
            round_number: currentRound,
            selected_ids: [selectedWordId],
            response_time_ms: responseTimeMs,
            hints_used: 0,
        };

        try {
            const response = await fetch(submitUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json();
            if (!data.success) {
                alert(data.error || txt('txtErrorSaving', 'There was an issue recording your answer.'));
                isSubmitting = false;
                if (btnConfirmSelection) {
                    btnConfirmSelection.disabled = false;
                    btnConfirmSelection.textContent = txt('txtConfirm', 'Confirm My Selection →');
                }
                return;
            }

            displayFeedback(data);
        } catch (error) {
            console.error('Submission error:', error);
            alert(txt('txtErrorSaving', 'A network error occurred. Please try confirming again.'));
            isSubmitting = false;
            if (btnConfirmSelection) {
                btnConfirmSelection.disabled = false;
                btnConfirmSelection.textContent = txt('txtConfirm', 'Confirm My Selection →');
            }
        }
    }

    /**
     * Displays gentle feedback screen
     */
    function displayFeedback(data) {
        const evaluation = data.evaluation;
        const isCorrect = evaluation.is_correct;

        if (isCorrect) {
            feedbackIconContainer.innerHTML = '✓';
            feedbackIconContainer.style.backgroundColor = 'var(--color-teal-100)';
            feedbackIconContainer.style.color = 'var(--color-teal-800)';
            feedbackHeading.textContent = txt('txtWonderful', 'Wonderful!');
        } else {
            feedbackIconContainer.innerHTML = '★';
            feedbackIconContainer.style.backgroundColor = 'var(--color-terracotta-50)';
            feedbackIconContainer.style.color = 'var(--color-terracotta-700)';
            feedbackHeading.textContent = txt('txtGoodEffort', 'Good Effort!');
        }

        feedbackText.textContent = evaluation.feedback_message;

        if (currentRoundData) {
            feedbackTheme.textContent = currentRoundData.theme;
            feedbackConceptTitle.textContent = currentRoundData.concept;
            feedbackTargetWord.textContent = evaluation.target_word || currentRoundData.target_word;
        }

        if (data.has_next_round) {
            btnNextAction.textContent = txt('txtNextRound', 'Continue to Next Round →');
            nextRoundDataCache = data.next_round_data;
        } else {
            btnNextAction.textContent = txt('txtViewSummary', 'View Results →');
            nextRoundDataCache = null;
        }

        associationStage.style.display = 'none';
        feedbackStage.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    /**
     * Renders a new round dynamically
     */
    function startNextRound(roundData) {
        currentRound = roundData.round_number;
        currentRoundData = roundData;

        if (roundIndicator) {
            roundIndicator.textContent = `${txt('txtRoundPrefix', 'Round')} ${currentRound} ${txt('txtOf', 'of')} ${totalRounds}`;
        }

        // Update concept card
        if (questionHeading) questionHeading.textContent = roundData.prompt;
        if (conceptTheme) conceptTheme.textContent = roundData.theme;
        if (conceptTitle) conceptTitle.textContent = roundData.concept;
        if (conceptClue) conceptClue.textContent = '"' + roundData.contextual_clue + '"';

        // Render choices grid
        if (wordChipGrid) {
            wordChipGrid.innerHTML = '';
            const speakerSvg = window.CognicareVoice ? window.CognicareVoice.getSpeakerSvg() : '';
            const stopSvg = window.CognicareVoice ? window.CognicareVoice.getStopSvg() : '';

            roundData.choices.forEach(choice => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'word-card';
                button.dataset.wordId = choice.id;
                button.dataset.wordText = choice.word;
                button.setAttribute('aria-label', choice.word);
                button.setAttribute('aria-pressed', 'false');

                button.innerHTML = `
                    <div class="word-card-check" aria-hidden="true">✓</div>
                    <span class="word-card-text">${choice.word}</span>
                    <span role="button"
                          tabindex="0"
                          class="word-card-audio-btn choice-voice-btn"
                          data-voice-speak="${choice.word}"
                          aria-label="Listen to ${choice.word}"
                          title="Listen to ${choice.word}">
                        ${speakerSvg}
                        ${stopSvg}
                    </span>
                `;

                button.addEventListener('click', function (e) {
                    if (e.target.closest('.word-card-audio-btn')) {
                        e.stopPropagation();
                        const audioEl = e.target.closest('.word-card-audio-btn');
                        if (window.CognicareVoice) {
                            window.CognicareVoice.toggle(choice.word, audioEl);
                        }
                        return;
                    }
                    selectWordCard(choice.id);
                });

                wordChipGrid.appendChild(button);
            });
        }

        selectedWordId = null;
        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = true;
        }

        feedbackStage.style.display = 'none';
        associationStage.style.display = 'block';

        roundStartTime = Date.now();
        isSubmitting = false;
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    /**
     * Completes the session on final round
     */
    async function completeSession() {
        try {
            const response = await fetch(completeUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({}),
            });
            const data = await response.json();
            if (data.success && data.redirect_url) {
                window.location.href = data.redirect_url;
            } else {
                window.location.href = resultsUrl;
            }
        } catch (e) {
            window.location.href = resultsUrl;
        }
    }

    // Attach button listeners
    if (btnConfirmSelection) {
        btnConfirmSelection.addEventListener('click', submitSelection);
    }

    if (btnNextAction) {
        btnNextAction.addEventListener('click', function () {
            if (window.CognicareVoice) window.CognicareVoice.stop();
            if (nextRoundDataCache) {
                const nextData = nextRoundDataCache;
                nextRoundDataCache = null;
                startNextRound(nextData);
            } else {
                btnNextAction.textContent = txt('txtFinalizing', 'Finalizing...');
                btnNextAction.disabled = true;
                completeSession();
            }
        });
    }

    // Initialize initial card listeners
    attachCardListeners();
})();
