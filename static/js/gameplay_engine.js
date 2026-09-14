/**
 * Cognicare Gameplay Engine (Vanilla JS)
 * Phase 5: Memory Market & Reusable Gameplay Foundation
 * 
 * Manages stage transitions (Memory -> Selection -> Feedback),
 * silent response latency measurement, accessible keyboard selection,
 * and server-side round submission with CSRF protection.
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
        return; // Not on an active game page
    }

    // Session and route metadata
    const sessionId = metaElem.dataset.sessionId;
    let currentRound = parseInt(metaElem.dataset.currentRound, 10) || 1;
    const totalRounds = parseInt(metaElem.dataset.totalRounds, 10) || 3;
    const submitUrl = metaElem.dataset.submitUrl;
    const completeUrl = metaElem.dataset.completeUrl;
    const resultsUrl = metaElem.dataset.resultsUrl;

    // DOM Elements
    const memoryStage = document.getElementById('memory-stage');
    const selectionStage = document.getElementById('selection-stage');
    const feedbackStage = document.getElementById('feedback-stage');
    const roundIndicator = document.getElementById('round-indicator');
    const targetItemsList = document.getElementById('target-items-list');
    const marketShelf = document.getElementById('market-shelf');
    const btnReady = document.getElementById('btn-ready');
    const btnSubmitRound = document.getElementById('btn-submit-round');
    const btnNextAction = document.getElementById('btn-next-action');
    const feedbackHeading = document.getElementById('feedback-message-heading');
    const feedbackText = document.getElementById('feedback-text');
    const feedbackIconContainer = document.getElementById('feedback-icon-container');
    const btnSpeakTargets = document.getElementById('btn-speak-targets');
    const btnSpeakFeedback = document.getElementById('btn-speak-feedback');

    // Silent telemetry variables (strictly for pacing/telemetry, never shown to user)
    let selectionStartTime = null;
    let isSubmitting = false;
    let nextRoundDataCache = null;
    let hasNextRound = false;

    // Initialize selection event handlers for shelf cards
    function bindCardEvents() {
        const selectableCards = marketShelf.querySelectorAll('.market-selectable-card');
        selectableCards.forEach(card => {
            function toggleCard() {
                const isSelected = card.classList.contains('selected');
                if (isSelected) {
                    card.classList.remove('selected');
                    card.setAttribute('aria-checked', 'false');
                    card.style.borderColor = 'var(--border-color)';
                    card.style.backgroundColor = 'var(--bg-surface)';
                    const badge = card.querySelector('.check-badge');
                    if (badge) badge.style.display = 'none';
                } else {
                    card.classList.add('selected');
                    card.setAttribute('aria-checked', 'true');
                    card.style.borderColor = 'var(--primary-main)';
                    card.style.backgroundColor = 'var(--color-teal-50)';
                    const badge = card.querySelector('.check-badge');
                    if (badge) badge.style.display = 'inline-flex';
                }
            }

            card.addEventListener('click', toggleCard);
            card.addEventListener('keydown', function (e) {
                if (e.key === ' ' || e.key === 'Enter') {
                    e.preventDefault();
                    toggleCard();
                }
            });
        });
    }

    // Initial binding
    bindCardEvents();

    // Helper to get text description of shopping targets for voice read-aloud
    function getTargetsText() {
        if (!targetItemsList) return 'Please take your time to remember the shopping items.';
        const cards = targetItemsList.querySelectorAll('.target-display-card');
        const items = [];
        cards.forEach(c => {
            const nameEl = c.querySelector('h3');
            const descEl = c.querySelector('p');
            if (nameEl) {
                const name = nameEl.textContent.trim();
                const desc = descEl ? descEl.textContent.trim() : '';
                items.push(desc ? (name + ', ' + desc) : name);
            }
        });
        if (items.length === 0) return 'Please take your time to remember the shopping items.';
        return 'Please take your time to remember these items: ' + items.join('. ') + '.';
    }

    // Voice Read-Aloud Listeners
    if (btnSpeakTargets) {
        btnSpeakTargets.addEventListener('click', function () {
            if (window.CognicareVoice) {
                window.CognicareVoice.toggle(getTargetsText(), btnSpeakTargets);
            }
        });
    }

    if (btnSpeakFeedback) {
        btnSpeakFeedback.addEventListener('click', function () {
            if (window.CognicareVoice) {
                const heading = feedbackHeading ? feedbackHeading.textContent.trim() : '';
                const body = feedbackText ? feedbackText.textContent.trim() : '';
                const msg = (heading ? heading + '. ' : '') + body;
                window.CognicareVoice.toggle(msg, btnSpeakFeedback);
            }
        });
    }

    // Stage 1 -> Stage 2: Member is ready
    if (btnReady) {
        btnReady.addEventListener('click', function () {
            if (window.CognicareVoice) window.CognicareVoice.stop();
            memoryStage.style.display = 'none';
            selectionStage.style.display = 'block';
            feedbackStage.style.display = 'none';

            // Start silent latency timer when selection options appear
            selectionStartTime = Date.now();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // Stage 2 -> Stage 3: Member submits remembered items
    if (btnSubmitRound) {
        btnSubmitRound.addEventListener('click', function () {
            if (isSubmitting) return;
            if (window.CognicareVoice) window.CognicareVoice.stop();

            // Compute silent latency
            const responseTimeMs = selectionStartTime ? Math.max(0, Date.now() - selectionStartTime) : 0;

            // Collect selected item IDs
            const selectedCards = marketShelf.querySelectorAll('.market-selectable-card.selected');
            const selectedIds = [];
            selectedCards.forEach(c => {
                if (c.dataset.itemId) {
                    selectedIds.push(c.dataset.itemId);
                }
            });

            isSubmitting = true;
            btnSubmitRound.disabled = true;
            btnSubmitRound.textContent = 'Checking...';

            const payload = {
                round_number: currentRound,
                selected_ids: selectedIds,
                response_time_ms: responseTimeMs,
                hints_used: 0
            };

            const csrfToken = getCookie('csrftoken') || (document.querySelector('[name=csrfmiddlewaretoken]') ? document.querySelector('[name=csrfmiddlewaretoken]').value : '');

            fetch(submitUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (!res.ok) {
                    throw new Error('Server returned error status ' + res.status);
                }
                return res.json();
            })
            .then(data => {
                isSubmitting = false;
                btnSubmitRound.disabled = false;
                btnSubmitRound.textContent = 'Check My Items →';

                if (!data.success) {
                    alert(data.error || 'There was a problem checking your selections. Please try again.');
                    return;
                }

                // Show gentle feedback stage
                selectionStage.style.display = 'none';
                feedbackStage.style.display = 'block';

                hasNextRound = data.has_next_round;
                nextRoundDataCache = data.next_round_data;

                const evalData = data.evaluation;
                feedbackText.textContent = evalData.feedback_message || 'Thank you for exercising your memory today.';

                if (evalData.is_correct) {
                    feedbackHeading.textContent = 'Well Done!';
                    feedbackIconContainer.textContent = '✓';
                    feedbackIconContainer.style.backgroundColor = 'var(--color-teal-100)';
                    feedbackIconContainer.style.color = 'var(--color-teal-800)';
                } else {
                    feedbackHeading.textContent = 'Good Effort!';
                    feedbackIconContainer.textContent = '🌱';
                    feedbackIconContainer.style.backgroundColor = '#fef3c7';
                    feedbackIconContainer.style.color = '#92400e';
                }

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
                btnSubmitRound.disabled = false;
                btnSubmitRound.textContent = 'Check My Items →';
                alert('We had trouble saving your answer. Please check your connection and try again.');
            });
        });
    }

    // Stage 3 -> Next Round or Final Results
    if (btnNextAction) {
        btnNextAction.addEventListener('click', function () {
            if (window.CognicareVoice) window.CognicareVoice.stop();
            if (hasNextRound && nextRoundDataCache) {
                // Setup next round
                currentRound = nextRoundDataCache.round_number;
                roundIndicator.textContent = 'Round ' + currentRound + ' of ' + totalRounds;

                // Render new Target items in memory stage
                targetItemsList.innerHTML = '';
                nextRoundDataCache.target_items.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'market-item-card target-display-card';
                    card.style.cssText = 'display: flex; flex-direction: column; justify-content: center; padding: var(--space-5); border: 2px solid var(--primary-border); border-radius: var(--radius-md); background-color: var(--color-teal-50);';
                    card.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-1);">
                            <span class="category-tag" style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: var(--color-teal-800); background-color: #ffffff; padding: 2px 8px; border-radius: var(--radius-sm); border: 1px solid var(--color-teal-200);">
                                ${item.category}
                            </span>
                        </div>
                        <h3 style="font-size: 1.4rem; color: var(--color-teal-900); margin: var(--space-1) 0 4px;">
                            ${item.name}
                        </h3>
                        <p style="font-size: 0.95rem; color: var(--color-slate-600); margin: 0;">
                            ${item.descriptor}
                        </p>
                    `;
                    targetItemsList.appendChild(card);
                });

                // Render new Market Shelf items in selection stage
                marketShelf.innerHTML = '';
                nextRoundDataCache.market_items.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'market-selectable-card';
                    card.setAttribute('role', 'checkbox');
                    card.setAttribute('aria-checked', 'false');
                    card.setAttribute('tabindex', '0');
                    card.dataset.itemId = item.id;
                    card.dataset.itemName = item.name;
                    card.style.cssText = 'position: relative; display: flex; flex-direction: column; justify-content: center; padding: var(--space-5); border: 2px solid var(--border-color); border-radius: var(--radius-md); background-color: var(--bg-surface); cursor: pointer; min-height: 76px; transition: all 0.15s ease-in-out;';
                    card.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-1);">
                            <span class="category-tag" style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: var(--color-slate-600); background-color: var(--color-slate-100); padding: 2px 8px; border-radius: var(--radius-sm);">
                                ${item.category}
                            </span>
                            <span class="check-badge" style="display: none; width: 26px; height: 26px; border-radius: 50%; background-color: var(--primary-main); color: #ffffff; align-items: center; justify-content: center; font-weight: bold; font-size: 0.9rem;">
                                ✓
                            </span>
                        </div>
                        <h3 style="font-size: 1.3rem; color: var(--text-primary); margin: var(--space-1) 0 4px;">
                            ${item.name}
                        </h3>
                        <p style="font-size: 0.95rem; color: var(--text-muted); margin: 0;">
                            ${item.descriptor}
                        </p>
                    `;
                    marketShelf.appendChild(card);
                });

                bindCardEvents();

                // Switch back to Memory Stage for the next round
                feedbackStage.style.display = 'none';
                selectionStage.style.display = 'none';
                memoryStage.style.display = 'block';
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                // Final round completed: complete session and redirect to results
                btnNextAction.disabled = true;
                btnNextAction.textContent = 'Loading Summary...';

                const csrfToken = getCookie('csrftoken') || '';
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
                    window.location.href = data.redirect_url || resultsUrl;
                })
                .catch(() => {
                    window.location.href = resultsUrl;
                });
            }
        });
    }
})();
