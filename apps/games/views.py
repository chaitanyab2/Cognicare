"""
Cognicare Gameplay Views.
Handles game catalog, introductions, session lifecycles, and client round submissions.
Phase 5: Gameplay Foundation + Memory Market.
"""

import json
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET

from django.utils.translation import gettext_lazy as _
from apps.accounts.decorators import patient_required
from apps.games.models import Game, GameSession
from apps.games.services import (
    GAME_ENGINES,
    create_fresh_game_session,
    record_round_submission,
    finalize_game_session,
)


@patient_required
@require_GET
def game_list_view(request):
    """
    Displays the catalog of all 6 Cognicare cognitive games.
    Active engines in GAME_ENGINES are playable; other games are shown as planned.
    """
    games = Game.objects.all().order_by('display_order', 'name')
    active_slugs = list(GAME_ENGINES.keys())
    return render(request, 'games/game_list.html', {
        'games': games,
        'active_game_slugs': active_slugs,
        'active_game_slug': 'memory-market',
    })


@patient_required
@require_GET
def game_detail_view(request, slug):
    """
    Introduction screen for an individual game with instructions and Start action.
    """
    game = get_object_or_404(Game, slug=slug, is_active=True)
    engine = GAME_ENGINES.get(game.slug)
    total_rounds = engine.TOTAL_ROUNDS if engine else 3
    instructions = engine.get_instructions() if (engine and hasattr(engine, 'get_instructions')) else None

    is_ready = True
    ready_error = None
    if game.slug == 'familiar-faces':
        people_count = request.user.familiar_people.filter(is_active=True).exclude(photo='').count()
        if people_count < 4:
            is_ready = False
            ready_error = (
                _("Familiar Faces requires at least 4 photos of family members or friends. "
                  "Currently %(count)s are ready. Please ask your caregiver to add photos in the Caregiver Portal.")
                % {'count': people_count}
            )

    return render(request, 'games/game_detail.html', {
        'game': game,
        'total_rounds': total_rounds,
        'is_playable': (game.slug in GAME_ENGINES) and is_ready,
        'instructions': instructions,
        'is_ready': is_ready,
        'ready_error': ready_error,
    })


@patient_required
@require_POST
def start_session_view(request, slug):
    """
    Initializes a fresh GameSession for the member and redirects to gameplay.
    Every explicit Start action creates a fresh session without resuming previous ones.
    """
    game = get_object_or_404(Game, slug=slug, is_active=True)
    if game.slug not in GAME_ENGINES:
        return HttpResponseBadRequest(_("This game is not yet active."))

    if game.slug == 'familiar-faces':
        people_count = request.user.familiar_people.filter(is_active=True).exclude(photo='').count()
        if people_count < 4:
            messages.warning(
                request,
                _("Familiar Faces requires at least 4 active people with photos. Currently %(count)s are ready. Please ask your caregiver to add photos.")
                % {'count': people_count}
            )
            return redirect('games:detail', slug=slug)

    try:
        difficulty = int(request.POST.get('difficulty', 1))
    except (ValueError, TypeError):
        difficulty = 1
    # Clamp difficulty between 1 and 5
    difficulty = max(1, min(5, difficulty))

    session = create_fresh_game_session(
        member=request.user,
        game_slug=game.slug,
        difficulty=difficulty,
    )
    return redirect('games:play', session_id=session.id)


@patient_required
@require_GET
def gameplay_view(request, session_id):
    """
    Active gameplay view. Serves the game interface and the current round data.
    Dispatches to the appropriate template configured by the game engine.
    """
    session = get_object_or_404(GameSession, id=session_id, member=request.user)

    # If the session is already finished, redirect directly to results
    if session.status == GameSession.Status.COMPLETED:
        return redirect('games:results', session_id=session.id)

    engine = GAME_ENGINES.get(session.game.slug)
    if not engine:
        return HttpResponseBadRequest(_("Unsupported game engine."))

    # Determine next round to present
    completed_rounds_count = session.rounds.count()
    current_round_number = completed_rounds_count + 1

    if current_round_number > engine.TOTAL_ROUNDS:
        finalize_game_session(session)
        return redirect('games:results', session_id=session.id)

    round_data = engine.get_round_data(current_round_number, session=session)
    template_name = getattr(engine, 'TEMPLATE_NAME', 'games/memory_market.html')

    return render(request, template_name, {
        'session': session,
        'round_data': round_data,
        'current_round': current_round_number,
        'total_rounds': engine.TOTAL_ROUNDS,
    })


@patient_required
@require_POST
def submit_round_view(request, session_id):
    """
    API endpoint accepting round selections from the client.
    Validates input server-side, records GameRound telemetry, and returns gentle feedback.
    """
    session = get_object_or_404(GameSession, id=session_id, member=request.user)

    if session.status != GameSession.Status.IN_PROGRESS:
        return JsonResponse({
            'success': False,
            'error': str(_("Cannot submit rounds to a completed or abandoned session."))
        }, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
        round_number = int(data.get('round_number', 0))
        selected_ids = data.get('selected_ids', [])
        response_time_ms = int(data.get('response_time_ms', 0))
        hints_used = int(data.get('hints_used', 0))
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': str(_("Invalid JSON payload."))}, status=400)

    try:
        result = record_round_submission(
            session=session,
            round_number=round_number,
            actual_selected_ids=selected_ids,
            response_time_ms=response_time_ms,
            hints_used=hints_used,
        )
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # Next round data if available
    next_round_data = None
    engine = GAME_ENGINES.get(session.game.slug)
    if result['has_next_round'] and engine:
        next_round_data = engine.get_round_data(result['next_round_number'], session=session)

    return JsonResponse({
        'success': True,
        'round_number': round_number,
        'evaluation': result['evaluation'],
        'has_next_round': result['has_next_round'],
        'next_round_number': result['next_round_number'],
        'next_round_data': next_round_data,
        'total_rounds': result['total_rounds'],
    })


@patient_required
@require_POST
def complete_session_view(request, session_id):
    """
    Finalizes the game session after all rounds have completed.
    Computes final score and metrics and returns redirection URL.
    """
    session = get_object_or_404(GameSession, id=session_id, member=request.user)

    engine = GAME_ENGINES.get(session.game.slug)
    if engine and hasattr(engine, 'TOTAL_ROUNDS'):
        if session.rounds.count() < engine.TOTAL_ROUNDS:
            return HttpResponseBadRequest(_("Cannot complete session before all required rounds are finished."))

    finalize_game_session(session)

    results_url = reverse('games:results', kwargs={'session_id': session.id})
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'success': True, 'redirect_url': results_url})

    return redirect('games:results', session_id=session.id)


@patient_required
@require_GET
def game_results_view(request, session_id):
    """
    Displays the warm, encouraging summary screen for a completed game session.
    Shows items remembered, supportive recap, and options to Play Again or return to Games.
    """
    session = get_object_or_404(GameSession, id=session_id, member=request.user)

    rounds = list(session.rounds.all().order_by('round_number'))

    # Reassuring message based on engagement
    if session.max_score > 0:
        ratio = session.score / session.max_score
        if ratio >= 0.8:
            encouragement = _("Remarkable effort! You had wonderful clarity and focus today.")
        elif ratio >= 0.5:
            encouragement = _("Great work! You completed most steps in natural order today.")
        else:
            encouragement = _("Good effort! Taking time to exercise your mind is what matters most.")
    else:
        encouragement = _("Thank you for spending time exercising with Cognicare today.")

    return render(request, 'games/game_results.html', {
        'session': session,
        'rounds': rounds,
        'encouragement': encouragement,
    })
