/**
 * Cognicare Daily Life Journey Engine (Vanilla JS)
 * Phase 6: Executive Function & Procedural Memory Sequencing
 * 
 * Features:
 * - Tap-to-order sequencing without drag-and-drop complexity
 * - Visual sequence tray with live step badges (Step 1, Step 2...)
 * - Easy Undo and Clear All sequence management
 * - Silent telemetry recording (latency, mistakes)
 * - Server-side validation via CSRF-protected JSON endpoint
 * - Gentle, reassuring feedback screen with supportive step breakdown
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
        return; // Not on active Daily Life Journey game page
    }

    // Session and route metadata
    const sessionId = metaElem.dataset.sessionId;
    let currentRound = parseInt(metaElem.dataset.currentRound, 10) || 1;
    const totalRounds = parseInt(metaElem.dataset.totalRounds, 10) || 3;
    const submitUrl = metaElem.dataset.submitUrl;
    const completeUrl = metaElem.dataset.completeUrl;
    const resultsUrl = metaElem.dataset.resultsUrl;

    // Load initial steps data injected via json_script
    let currentSteps = [];
    const initialDataElem = document.getElementById('initial-steps-data');
    if (initialDataElem) {
        try {
            currentSteps = JSON.parse(initialDataElem.textContent);
        } catch (e) {
            console.error('Failed to parse initial steps data:', e);
            currentSteps = [];
        }
    }

    // DOM Elements
    const scenarioHeading = document.getElementById('scenario-heading');
    const scenarioInstruction = document.getElementById('scenario-instruction');
    const roundIndicator = document.getElementById('round-indicator');
    const sequenceTray = document.getElementById('sequence-tray');
    const availableShelf = document.getElementById('available-steps-shelf');
    const btnUndo = document.getElementById('btn-undo');
    const btnClear = document.getElementById('btn-clear');
    const btnCheckSequence = document.getElementById('btn-check-sequence');
    const sequencingStage = document.getElementById('sequencing-stage');
    const feedbackStage = document.getElementById('feedback-stage');
    const feedbackHeading = document.getElementById('feedback-message-heading');
    const feedbackText = document.getElementById('feedback-text');
    const feedbackIconContainer = document.getElementById('feedback-icon-container');
    const feedbackBreakdown = document.getElementById('feedback-breakdown');
    const btnNextAction = document.getElementById('btn-next-action');
    const btnSpeakScenario = document.getElementById('btn-speak-scenario');
    const btnSpeakFeedback = document.getElementById('btn-speak-feedback');

    // State Variables
    let orderedSequence = []; // Array of step IDs placed by member: ['tea_boil', ...]
    let roundStartTime = Date.now();
    let isSubmitting = false;
    let hasNextRound = false;
    let nextRoundDataCache = null;

    /**
     * Finds a step object from currentSteps by ID.
     */
    function getStepById(stepId) {
        return currentSteps.find(s => s.id === stepId) || null;
    }

    /**
     * Renders both the Sequence Tray and the Available Steps shelf.
     */
    function renderSequencingUI() {
        if (!sequenceTray || !availableShelf) return;

        // Clear existing items
        sequenceTray.innerHTML = '';
        availableShelf.innerHTML = '';

        const totalStepsCount = currentSteps.length;

        // 1. Render Sequence Tray Slots
        for (let i = 0; i < totalStepsCount; i++) {
            const slot = document.createElement('div');

            if (i < orderedSequence.length) {
                // Filled slot
                const stepId = orderedSequence[i];
                const step = getStepById(stepId);
                slot.className = 'sequence-slot filled';

                slot.innerHTML = `
                    <div style="display: flex; align-items: center; gap: var(--space-4); flex-grow: 1;">
                        <span class="step-number-badge" aria-label="Step ${i + 1}">
                            ${i + 1}
                        </span>
                        <div>
                            <strong style="font-size: 1.15rem; color: var(--color-teal-900); display: block;">
                                ${step ? step.title : 'Step'}
                            </strong>
                            <span style="font-size: 0.95rem; color: var(--text-secondary); display: block; margin-top: 2px;">
                                ${step ? step.description : ''}
                            </span>
                        </div>
                    </div>
                    <button type="button" class="step-remove-btn" data-step-index="${i}" aria-label="Remove Step ${i + 1}: ${step ? step.title : ''}">
                        Remove
                    </button>
                `;

                // Bind remove button
                const removeBtn = slot.querySelector('.step-remove-btn');
                if (removeBtn) {
                    removeBtn.addEventListener('click', function (e) {
                        e.stopPropagation();
                        removeStepFromSequence(i);
                    });
                }
            } else {
                // Empty placeholder slot
                slot.className = 'sequence-slot empty';
                slot.innerHTML = `
                    <div style="display: flex; align-items: center; gap: var(--space-4);">
                        <span class="step-number-badge empty-badge" aria-label="Empty Step slot ${i + 1}">
                            ${i + 1}
                        </span>
                        <div>
                            <span style="font-size: 1.05rem; font-weight: 500; color: var(--text-muted);">
                                Step ${i + 1}: Tap an available step below
                            </span>
                        </div>
                    </div>
                `;
            }

            sequenceTray.appendChild(slot);
        }

        // 2. Render Available Steps Shelf
        currentSteps.forEach(step => {
            const isPlaced = orderedSequence.includes(step.id);
            const card = document.createElement('button');
            card.type = 'button';
            card.className = isPlaced ? 'available-step-card placed' : 'available-step-card';
            card.dataset.stepId = step.id;

            if (isPlaced) {
                const placedIndex = orderedSequence.indexOf(step.id) + 1;
                card.setAttribute('aria-disabled', 'true');
                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <strong style="font-size: 1.15rem; color: var(--color-slate-500);">
                            ${step.title}
                        </strong>
                        <span class="badge" style="background-color: var(--color-teal-100); color: var(--color-teal-800); font-size: 0.85rem; padding: 2px 10px;">
                            Placed as Step ${placedIndex}
                        </span>
                    </div>
                    <p style="font-size: 0.95rem; color: var(--text-muted); margin: 0;">
                        ${step.description}
                    </p>
                `;
            } else {
                card.setAttribute('aria-label', `Select step: ${step.title}. ${step.description}`);
                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <strong style="font-size: 1.2rem; color: var(--text-primary);">
                            ${step.title}
                        </strong>
                        <span class="badge" style="background-color: var(--color-slate-100); color: var(--text-secondary); font-size: 0.85rem; padding: 2px 10px;">
                            Tap to Add +
                        </span>
                    </div>
                    <p style="font-size: 0.95rem; color: var(--text-secondary); margin: 0;">
                        ${step.description}
                    </p>
                `;

                card.addEventListener('click', function () {
                    addStepToSequence(step.id);
                });
            }

            availableShelf.appendChild(card);
        });

        // 3. Update Action Buttons State
        if (btnUndo) {
            btnUndo.disabled = (orderedSequence.length === 0);
        }
        if (btnClear) {
            btnClear.disabled = (orderedSequence.length === 0);
        }
        if (btnCheckSequence) {
            const allPlaced = (orderedSequence.length === totalStepsCount);
            btnCheckSequence.disabled = !allPlaced;
            if (allPlaced) {
                btnCheckSequence.focus();
            }
        }
    }

    /**
     * Adds a step to the active sequence.
     */
    function addStepToSequence(stepId) {
        if (orderedSequence.includes(stepId)) return;
        if (orderedSequence.length >= currentSteps.length) return;

        orderedSequence.push(stepId);
        renderSequencingUI();
    }

    /**
     * Removes a specific step from the sequence by index.
     */
    function removeStepFromSequence(index) {
        if (index >= 0 && index < orderedSequence.length) {
            orderedSequence.splice(index, 1);
            renderSequencingUI();
        }
    }

    /**
     * Undoes the most recently placed step.
     */
    if (btnUndo) {
        btnUndo.addEventListener('click', function () {
            if (orderedSequence.length > 0) {
                orderedSequence.pop();
                renderSequencingUI();
            }
        });
    }

    /**
     * Clears all placed steps in the sequence.
     */
    if (btnClear) {
        btnClear.addEventListener('click', function () {
            if (orderedSequence.length > 0) {
                orderedSequence = [];
                renderSequencingUI();
            }
        });
    }

    // Voice Read-Aloud Listeners
    function getScenarioText() {
        const title = scenarioHeading ? scenarioHeading.textContent.trim() : '';
        const inst = scenarioInstruction ? scenarioInstruction.textContent.trim() : '';
        let text = title + '. ' + inst;
        if (currentSteps && currentSteps.length > 0) {
            text += ' Available steps: ' + currentSteps.map(s => s.title + ', ' + s.description).join('. ') + '.';
        }
        return text;
    }

    if (btnSpeakScenario) {
        btnSpeakScenario.addEventListener('click', function () {
            if (window.CognicareVoice) {
                window.CognicareVoice.toggle(getScenarioText(), btnSpeakScenario);
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

    /**
     * Submits the ordered sequence to the server.
     */
    if (btnCheckSequence) {
        btnCheckSequence.addEventListener('click', function () {
            if (isSubmitting) return;
            if (orderedSequence.length < currentSteps.length) return;
            if (window.CognicareVoice) window.CognicareVoice.stop();

            const responseTimeMs = Math.max(0, Date.now() - roundStartTime);
            isSubmitting = true;
            btnCheckSequence.disabled = true;
            btnCheckSequence.textContent = 'Checking Sequence...';

            const payload = {
                round_number: currentRound,
                selected_ids: orderedSequence,
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
                btnCheckSequence.disabled = false;
                btnCheckSequence.textContent = 'Check My Sequence →';

                if (!data.success) {
                    alert(data.error || 'There was a problem checking your sequence. Please try again.');
                    return;
                }

                // Show gentle feedback stage
                sequencingStage.style.display = 'none';
                feedbackStage.style.display = 'block';

                hasNextRound = data.has_next_round;
                nextRoundDataCache = data.next_round_data;

                const evalData = data.evaluation;
                feedbackText.textContent = evalData.feedback_message || 'Thank you for arranging the steps.';

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

                // Render sequence review breakdown
                renderFeedbackBreakdown(evalData);

                if (hasNextRound) {
                    btnNextAction.textContent = 'Next Journey →';
                } else {
                    btnNextAction.textContent = 'View Summary →';
                }

                window.scrollTo({ top: 0, behavior: 'smooth' });
            })
            .catch(err => {
                console.error('Submission error:', err);
                isSubmitting = false;
                btnCheckSequence.disabled = false;
                btnCheckSequence.textContent = 'Check My Sequence →';
                alert('We had trouble saving your sequence. Please check your connection and try again.');
            });
        });
    }

    /**
     * Renders a gentle, supportive breakdown of how the steps were arranged.
     */
    function renderFeedbackBreakdown(evalData) {
        if (!feedbackBreakdown) return;
        feedbackBreakdown.innerHTML = '';

        const heading = document.createElement('h3');
        heading.style.cssText = 'font-size: 1.15rem; color: var(--text-primary); margin-bottom: var(--space-3); font-weight: 700;';
        heading.textContent = 'Your Sequence Review';
        feedbackBreakdown.appendChild(heading);

        const listContainer = document.createElement('div');
        listContainer.style.cssText = 'display: flex; flex-direction: column; gap: var(--space-2);';

        const correctIds = evalData.correct_ids || [];

        orderedSequence.forEach((stepId, idx) => {
            const step = getStepById(stepId);
            const isStepCorrectPosition = correctIds.includes(stepId);

            const row = document.createElement('div');
            row.style.cssText = `
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: var(--space-3) var(--space-4);
                background-color: ${isStepCorrectPosition ? 'var(--color-teal-50)' : 'var(--color-slate-50)'};
                border: 1px solid ${isStepCorrectPosition ? 'var(--primary-border)' : 'var(--border-color)'};
                border-radius: var(--radius-sm);
            `;

            row.innerHTML = `
                <div style="display: flex; align-items: center; gap: var(--space-3);">
                    <span style="font-weight: 700; color: var(--color-teal-900); font-size: 1rem;">
                        Step ${idx + 1}:
                    </span>
                    <span style="font-size: 1.05rem; color: var(--text-primary);">
                        ${step ? step.title : stepId}
                    </span>
                </div>
                <div>
                    ${isStepCorrectPosition
                        ? '<span class="badge" style="background-color: var(--state-success-bg); color: var(--state-success-text); border: 1px solid var(--state-success-border); font-size: 0.85rem; font-weight: 600;">✓ Natural Order</span>'
                        : '<span class="badge" style="background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; font-size: 0.85rem;">Misplaced</span>'
                    }
                </div>
            `;

            listContainer.appendChild(row);
        });

        feedbackBreakdown.appendChild(listContainer);
    }

    /**
     * Advances to the next round or finalizes the session.
     */
    if (btnNextAction) {
        btnNextAction.addEventListener('click', function () {
            if (window.CognicareVoice) window.CognicareVoice.stop();
            if (hasNextRound && nextRoundDataCache) {
                // Setup next round
                currentRound = nextRoundDataCache.round_number;
                roundIndicator.textContent = 'Round ' + currentRound + ' of ' + totalRounds;

                scenarioHeading.textContent = nextRoundDataCache.scenario_title;
                scenarioInstruction.textContent = nextRoundDataCache.scenario_instruction;
                currentSteps = nextRoundDataCache.available_steps;
                orderedSequence = [];
                roundStartTime = Date.now();

                feedbackStage.style.display = 'none';
                sequencingStage.style.display = 'block';

                renderSequencingUI();
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

    // Initial render on page load
    renderSequencingUI();
})();
