"""
Cognicare Caregiver Analytics Services.
Provides database aggregation and formatting for the Caregiver Analytics Dashboard.
Phase 7: Caregiver Analytics Dashboard.
"""

import datetime
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.utils import timezone

from django.utils.translation import gettext_lazy as _

from apps.accounts.models import CaregiverMemberRelationship
from apps.games.models import Game, GameSession, GameRound
from apps.games.services import GAME_ENGINES
from apps.routines.models import Routine


GAME_COGNITIVE_DOMAINS = {
    'memory-market': _('Working Memory'),
    'daily-life-journey': _('Executive Function'),
    'familiar-faces': _('Recognition Memory'),
    'focus-finder': _('Visual Attention'),
    'word-connections': _('Semantic Memory'),
    'pattern-detective': _('Reasoning & Logic'),
}


def get_caregiver_dashboard_data(caregiver, member_id=None):
    """
    Fetches, aggregates, and structures real database telemetry for the caregiver dashboard.
    Strictly scoped to active CaregiverMemberRelationship records owned by the caregiver.
    """
    # 1. Fetch active supervised relationships
    relationships = CaregiverMemberRelationship.objects.filter(
        caregiver=caregiver,
        is_active=True
    ).select_related('member').order_by('member__username')

    if not relationships.exists():
        return {
            'has_members': False,
            'authorized_members': [],
            'selected_member': None,
        }

    # 2. Resolve selected member with strict authorization check
    if member_id is not None:
        try:
            member_id_int = int(member_id)
        except (ValueError, TypeError):
            raise Http404("Invalid member identifier.")

        selected_rel = relationships.filter(member_id=member_id_int).first()
        if not selected_rel:
            raise Http404("Member not found or not supervised by this caregiver.")
        selected_member = selected_rel.member
    else:
        selected_member = relationships.first().member

    # Authorized members list for dropdown
    authorized_members = [
        {
            'id': r.member.id,
            'name': f"{r.member.first_name} {r.member.last_name}".strip() or r.member.username,
            'username': r.member.username,
            'is_selected': (r.member.id == selected_member.id),
        }
        for r in relationships
    ]

    # 3. Query completed game sessions for selected member
    completed_sessions_qs = GameSession.objects.filter(
        member=selected_member,
        status=GameSession.Status.COMPLETED
    )

    total_completed = completed_sessions_qs.count()

    # Sessions completed in past 7 days
    seven_days_ago = timezone.now() - datetime.timedelta(days=7)
    sessions_past_7_days = completed_sessions_qs.filter(completed_at__gte=seven_days_ago).count()

    # Overall average accuracy
    avg_accuracy_val = completed_sessions_qs.aggregate(avg=Avg('accuracy'))['avg']
    overall_avg_accuracy = round(float(avg_accuracy_val), 1) if avg_accuracy_val is not None else None

    # Average response time across all completed rounds (gameplay latency telemetry)
    avg_rt_val = GameRound.objects.filter(
        session__member=selected_member,
        session__status=GameSession.Status.COMPLETED
    ).aggregate(avg=Avg('response_time_ms'))['avg']

    if avg_rt_val is not None:
        avg_response_time_ms = int(round(avg_rt_val))
        avg_response_time_sec = round(avg_response_time_ms / 1000.0, 1)
    else:
        avg_response_time_ms = None
        avg_response_time_sec = None

    # 4. Routine Adherence for Today
    today = timezone.localdate()
    today_routine = Routine.objects.filter(
        member=selected_member,
        date=today,
        is_active=True
    ).prefetch_related('items').first()

    if today_routine:
        routine_items = list(today_routine.items.all().order_by('display_order', 'scheduled_time'))
        total_routine_items = len(routine_items)
        completed_routine_items = sum(1 for item in routine_items if item.is_completed)
        routine_adherence_pct = round((completed_routine_items / total_routine_items) * 100) if total_routine_items > 0 else 0
    else:
        today_routine = None
        routine_items = []
        total_routine_items = 0
        completed_routine_items = 0
        routine_adherence_pct = None

    # 5. Cognitive Games Breakdown Table (all 6 games)
    all_games = Game.objects.all().order_by('display_order', 'name')
    games_performance = []

    for g in all_games:
        g_sessions = completed_sessions_qs.filter(game=g)
        count = g_sessions.count()

        if count > 0:
            g_avg_acc = g_sessions.aggregate(avg=Avg('accuracy'))['avg']
            g_avg_acc = round(float(g_avg_acc), 1) if g_avg_acc is not None else 0.0

            latest_sess = g_sessions.order_by('-completed_at').first()
            latest_diff = latest_sess.difficulty if latest_sess else 1

            g_avg_rt = GameRound.objects.filter(
                session__game=g,
                session__member=selected_member,
                session__status=GameSession.Status.COMPLETED
            ).aggregate(avg=Avg('response_time_ms'))['avg']

            g_avg_rt_ms = int(round(g_avg_rt)) if g_avg_rt is not None else None
            g_avg_rt_sec = round(g_avg_rt_ms / 1000.0, 1) if g_avg_rt_ms is not None else None
        else:
            g_avg_acc = None
            latest_diff = None
            g_avg_rt_ms = None
            g_avg_rt_sec = None

        is_active_engine = g.slug in GAME_ENGINES

        games_performance.append({
            'game': g,
            'name': g.name,
            'slug': g.slug,
            'domain': getattr(g, 'cognitive_domain', None) or GAME_COGNITIVE_DOMAINS.get(g.slug, 'Cognitive Wellness'),
            'is_active': is_active_engine,
            'completed_count': count,
            'current_difficulty': latest_diff,
            'avg_accuracy': g_avg_acc,
            'avg_response_time_ms': g_avg_rt_ms,
            'avg_response_time_sec': g_avg_rt_sec,
        })

    # 6. Recent 5 Completed Gameplay Sessions
    recent_sessions = list(
        completed_sessions_qs.select_related('game').order_by('-completed_at')[:5]
    )

    # 7. Accuracy Over Completed Sessions (SVG Chart Data)
    chart_sessions = list(
        completed_sessions_qs.select_related('game').order_by('completed_at')
    )

    chart_points = []
    chart_polyline = ""
    view_width = 800
    view_height = 260
    padding_left = 60
    padding_right = 30
    padding_top = 25
    padding_bottom = 45

    plot_width = view_width - padding_left - padding_right
    plot_height = view_height - padding_top - padding_bottom

    num_points = len(chart_sessions)

    for i, s in enumerate(chart_sessions):
        acc = float(s.accuracy)
        # Clamped Y coordinate: 100% -> padding_top, 0% -> padding_top + plot_height
        y = padding_top + plot_height - ((acc / 100.0) * plot_height)
        y = round(y, 1)

        # X coordinate
        if num_points == 1:
            x = padding_left + (plot_width / 2.0)
        else:
            x = padding_left + (i / float(num_points - 1)) * plot_width
        x = round(x, 1)

        date_str = s.completed_at.strftime('%b %d') if s.completed_at else ''
        time_str = s.completed_at.strftime('%H:%M') if s.completed_at else ''

        chart_points.append({
            'index': i + 1,
            'x': x,
            'y': y,
            'accuracy': acc,
            'accuracy_int': int(round(acc)),
            'date': date_str,
            'time': time_str,
            'game_name': s.game.name,
            'score': s.score,
            'max_score': s.max_score,
            'difficulty': s.difficulty,
        })

    if chart_points:
        chart_polyline = " ".join(f"{p['x']},{p['y']}" for p in chart_points)

    # Standard Y-axis grid lines (0%, 25%, 50%, 75%, 100%)
    grid_lines = []
    for pct in [0, 25, 50, 75, 100]:
        grid_y = round(padding_top + plot_height - ((pct / 100.0) * plot_height), 1)
        grid_lines.append({
            'pct': pct,
            'y': grid_y,
        })

    return {
        'has_members': True,
        'authorized_members': authorized_members,
        'selected_member': selected_member,
        'total_completed_games': total_completed,
        'sessions_past_7_days': sessions_past_7_days,
        'overall_avg_accuracy': overall_avg_accuracy,
        'avg_response_time_ms': avg_response_time_ms,
        'avg_response_time_sec': avg_response_time_sec,
        'today_routine': today_routine,
        'routine_items': routine_items,
        'routine_total_items': total_routine_items,
        'routine_completed_items': completed_routine_items,
        'routine_adherence_pct': routine_adherence_pct,
        'games_performance': games_performance,
        'recent_sessions': recent_sessions,
        'chart_points': chart_points,
        'chart_polyline': chart_polyline,
        'chart_has_data': len(chart_points) > 0,
        'chart_grid_lines': grid_lines,
        'chart_view_width': view_width,
        'chart_view_height': view_height,
        'chart_padding_left': padding_left,
        'chart_padding_bottom': padding_top + plot_height,
    }
