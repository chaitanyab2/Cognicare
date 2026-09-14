/**
 * Cognicare Focus Finder Engine (Vanilla JS)
 * Phase 9: Visual Selective Attention Cognitive Activity
 * 
 * Features:
 * - Elder-friendly visual search with clear selection highlights
 * - Tremor-tolerant: changing selection has ZERO penalty before confirmation
 * - Silent latency recording (no visible ticking clock or countdown pressure)
 * - Server-side validation via CSRF-protected JSON endpoint
 * - Dignified, calm, encouraging feedback screen
 * - Web Speech API synthesis for auditory accessibility
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
        return; // Not on active Focus Finder game page
    }

    const sessionId = metaElem.dataset.sessionId;
    let currentRound = parseInt(metaElem.dataset.currentRound, 10) || 1;
    const totalRounds = parseInt(metaElem.dataset.totalRounds, 10) || 3;
    const submitUrl = metaElem.dataset.submitUrl;
    const completeUrl = metaElem.dataset.completeUrl;
    const resultsUrl = metaElem.dataset.resultsUrl;

    // DOM elements
    const roundIndicator = document.getElementById('round-indicator');
    const searchStage = document.getElementById('search-stage');
    const feedbackStage = document.getElementById('feedback-stage');
    const targetIconBox = document.getElementById('target-icon-box');
    const targetItemName = document.getElementById('target-item-name');
    const targetItemCategory = document.getElementById('target-item-category');
    const btnSpeakTarget = document.getElementById('btn-speak-target');
    const focusGrid = document.getElementById('focus-grid');
    const btnConfirmSelection = document.getElementById('btn-confirm-selection');

    // Feedback elements
    const feedbackIconContainer = document.getElementById('feedback-icon-container');
    const feedbackHeading = document.getElementById('feedback-message-heading');
    const feedbackText = document.getElementById('feedback-text');
    const feedbackTargetIconBox = document.getElementById('feedback-target-icon-box');
    const feedbackItemName = document.getElementById('feedback-item-name');
    const feedbackItemCategory = document.getElementById('feedback-item-category');
    const btnNextAction = document.getElementById('btn-next-action');

    // State variables
    let selectedItemId = null;
    let roundStartTime = Date.now();
    let isSubmitting = false;
    let nextRoundDataCache = null;
    let currentTarget = null;

    // Read initial target from JSON script if present
    const initialTargetScript = document.getElementById('initial-target-item');
    if (initialTargetScript) {
        try {
            currentTarget = JSON.parse(initialTargetScript.textContent);
        } catch (e) {
            currentTarget = null;
        }
    }

    /**
     * Attaches click handlers to grid tiles
     */
    function attachTileListeners() {
        if (!focusGrid) return;
        const tiles = focusGrid.querySelectorAll('.focus-tile');
        tiles.forEach(tile => {
            tile.addEventListener('click', function () {
                const itemId = this.dataset.itemId;
                selectTile(itemId);
            });
        });
    }

    /**
     * Updates UI when a tile is selected (penalty-free)
     */
    function selectTile(itemId) {
        selectedItemId = itemId;
        const tiles = focusGrid.querySelectorAll('.focus-tile');
        tiles.forEach(tile => {
            const isSelected = (tile.dataset.itemId === itemId);
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
     * Web Speech API hook for elderly accessibility
     */
    function speakCurrentTarget() {
        if (!('speechSynthesis' in window)) return;
        const name = currentTarget ? currentTarget.name : (targetItemName ? targetItemName.textContent.trim() : '');
        if (!name) return;

        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance('Find the ' + name);
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }

    if (btnSpeakTarget) {
        btnSpeakTarget.addEventListener('click', speakCurrentTarget);
    }

    /**
     * Submits selected tile to server for authoritative validation
     */
    async function submitSelection() {
        if (!selectedItemId || isSubmitting) return;

        isSubmitting = true;
        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = true;
        }

        const responseTimeMs = Math.max(0, Date.now() - roundStartTime);
        const payload = {
            round_number: currentRound,
            selected_ids: [selectedItemId],
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
                alert(data.error || 'There was an issue recording your answer.');
                isSubmitting = false;
                if (btnConfirmSelection) btnConfirmSelection.disabled = false;
                return;
            }

            displayFeedback(data);
        } catch (error) {
            console.error('Submission error:', error);
            alert('A network error occurred. Please try confirming again.');
            isSubmitting = false;
            if (btnConfirmSelection) btnConfirmSelection.disabled = false;
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
            feedbackHeading.textContent = 'Wonderful!';
        } else {
            feedbackIconContainer.innerHTML = '★';
            feedbackIconContainer.style.backgroundColor = 'var(--color-terracotta-50)';
            feedbackIconContainer.style.color = 'var(--color-terracotta-700)';
            feedbackHeading.textContent = 'Good Effort!';
        }

        feedbackText.textContent = evaluation.feedback_message;

        if (currentTarget) {
            feedbackTargetIconBox.innerHTML = currentTarget.svg_icon;
            feedbackItemName.textContent = currentTarget.name;
            feedbackItemCategory.textContent = currentTarget.category;
        }

        if (data.has_next_round) {
            btnNextAction.textContent = 'Continue to Next Round →';
            nextRoundDataCache = data.next_round_data;
        } else {
            btnNextAction.textContent = 'View Results →';
            nextRoundDataCache = null;
        }

        searchStage.style.display = 'none';
        feedbackStage.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    /**
     * Renders a new round dynamically
     */
    function startNextRound(roundData) {
        currentRound = roundData.round_number;
        currentTarget = roundData.target_item;

        if (roundIndicator) {
            roundIndicator.textContent = 'Round ' + currentRound + ' of ' + totalRounds;
        }

        // Update target card
        if (targetIconBox) targetIconBox.innerHTML = currentTarget.svg_icon;
        if (targetItemName) targetItemName.textContent = currentTarget.name;
        if (targetItemCategory) targetItemCategory.textContent = currentTarget.category;

        // Render grid
        if (focusGrid) {
            const cols = roundData.grid_size ? roundData.grid_size.cols : 3;
            focusGrid.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 1fr))';
            focusGrid.innerHTML = '';

            roundData.grid_items.forEach(item => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'focus-tile';
                button.dataset.itemId = item.id;
                button.setAttribute('aria-label', item.name);
                button.setAttribute('aria-pressed', 'false');

                button.innerHTML = `
                    <div class="focus-tile-check" aria-hidden="true">✓</div>
                    <div class="focus-tile-svg">
                        ${item.svg_icon}
                    </div>
                    <div class="focus-tile-label">
                        ${item.name}
                    </div>
                `;

                button.addEventListener('click', function () {
                    selectTile(item.id);
                });

                focusGrid.appendChild(button);
            });
        }

        selectedItemId = null;
        if (btnConfirmSelection) {
            btnConfirmSelection.disabled = true;
        }

        feedbackStage.style.display = 'none';
        searchStage.style.display = 'block';

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
            if (nextRoundDataCache) {
                const nextData = nextRoundDataCache;
                nextRoundDataCache = null;
                startNextRound(nextData);
            } else {
                completeSession();
            }
        });
    }

    // Initialize initial tile listeners
    attachTileListeners();
})();
