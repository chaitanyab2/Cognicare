"""
Cognicare Cognitive Personalization Engine.
Phase 13C-3A: Explainable Personalization Service.

Provides deterministic, explainable, and non-clinical cognitive activity recommendations
based solely on persisted game telemetry (accuracy, session recency, cognitive domains,
and difficulty levels).

Design Principles:
1. 100% Deterministic: The exact same database state always yields the exact same recommendation.
2. 100% Explainable: Every recommendation has an audited rationale and structured category.
3. Elder-Friendly & Supportive: Zero medical or diagnostic claims. Encourages engagement.
4. Tenant Isolated: Scoped strictly to the provided member record.
5. Zero Migrations & Zero External Dependencies: Pure Python and Django ORM.
"""

from decimal import Decimal
from django.db.models import Avg
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Role
from apps.games.models import Game, GameSession
from apps.games.services import GAME_ENGINES, FamiliarFacesEngine


# Cognitive Domain Mapping for Cognicare Games
GAME_COGNITIVE_DOMAINS = {
    'memory-market': _('Working Memory'),
    'daily-life-journey': _('Executive Function'),
    'familiar-faces': _('Recognition Memory'),
    'focus-finder': _('Visual Attention'),
    'word-connections': _('Semantic Memory'),
    'pattern-detective': _('Reasoning & Logic'),
}

# Elder-Friendly Difficulty Tier Labels
DIFFICULTY_LABELS = {
    1: _('Gentle'),
    2: _('Comfortable'),
    3: _('Engaging'),
    4: _('Challenging'),
    5: _('Mastery'),
}

# Algorithmic Thresholds
ACCURACY_THRESHOLD_REINFORCEMENT = Decimal('70.00')
ACCURACY_THRESHOLD_PROGRESSION = Decimal('85.00')
MIN_SESSIONS_FOR_PROGRESSION = 2
RECENT_SESSIONS_WINDOW = 15


# Recommendation Categories
class RecommendationCategory:
    COLD_START = 'COLD_START'
    GENTLE_REINFORCEMENT = 'GENTLE_REINFORCEMENT'
    DOMAIN_VARIETY = 'DOMAIN_VARIETY'
    PROGRESSION = 'PROGRESSION'


def is_game_playable_for_member(game, member):
    """
    Checks if a game is currently playable by this specific member.
    Validates game engine registration and prerequisites (e.g. Familiar Faces photo pool).
    """
    if not game.is_active:
        return False

    if game.slug not in GAME_ENGINES:
        return False

    if game.slug == FamiliarFacesEngine.SLUG:
        people_count = member.familiar_people.filter(is_active=True).exclude(photo='').count()
        if people_count < FamiliarFacesEngine.MIN_PEOPLE_REQUIRED:
            return False

    return True


def get_eligible_games_for_member(member):
    """
    Returns an ordered list of active, playable Game objects for the member.
    Ordered deterministically by display_order, then id.
    """
    all_active_games = list(Game.objects.filter(is_active=True).order_by('display_order', 'id'))
    return [g for g in all_active_games if is_game_playable_for_member(g, member)]


def get_personalized_recommendation(member):
    """
    Generates a deterministic, explainable, and supportive activity recommendation for a member.

    Decision Hierarchy:
    1. Cold Start: If the member has 0 completed sessions, recommend a welcoming foundational
       game (Memory Market) at Level 1 (Gentle).
    2. Gentle Reinforcement: If any game in recent sessions has lower average accuracy (< 70%),
       recommend it at a gentle difficulty with comforting, supportive copy.
    3. Progression: If the member's most recently practiced game has been played consistently
       (>= 2 sessions at current difficulty) with strong accuracy (>= 85%), suggest stepping up
       one level (capped at Level 5).
    4. Domain Variety: Recommend an unplayed or least-recently practiced cognitive domain to
       maintain balanced stimulation across memory, attention, and executive function.

    Returns a structured dictionary with game details, suggested difficulty, and supportive rationale.
    """
    if not member or not hasattr(member, 'role') or member.role != Role.PATIENT:
        raise ValueError("Personalization is only available for members with the PATIENT role.")

    eligible_games = get_eligible_games_for_member(member)
    if not eligible_games:
        return None

    # Fetch all completed sessions for this member only (strict tenant isolation)
    completed_sessions_qs = GameSession.objects.filter(
        member=member,
        status=GameSession.Status.COMPLETED
    ).select_related('game')

    total_completed_count = completed_sessions_qs.count()

    # =========================================================================
    # CASE 1: COLD START (No completed history)
    # =========================================================================
    if total_completed_count == 0:
        # Default beginner game: Memory Market (or first eligible by display_order)
        chosen_game = eligible_games[0]
        for g in eligible_games:
            if g.slug == 'memory-market':
                chosen_game = g
                break

        domain_name = GAME_COGNITIVE_DOMAINS.get(chosen_game.slug, _('Cognitive Wellness'))
        return {
            'recommended_game': chosen_game,
            'game_id': chosen_game.id,
            'game_slug': chosen_game.slug,
            'game_name': chosen_game.name,
            'cognitive_domain': domain_name,
            'recommended_difficulty': 1,
            'difficulty_label': DIFFICULTY_LABELS[1],
            'reason_category': RecommendationCategory.COLD_START,
            'supportive_headline': _("Welcome Activity"),
            'supportive_rationale': _("This is a gentle activity for today's practice."),
            'is_cold_start': True,
            'stats': {
                'total_completed_sessions': 0,
                'recent_accuracy': None,
                'sessions_at_current_difficulty': 0,
            }
        }

    # =========================================================================
    # ANALYZE RECENT HISTORY (Last N completed sessions)
    # =========================================================================
    recent_sessions = list(
        completed_sessions_qs.order_by('-completed_at', '-id')[:RECENT_SESSIONS_WINDOW]
    )

    # Track metrics per game
    game_stats = {}
    for g in eligible_games:
        game_stats[g.slug] = {
            'game': g,
            'completed_count': 0,
            'accuracies': [],
            'last_completed_at': None,
            'latest_difficulty': 1,
            'sessions_at_latest_diff': 0,
        }

    for s in recent_sessions:
        slug = s.game.slug
        if slug in game_stats:
            stats = game_stats[slug]
            stats['completed_count'] += 1
            stats['accuracies'].append(Decimal(str(s.accuracy)))
            if stats['last_completed_at'] is None:
                stats['last_completed_at'] = s.completed_at or s.started_at
                stats['latest_difficulty'] = s.difficulty

    # Count consecutive sessions at the latest difficulty for games
    for slug, stats in game_stats.items():
        if stats['completed_count'] > 0:
            latest_diff = stats['latest_difficulty']
            diff_sessions = [
                s for s in recent_sessions
                if s.game.slug == slug and s.difficulty == latest_diff
            ]
            stats['sessions_at_latest_diff'] = len(diff_sessions)

    # Compute average recent accuracy per game
    for slug, stats in game_stats.items():
        if stats['accuracies']:
            stats['avg_accuracy'] = sum(stats['accuracies']) / Decimal(str(len(stats['accuracies'])))
        else:
            stats['avg_accuracy'] = None

    # =========================================================================
    # CASE 2: GENTLE REINFORCEMENT (Lower-performing activity)
    # =========================================================================
    lower_performing_games = []
    for slug, stats in game_stats.items():
        if stats['completed_count'] > 0 and stats['avg_accuracy'] is not None:
            if stats['avg_accuracy'] < ACCURACY_THRESHOLD_REINFORCEMENT:
                lower_performing_games.append(stats)

    if lower_performing_games:
        # Deterministic sorting:
        # 1. Lowest average accuracy first
        # 2. Least recently completed first (oldest timestamp)
        # 3. display_order ascending, id ascending
        lower_performing_games.sort(
            key=lambda x: (
                x['avg_accuracy'],
                x['last_completed_at'],
                x['game'].display_order,
                x['game'].id
            )
        )
        chosen_stats = lower_performing_games[0]
        chosen_game = chosen_stats['game']
        domain_name = GAME_COGNITIVE_DOMAINS.get(chosen_game.slug, _('Cognitive Wellness'))

        # Gentle difficulty: always Level 1 to avoid stress
        rec_diff = 1

        return {
            'recommended_game': chosen_game,
            'game_id': chosen_game.id,
            'game_slug': chosen_game.slug,
            'game_name': chosen_game.name,
            'cognitive_domain': domain_name,
            'recommended_difficulty': rec_diff,
            'difficulty_label': DIFFICULTY_LABELS[rec_diff],
            'reason_category': RecommendationCategory.GENTLE_REINFORCEMENT,
            'supportive_headline': _("Gentle Practice"),
            'supportive_rationale': _("This activity gives you a chance to practice at a comfortable and unhurried pace."),
            'is_cold_start': False,
            'stats': {
                'total_completed_sessions': total_completed_count,
                'recent_accuracy': float(round(chosen_stats['avg_accuracy'], 1)),
                'sessions_at_current_difficulty': chosen_stats['sessions_at_latest_diff'],
            }
        }

    # =========================================================================
    # CASE 3: PROGRESSION (Consistently strong performance)
    # =========================================================================
    most_recent_session = recent_sessions[0] if recent_sessions else None
    if most_recent_session and most_recent_session.game.slug in game_stats:
        recent_slug = most_recent_session.game.slug
        r_stats = game_stats[recent_slug]
        curr_diff = r_stats['latest_difficulty']

        if (
            r_stats['sessions_at_latest_diff'] >= MIN_SESSIONS_FOR_PROGRESSION
            and r_stats['avg_accuracy'] is not None
            and r_stats['avg_accuracy'] >= ACCURACY_THRESHOLD_PROGRESSION
            and curr_diff < 5
        ):
            # Check that no recent session on this game was poor (< 75%)
            recent_game_accs = [
                s.accuracy for s in recent_sessions
                if s.game.slug == recent_slug and s.difficulty == curr_diff
            ]
            if all(acc >= Decimal('75.00') for acc in recent_game_accs):
                chosen_game = r_stats['game']
                domain_name = GAME_COGNITIVE_DOMAINS.get(chosen_game.slug, _('Cognitive Wellness'))
                new_diff = min(5, curr_diff + 1)

                return {
                    'recommended_game': chosen_game,
                    'game_id': chosen_game.id,
                    'game_slug': chosen_game.slug,
                    'game_name': chosen_game.name,
                    'cognitive_domain': domain_name,
                    'recommended_difficulty': new_diff,
                    'difficulty_label': DIFFICULTY_LABELS[new_diff],
                    'reason_category': RecommendationCategory.PROGRESSION,
                    'supportive_headline': _("Engaging Challenge"),
                    'supportive_rationale': _("You have been doing well with this activity. This is an engaging opportunity for today's practice."),
                    'is_cold_start': False,
                    'stats': {
                        'total_completed_sessions': total_completed_count,
                        'recent_accuracy': float(round(r_stats['avg_accuracy'], 1)),
                        'sessions_at_current_difficulty': r_stats['sessions_at_latest_diff'],
                    }
                }

    # =========================================================================
    # CASE 4: DOMAIN VARIETY (Unplayed or least-recently practiced domain)
    # =========================================================================
    # 4a: Check for completely unplayed eligible games first
    unplayed_games = [
        stats['game'] for slug, stats in game_stats.items()
        if stats['completed_count'] == 0
    ]

    if unplayed_games:
        # Deterministic tie-breaker: display_order ascending, id ascending
        unplayed_games.sort(key=lambda g: (g.display_order, g.id))
        chosen_game = unplayed_games[0]
        domain_name = GAME_COGNITIVE_DOMAINS.get(chosen_game.slug, _('Cognitive Wellness'))
        rec_diff = 1

        return {
            'recommended_game': chosen_game,
            'game_id': chosen_game.id,
            'game_slug': chosen_game.slug,
            'game_name': chosen_game.name,
            'cognitive_domain': domain_name,
            'recommended_difficulty': rec_diff,
            'difficulty_label': DIFFICULTY_LABELS[rec_diff],
            'reason_category': RecommendationCategory.DOMAIN_VARIETY,
            'supportive_headline': _("Explore Something Fresh"),
            'supportive_rationale': _("You haven't played this activity recently. It offers a fresh way to exercise focus."),
            'is_cold_start': False,
            'stats': {
                'total_completed_sessions': total_completed_count,
                'recent_accuracy': None,
                'sessions_at_current_difficulty': 0,
            }
        }

    # 4b: All eligible games have been played at least once.
    # Select the least-recently completed game (oldest completed_at timestamp).
    played_games_stats = [stats for stats in game_stats.values() if stats['completed_count'] > 0]
    played_games_stats.sort(
        key=lambda x: (
            x['last_completed_at'],
            x['game'].display_order,
            x['game'].id
        )
    )

    chosen_stats = played_games_stats[0]
    chosen_game = chosen_stats['game']
    domain_name = GAME_COGNITIVE_DOMAINS.get(chosen_game.slug, _('Cognitive Wellness'))
    rec_diff = chosen_stats['latest_difficulty']

    return {
        'recommended_game': chosen_game,
        'game_id': chosen_game.id,
        'game_slug': chosen_game.slug,
        'game_name': chosen_game.name,
        'cognitive_domain': domain_name,
        'recommended_difficulty': rec_diff,
        'difficulty_label': DIFFICULTY_LABELS[rec_diff],
        'reason_category': RecommendationCategory.DOMAIN_VARIETY,
        'supportive_headline': _("Today's Gentle Suggestion"),
        'supportive_rationale': _("You haven't played this activity recently. Try this gentle activity for today's practice."),
        'is_cold_start': False,
        'stats': {
            'total_completed_sessions': total_completed_count,
            'recent_accuracy': float(round(chosen_stats['avg_accuracy'], 1)) if chosen_stats['avg_accuracy'] is not None else None,
            'sessions_at_current_difficulty': chosen_stats['sessions_at_latest_diff'],
        }
    }
