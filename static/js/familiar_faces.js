/**
 * Cognicare Familiar Faces Engine (Vanilla JS)
 * Phase 8: Facial Recognition, Relational & Episodic Memory
 * 
 * Features:
 * - High contrast, touch-accessible person selection
 * - Central photo inspection with clear aspect-fill framing
 * - Silent telemetry recording (latency ms)
 * - Server-side validation via CSRF-protected JSON endpoint
 * - Gentle, warm, non-stigmatizing feedback screen
 */

(function () {
    'use strict';

    // Helper to extract Django CSRF token from cookies
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
        return; // Not on active Familiar Faces game page
    }

    const sessionId = metaElem.dataset.sessionId;
    let currentRound = parseInt(metaElem.dataset.currentRound, 10) || 1;
    const totalRounds = parseInt(metaElem.dataset.totalRounds, 10) || 3;
    const submitUrl = metaElem.dataset.submitUrl;
    const completeUrl = metaElem.dataset.completeUrl;
    const resultsUrl = metaElem.dataset.resultsUrl;

    // DOM elements
    const roundIndicator = document.getElementById('round-indicator');
    const recognitionStage = document.getElementById('recognition-stage');
    const feedbackStage = document.getElementById('feedback-stage');
    const targetPhoto = document.getElementById('target-photo');
    const choicesContainer = document.getElementById('choices-container');
    const btnConfirmChoice = document.getElementById('btn-confirm-choice');
    const feedbackHeading = document.getElementById('feedback-message-heading');
    const feedbackText = document.getElementById('feedback-text');
    const feedbackIconContainer = document.getElementById('feedback-icon-container');
    const feedbackPhoto = document.getElementById('feedback-photo');
    const feedbackPersonName = document.getElementById('feedback-person-name');
    const feedbackPersonRelationship = document.getElementById('feedback-person-relationship');
    const btnNextAction = document.getElementById('btn-next-action');
    const questionHeading = document.getElementById('question-heading');
    const btnSpeakPrompt = document.getElementById('btn-speak-prompt');
    const btnSpeakFeedback = document.getElementById('btn-speak-feedback');

    // State variables
    let selectedPersonId = null;
    let roundStartTime = Date.now();
    let isSubmitting = false;
    let hasNextRound = false;
    let nextRoundDataCache = null;

    // Helper to get text description of prompt and choices for voice read-aloud
    function getPromptText() {
        const heading = questionHeading ? questionHeading.textContent.trim() : 'Who is this familiar person?';
        const choiceEls = choicesContainer ? choicesContainer.querySelectorAll('.choice-name') : [];
        const names = [];
        choiceEls.forEach(el => names.push(el.textContent.trim()));
        let text = heading + '. Look at the picture and choose the person\'s name and relationship.';
        if (names.length > 0) {
            text += ' The choices are: ' + names.join(', ') + '.';
        }
        return text;
    }

    // Voice Read-Aloud Listeners
    if (btnSpeakPrompt) {
        btnSpeakPrompt.addEventListener('click', function () {
            if (window.CognicareVoice) {
                window.CognicareVoice.toggle(getPromptText(), btnSpeakPrompt);
            }
        });
    }

    if (btnSpeakFeedback) {
        btnSpeakFeedback.addEventListener('click', function () {
            if (window.CognicareVoice) {
                const heading = feedbackHeading ? feedbackHeading.textContent.trim() : '';
                const text = feedbackText ? feedbackText.textContent.trim() : '';
                const name = feedbackPersonName ? feedbackPersonName.textContent.trim() : '';
                const rel = feedbackPersonRelationship ? feedbackPersonRelationship.textContent.trim() : '';
                const personInfo = name ? (' That is ' + name + (rel ? ', ' + rel : '') + '.') : '';
                const msg = (heading ? heading + '.' : '') + personInfo + ' ' + text;
                window.CognicareVoice.toggle(msg.trim(), btnSpeakFeedback);
            }
        });
    }

    /**
     * Attaches click handlers to choice buttons
     */
    function attachChoiceListeners() {
        if (!choicesContainer) return;
        const buttons = choicesContainer.querySelectorAll('.familiar-choice-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', function (e) {
                if (e.target.closest('.choice-voice-btn')) {
                    e.stopPropagation();
                    return;
                }
                const personId = this.dataset.personId;
                selectChoice(personId);
            });
        });
    }

    /**
     * Updates UI when a choice is selected
     */
    function selectChoice(personId) {
        selectedPersonId = personId;
        const buttons = choicesContainer.querySelectorAll('.familiar-choice-btn');
        buttons.forEach(btn => {
            const isSelected = (btn.dataset.personId === personId);
            btn.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
            const dot = btn.querySelector('.radio-inner-dot');
            const indicator = btn.querySelector('.choice-radio-indicator');

            if (isSelected) {
                btn.style.borderColor = 'var(--primary-main)';
                btn.style.borderWidth = '2.5px';
                btn.style.backgroundColor = 'var(--color-teal-50)';
                btn.style.boxShadow = '0 4px 12px rgba(13, 148, 136, 0.15)';
                if (dot) dot.style.display = 'block';
                if (indicator) indicator.style.borderColor = 'var(--primary-main)';
            } else {
                btn.style.borderColor = 'var(--border-color)';
                btn.style.borderWidth = '2px';
                btn.style.backgroundColor = 'var(--bg-surface)';
                btn.style.boxShadow = 'none';
                if (dot) dot.style.display = 'none';
                if (indicator) indicator.style.borderColor = 'var(--border-color)';
            }
        });

        if (btnConfirmChoice) {
            btnConfirmChoice.disabled = false;
        }
    }

    /**
     * Renders choices dynamically for new rounds
     */
    function renderChoices(choices) {
        if (!choicesContainer) return;
        choicesContainer.innerHTML = '';
        selectedPersonId = null;
        if (btnConfirmChoice) {
            btnConfirmChoice.disabled = true;
        }

        choices.forEach(choice => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'familiar-choice-btn';
            btn.dataset.personId = choice.id;
            btn.setAttribute('aria-pressed', 'false');
            btn.style.cssText = 'min-height: 68px; padding: var(--space-4) var(--space-5); border: 2px solid var(--border-color); border-radius: var(--radius-md); background-color: var(--bg-surface); display: flex; justify-content: space-between; align-items: center; text-align: left; cursor: pointer; transition: all 0.15s ease; gap: var(--space-3);';

            const speakText = choice.name + (choice.relationship ? (', ' + choice.relationship) : '');
            const speakerSvg = window.CognicareVoice ? window.CognicareVoice.getSpeakerSvg() : '';
            const stopSvg = window.CognicareVoice ? window.CognicareVoice.getStopSvg() : '';

            btn.innerHTML = `
                <div style="flex-grow: 1;">
                    <div class="choice-name" style="font-size: 1.2rem; font-weight: 700; color: var(--text-primary); line-height: 1.3;">
                        ${escapeHtml(choice.name)}
                    </div>
                    ${choice.relationship ? `
                        <div class="choice-relationship" style="font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px;">
                            ${escapeHtml(choice.relationship)}
                        </div>
                    ` : ''}
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span role="button" tabindex="0" class="choice-voice-btn" data-voice-speak="${escapeHtml(speakText)}" aria-label="Listen to ${escapeHtml(choice.name)}" title="Listen to ${escapeHtml(choice.name)}">
                        ${speakerSvg}
                        ${stopSvg}
                    </span>
                    <div class="choice-radio-indicator" style="width: 24px; height: 24px; border-radius: 50%; border: 2px solid var(--border-color); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        <div class="radio-inner-dot" style="width: 12px; height: 12px; border-radius: 50%; background-color: var(--primary-main); display: none;"></div>
                    </div>
                </div>
            `;

            btn.addEventListener('click', function (e) {
                if (e.target.closest('.choice-voice-btn')) {
                    e.stopPropagation();
                    return;
                }
                selectChoice(choice.id);
            });

            choicesContainer.appendChild(btn);
        });
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Submits the chosen answer to the server
     */
    if (btnConfirmChoice) {
        btnConfirmChoice.addEventListener('click', function () {
            if (!selectedPersonId || isSubmitting) return;
            if (window.CognicareVoice) window.CognicareVoice.stop();

            isSubmitting = true;
            btnConfirmChoice.disabled = true;
            btnConfirmChoice.textContent = 'Saving...';

            const responseTimeMs = Math.max(0, Date.now() - roundStartTime);
            const csrfToken = getCookie('csrftoken') || (document.querySelector('[name=csrfmiddlewaretoken]') ? document.querySelector('[name=csrfmiddlewaretoken]').value : '');

            const payload = {
                round_number: currentRound,
                selected_ids: [selectedPersonId],
                response_time_ms: responseTimeMs,
                hints_used: 0
            };

            fetch(submitUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (!res.ok) throw new Error('Submission error');
                return res.json();
            })
            .then(data => {
                isSubmitting = false;
                btnConfirmChoice.disabled = false;
                btnConfirmChoice.textContent = 'Confirm My Answer →';

                const evalData = data.evaluation;
                hasNextRound = data.has_next_round;
                nextRoundDataCache = data.next_round_data;

                // Configure feedback stage
                if (feedbackHeading) {
                    feedbackHeading.textContent = evalData.is_correct ? 'Wonderful!' : 'Thank You!';
                }
                if (feedbackText) {
                    feedbackText.textContent = evalData.feedback_message || 'Thank you for connecting with this memory.';
                }
                if (feedbackIconContainer) {
                    if (evalData.is_correct) {
                        feedbackIconContainer.innerHTML = '✓';
                        feedbackIconContainer.style.backgroundColor = 'var(--color-teal-100)';
                        feedbackIconContainer.style.color = 'var(--color-teal-800)';
                    } else {
                        feedbackIconContainer.innerHTML = '♥';
                        feedbackIconContainer.style.backgroundColor = 'var(--color-teal-50)';
                        feedbackIconContainer.style.color = 'var(--primary-main)';
                    }
                }

                if (feedbackPersonName) {
                    feedbackPersonName.textContent = evalData.target_name || '';
                }
                if (feedbackPersonRelationship) {
                    feedbackPersonRelationship.textContent = evalData.target_relationship || '';
                }
                if (feedbackPhoto && targetPhoto) {
                    feedbackPhoto.src = targetPhoto.src;
                }

                // Switch to feedback view
                recognitionStage.style.display = 'none';
                feedbackStage.style.display = 'block';

                if (hasNextRound) {
                    btnNextAction.textContent = 'Next Round →';
                } else {
                    btnNextAction.textContent = 'View Summary →';
                }

                window.scrollTo({ top: 0, behavior: 'smooth' });
            })
            .catch(err => {
                console.error('Submission error:', err);
                isSubmitting = false;
                btnConfirmChoice.disabled = false;
                btnConfirmChoice.textContent = 'Confirm My Answer →';
                alert('We had trouble saving your answer. Please check your connection and try again.');
            });
        });
    }

    /**
     * Advances to the next round or finalizes the session
     */
    if (btnNextAction) {
        btnNextAction.addEventListener('click', function () {
            if (window.CognicareVoice) window.CognicareVoice.stop();
            if (hasNextRound && nextRoundDataCache) {
                currentRound = nextRoundDataCache.round_number;
                roundIndicator.textContent = 'Round ' + currentRound + ' of ' + totalRounds;

                if (targetPhoto && nextRoundDataCache.target_photo_url) {
                    targetPhoto.src = nextRoundDataCache.target_photo_url;
                }

                renderChoices(nextRoundDataCache.choices);

                roundStartTime = Date.now();
                feedbackStage.style.display = 'none';
                recognitionStage.style.display = 'block';

                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                // Finalize session on server
                const csrfToken = getCookie('csrftoken') || (document.querySelector('[name=csrfmiddlewaretoken]') ? document.querySelector('[name=csrfmiddlewaretoken]').value : '');

                btnNextAction.disabled = true;
                btnNextAction.textContent = 'Finalizing...';

                fetch(completeUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(res => {
                    if (!res.ok) throw new Error('Failed to complete session');
                    return res.json();
                })
                .then(data => {
                    window.location.href = data.redirect_url || resultsUrl;
                })
                .catch(err => {
                    console.error('Session completion error:', err);
                    window.location.href = resultsUrl;
                });
            }
        });
    }

    // Attach initial click listeners
    attachChoiceListeners();
})();
