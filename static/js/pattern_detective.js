/**
 * Cognicare Pattern Detective Engine (Vanilla JS)
 * Phase 11: Visual Pattern Recognition & Abstract Reasoning Cognitive Activity
 * 
 * Features:
 * - Touch-accessible large vector pattern cards and choices
 * - Tremor-tolerant: changing selection has ZERO penalty before confirmation
 * - Silent latency recording (no visible ticking clock or countdown pressure)
 * - Server-side validation via CSRF-protected JSON endpoint
 * - Dignified, calm, encouraging feedback screen explaining pattern harmony
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
        return; // Not on active Pattern Detective game page
    }

    const sessionId = metaElem.dataset.sessionId;
    let currentRound = parseInt(metaElem.dataset.currentRound, 10) || 1;
    const totalRounds = parseInt(metaElem.dataset.totalRounds, 10) || 3;
    const submitUrl = metaElem.dataset.submitUrl;
    const completeUrl = metaElem.dataset.completeUrl;
    const resultsUrl = metaElem.dataset.resultsUrl;

    // DOM elements
    const roundIndicator = document.getElementById('round-indicator');
    const patternStage = document.getElementById('pattern-stage');
    const feedbackStage = document.getElementById('feedback-stage');

    // Pattern display elements
    const puzzleHeading = document.getElementById('puzzle-heading');
    const patternTitle = document.getElementById('pattern-title');
    const btnSpeakPrompt = document.getElementById('btn-speak-prompt');
    const patternVisualContainer = document.getElementById('pattern-visual-container');
    const choiceTilesGrid = document.getElementById('choice-tiles-grid');
    const btnConfirmSelection = document.getElementById('btn-confirm-selection');

    // Feedback elements
    const feedbackIconContainer = document.getElementById('feedback-icon-container');
    const feedbackHeading = document.getElementById('feedback-message-heading');
    const feedbackText = document.getElementById('feedback-text');
    const btnSpeakFeedback = document.getElementById('btn-speak-feedback');
    const feedbackTargetSvg = document.getElementById('feedback-target-svg');
    const feedbackTargetName = document.getElementById('feedback-target-name');
    const btnNextAction = document.getElementById('btn-next-action');

    // State variables
    let selectedTileId = null;
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
     * Attaches click handlers to choice tiles and speech buttons
     */
    function attachTileListeners() {
        if (!choiceTilesGrid) return;
        const tiles = choiceTilesGrid.querySelectorAll('.pattern-choice-tile');
        tiles.forEach(tile => {
            tile.addEventListener('click', function (e) {
                // If user clicked the small audio button, speak name without changing selection
                if (e.target.closest('.pattern-tile-audio-btn')) {
                    e.stopPropagation();
                    const speakText = tile.dataset.tileName;
                    speakTextSnippet(speakText);
                    return;
                }
                const tileId = this.dataset.tileId;
                selectTile(tileId);
            });
        });
    }

    /**
     * Updates UI when a choice tile is selected (penalty-free)
     */
    function selectTile(tileId) {
        selectedTileId = tileId;
        const tiles = choiceTilesGrid.querySelectorAll('.pattern-choice-tile');
        tiles.forEach(tile => {
            const isSelected = (tile.dataset.tileId === tileId);
            tile.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
            if (isSelected) {
                tile.classList.add('selected');
            } else {
                tile.classList.remove('selected');
            }
        });

        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = false;
        }
    }

    /**
     * Web Speech API synthesis hook
     */
    function speakTextSnippet(text) {
        if (!('speechSynthesis' in window) || !text) return;
        try {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
        } catch (e) {
            console.warn('Speech synthesis error:', e);
        }
    }

    /**
     * Speaks the current pattern title, prompt, and layout
     */
    function speakCurrentPrompt() {
        if (!currentRoundData) return;
        const promptText = (currentRoundData.prompt || '') + '. ' + (currentRoundData.title || '');
        speakTextSnippet(promptText);
    }

    /**
     * Renders a round into the DOM
     */
    function renderRound(data) {
        currentRoundData = data;
        selectedTileId = null;
        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = true;
        }

        if (roundIndicator) {
            roundIndicator.textContent = `Round ${data.round_number} of ${data.total_rounds || totalRounds}`;
        }
        if (puzzleHeading) {
            puzzleHeading.textContent = data.prompt;
        }
        if (patternTitle) {
            patternTitle.textContent = data.title;
        }

        // Render pattern visual container
        if (patternVisualContainer) {
            if (data.layout === 'matrix_2x2') {
                let html = '<div class="pattern-matrix-grid" role="group" aria-label="Pattern matrix 2 by 2">';
                (data.matrix || []).forEach(row => {
                    (row || []).forEach(item => {
                        if (item.is_missing) {
                            html += `
                                <div class="pattern-tile-display pattern-tile-missing" role="img" aria-label="Missing tile marked with question mark">
                                    <div class="missing-badge" aria-hidden="true">?</div>
                                    <span class="missing-label">Missing Tile</span>
                                </div>
                            `;
                        } else {
                            html += `
                                <div class="pattern-tile-display" role="img" aria-label="${item.name}">
                                    <div class="pattern-tile-svg">${item.svg}</div>
                                    <span class="pattern-tile-label">${item.name}</span>
                                </div>
                            `;
                        }
                    });
                });
                html += '</div>';
                patternVisualContainer.innerHTML = html;
            } else {
                let html = '<div class="pattern-sequence-strip" role="group" aria-label="Pattern sequence strip">';
                (data.sequence || []).forEach(item => {
                    if (item.is_missing) {
                        html += `
                            <div class="pattern-tile-display pattern-tile-missing" role="img" aria-label="Missing tile marked with question mark">
                                <div class="missing-badge" aria-hidden="true">?</div>
                                <span class="missing-label">Missing Tile</span>
                            </div>
                        `;
                    } else {
                        html += `
                            <div class="pattern-tile-display" role="img" aria-label="${item.name}">
                                <div class="pattern-tile-svg">${item.svg}</div>
                                <span class="pattern-tile-label">${item.name}</span>
                            </div>
                        `;
                    }
                });
                html += '</div>';
                patternVisualContainer.innerHTML = html;
            }
        }

        // Render choice tiles
        if (choiceTilesGrid) {
            let choiceHtml = '';
            (data.choices || []).forEach(choice => {
                choiceHtml += `
                    <button type="button"
                            class="pattern-choice-tile"
                            data-tile-id="${choice.id}"
                            data-tile-name="${choice.name}"
                            aria-label="${choice.name}"
                            aria-pressed="false">
                        <div class="pattern-choice-check" aria-hidden="true">✓</div>
                        <div class="pattern-choice-svg">${choice.svg}</div>
                        <span class="pattern-choice-name">${choice.name}</span>
                        <button type="button"
                                class="pattern-tile-audio-btn"
                                data-speak-text="${choice.name}"
                                aria-label="Listen to ${choice.name}"
                                title="Listen to ${choice.name}"
                                tabindex="-1">
                            <span aria-hidden="true">🔊</span>
                        </button>
                    </button>
                `;
            });
            choiceTilesGrid.innerHTML = choiceHtml;
            attachTileListeners();
        }

        // Show pattern stage, hide feedback stage
        if (patternStage) patternStage.style.display = 'block';
        if (feedbackStage) feedbackStage.style.display = 'none';

        roundStartTime = Date.now();
        isSubmitting = false;
    }

    /**
     * Submits player selection to server endpoint
     */
    function submitSelection() {
        if (!selectedTileId || isSubmitting) return;
        isSubmitting = true;

        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = true;
            btnConfirmSelection.textContent = 'Checking...';
        }

        const latencyMs = Math.max(0, Date.now() - roundStartTime);
        const payload = {
            round_number: currentRound,
            selected_ids: [selectedTileId],
            response_time_ms: latencyMs,
            hints_used: 0
        };

        const csrfToken = getCookie('csrftoken');

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
            if (!res.ok) {
                throw new Error(`Server returned status ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            if (!data.success) {
                alert(data.error || 'A problem occurred while recording your selection.');
                isSubmitting = false;
                if (btnConfirmSelection) {
                    btnConfirmSelection.disabled = false;
                    btnConfirmSelection.textContent = 'Confirm My Selection';
                }
                return;
            }

            // Cache next round data if returned
            nextRoundDataCache = data.next_round_data;

            // Transition to gentle feedback stage
            showFeedbackStage(data);
        })
        .catch(err => {
            console.error('Submission error:', err);
            alert('A network communication issue occurred. Please try confirming again.');
            isSubmitting = false;
            if (btnConfirmSelection) {
                btnConfirmSelection.disabled = false;
                btnConfirmSelection.textContent = 'Confirm My Selection';
            }
        });
    }

    /**
     * Displays gentle encouraging feedback stage
     */
    function showFeedbackStage(data) {
        const evalData = data.evaluation;
        const isCorrect = evalData.is_correct;

        if (patternStage) patternStage.style.display = 'none';
        if (feedbackStage) feedbackStage.style.display = 'block';

        if (feedbackIconContainer) {
            if (isCorrect) {
                feedbackIconContainer.textContent = '🌱';
                feedbackIconContainer.style.backgroundColor = 'var(--color-teal-100)';
                feedbackIconContainer.style.color = 'var(--color-teal-900)';
            } else {
                feedbackIconContainer.textContent = '🌿';
                feedbackIconContainer.style.backgroundColor = 'var(--color-slate-100)';
                feedbackIconContainer.style.color = 'var(--color-slate-800)';
            }
        }

        if (feedbackHeading) {
            feedbackHeading.textContent = isCorrect ? 'Harmonious Match!' : 'Thoughtful Effort!';
        }

        if (feedbackText) {
            feedbackText.textContent = evalData.feedback_message;
        }

        if (feedbackTargetName) {
            feedbackTargetName.textContent = evalData.target_name || '';
        }

        if (feedbackTargetSvg && currentRoundData) {
            const targetTile = (currentRoundData.choices || []).find(c => c.name === evalData.target_name) || currentRoundData.target_tile;
            if (targetTile && targetTile.svg) {
                feedbackTargetSvg.innerHTML = targetTile.svg;
            }
        }

        if (btnNextAction) {
            if (data.has_next_round) {
                btnNextAction.textContent = `Continue to Round ${data.next_round_number} →`;
                btnNextAction.dataset.action = 'next_round';
                btnNextAction.dataset.nextRoundNumber = data.next_round_number;
            } else {
                btnNextAction.textContent = 'View Activity Results →';
                btnNextAction.dataset.action = 'complete_session';
            }
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    /**
     * Handles Next Action button click
     */
    function handleNextAction() {
        const action = btnNextAction.dataset.action;

        if (action === 'next_round') {
            currentRound = parseInt(btnNextAction.dataset.nextRoundNumber, 10);
            if (nextRoundDataCache) {
                renderRound(nextRoundDataCache);
                nextRoundDataCache = null;
            } else {
                window.location.reload();
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else if (action === 'complete_session') {
            btnNextAction.disabled = true;
            btnNextAction.textContent = 'Finalizing Results...';

            const csrfToken = getCookie('csrftoken');
            fetch(completeUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    window.location.href = resultsUrl;
                }
            })
            .catch(err => {
                console.error('Finalize error:', err);
                window.location.href = resultsUrl;
            });
        }
    }

    // Event listeners
    if (btnConfirmSelection) {
        btnConfirmSelection.addEventListener('click', submitSelection);
    }
    if (btnNextAction) {
        btnNextAction.addEventListener('click', handleNextAction);
    }
    if (btnSpeakPrompt) {
        btnSpeakPrompt.addEventListener('click', speakCurrentPrompt);
    }
    if (btnSpeakFeedback) {
        btnSpeakFeedback.addEventListener('click', function () {
            if (feedbackText) {
                speakTextSnippet(feedbackText.textContent);
            }
        });
    }

    // Initialize tile listeners on first load
    attachTileListeners();

})();
