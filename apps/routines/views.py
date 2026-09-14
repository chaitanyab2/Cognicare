from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_GET, require_http_methods

from apps.accounts.decorators import caregiver_required, patient_required
from apps.accounts.models import CaregiverMemberRelationship
from apps.routines.forms import RoutineForm, RoutineItemForm
from apps.routines.models import Routine, RoutineItem


def _get_supervised_member(caregiver, member_id=None):
    """
    Helper to resolve a supervised patient member for the caregiver.
    Strictly verifies active CaregiverMemberRelationship.
    """
    relationships = CaregiverMemberRelationship.objects.filter(
        caregiver=caregiver,
        is_active=True
    ).select_related('member').order_by('member__username')

    if not relationships.exists():
        return None, []

    authorized_members = [
        {
            'id': r.member.id,
            'name': f"{r.member.first_name} {r.member.last_name}".strip() or r.member.username,
            'username': r.member.username,
        }
        for r in relationships
    ]

    if member_id is not None:
        try:
            m_id = int(member_id)
        except (ValueError, TypeError):
            raise Http404("Invalid member identifier.")

        rel = relationships.filter(member_id=m_id).first()
        if not rel:
            raise PermissionDenied("Supervised member not found or unauthorized for this caregiver.")
        return rel.member, authorized_members

    return relationships.first().member, authorized_members


# ==============================================================================
# Caregiver Routine Views
# ==============================================================================

@caregiver_required
@require_GET
def manage_routines_view(request):
    """
    Caregiver portal for viewing and managing daily routines of the supervised member.
    """
    member_id = request.GET.get('member')
    selected_member, authorized_members = _get_supervised_member(request.user, member_id)

    if not selected_member:
        return render(request, 'routines/manage_routines.html', {
            'has_members': False,
            'selected_member': None,
            'authorized_members': [],
            'routines': [],
        })

    routines = Routine.objects.filter(member=selected_member).prefetch_related('items').order_by('-date', 'title')

    # Compute items completion summary per routine
    routine_cards = []
    for r in routines:
        items = list(r.items.all())
        total_items = len(items)
        completed_items = sum(1 for item in items if item.is_completed)
        pct = round((completed_items / total_items * 100)) if total_items > 0 else 0
        routine_cards.append({
            'routine': r,
            'total_items': total_items,
            'completed_items': completed_items,
            'adherence_pct': pct,
        })

    return render(request, 'routines/manage_routines.html', {
        'has_members': True,
        'selected_member': selected_member,
        'authorized_members': authorized_members,
        'routine_cards': routine_cards,
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def add_routine_view(request):
    """
    Adds a new daily routine schedule for the selected supervised member.
    """
    member_id = request.GET.get('member') or request.POST.get('member')
    selected_member, authorized_members = _get_supervised_member(request.user, member_id)

    if not selected_member:
        raise Http404("No supervised member available.")

    if request.method == 'POST':
        form = RoutineForm(request.POST)
        if form.is_valid():
            routine = form.save(commit=False)
            routine.member = selected_member
            routine.save()
            messages.success(request, _("Daily routine created successfully. You can now add schedule items."))
            return redirect(f"{reverse('routines:edit_routine', args=[routine.id])}")
    else:
        form = RoutineForm(initial={'date': timezone.now().date(), 'is_active': True})

    return render(request, 'routines/routine_form.html', {
        'form': form,
        'selected_member': selected_member,
        'is_edit': False,
        'action_title': _("Create Daily Routine"),
        'items': [],
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def edit_routine_view(request, routine_id):
    """
    Edits an existing routine metadata and lists its items. Strictly checks caregiver supervision.
    """
    routine = get_object_or_404(Routine, id=routine_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=routine.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to routine schedule.")

    if request.method == 'POST':
        form = RoutineForm(request.POST, instance=routine)
        if form.is_valid():
            form.save()
            messages.success(request, _("Routine schedule updated successfully."))
            return redirect(f"{reverse('routines:manage_routines')}?member={routine.member.id}")
    else:
        form = RoutineForm(instance=routine)

    items = routine.items.all().order_by('display_order', 'scheduled_time', 'created_at')

    return render(request, 'routines/routine_form.html', {
        'form': form,
        'selected_member': routine.member,
        'routine': routine,
        'is_edit': True,
        'action_title': _("Edit Daily Routine"),
        'items': items,
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def delete_routine_view(request, routine_id):
    """
    Deletes a routine and its items after caregiver confirmation.
    """
    routine = get_object_or_404(Routine, id=routine_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=routine.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to routine schedule.")

    member_id = routine.member.id
    if request.method == 'POST':
        routine.delete()
        messages.success(request, _("Routine schedule deleted successfully."))
        return redirect(f"{reverse('routines:manage_routines')}?member={member_id}")

    return render(request, 'routines/routine_confirm_delete.html', {
        'routine': routine,
        'selected_member': routine.member,
    })


# ==============================================================================
# Caregiver Routine Items Views
# ==============================================================================

@caregiver_required
@require_http_methods(['GET', 'POST'])
def add_routine_item_view(request, routine_id):
    """
    Adds a task or reminder item to an existing routine.
    """
    routine = get_object_or_404(Routine, id=routine_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=routine.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to routine schedule.")

    if request.method == 'POST':
        form = RoutineItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.routine = routine
            item.save()
            messages.success(request, _("Added task to routine successfully."))
            return redirect(reverse('routines:edit_routine', args=[routine.id]))
    else:
        # Suggest next display order
        last_item = routine.items.order_by('-display_order').first()
        next_order = (last_item.display_order + 1) if last_item else 1
        form = RoutineItemForm(initial={'display_order': next_order})

    return render(request, 'routines/routine_item_form.html', {
        'form': form,
        'routine': routine,
        'selected_member': routine.member,
        'is_edit': False,
        'action_title': _("Add Task to Routine"),
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def edit_routine_item_view(request, item_id):
    """
    Edits an individual task/reminder item.
    """
    item = get_object_or_404(RoutineItem, id=item_id)
    routine = item.routine

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=routine.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to routine item.")

    if request.method == 'POST':
        form = RoutineItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, _("Task updated successfully."))
            return redirect(reverse('routines:edit_routine', args=[routine.id]))
    else:
        form = RoutineItemForm(instance=item)

    return render(request, 'routines/routine_item_form.html', {
        'form': form,
        'routine': routine,
        'selected_member': routine.member,
        'item': item,
        'is_edit': True,
        'action_title': _("Edit Task"),
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def delete_routine_item_view(request, item_id):
    """
    Deletes a task/reminder item after caregiver confirmation.
    """
    item = get_object_or_404(RoutineItem, id=item_id)
    routine = item.routine

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=routine.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to routine item.")

    if request.method == 'POST':
        item.delete()
        messages.success(request, _("Task removed from routine."))
        return redirect(reverse('routines:edit_routine', args=[routine.id]))

    return render(request, 'routines/routine_item_confirm_delete.html', {
        'item': item,
        'routine': routine,
        'selected_member': routine.member,
    })


# ==============================================================================
# Patient Routine Views
# ==============================================================================

@patient_required
@require_GET
def patient_routine_view(request):
    """
    Calm, clear, and dignified daily routine checklist for the logged-in member.
    """
    today = timezone.now().date()
    routine = Routine.objects.filter(
        member=request.user,
        date=today,
        is_active=True
    ).first()

    # Fallback to most recent active routine if today has none scheduled
    if not routine:
        routine = Routine.objects.filter(
            member=request.user,
            is_active=True
        ).order_by('-date').first()

    items = []
    total_items = 0
    completed_items = 0
    adherence_pct = 0

    if routine:
        items = list(routine.items.all().order_by('display_order', 'scheduled_time', 'created_at'))
        total_items = len(items)
        completed_items = sum(1 for i in items if i.is_completed)
        adherence_pct = round((completed_items / total_items) * 100) if total_items > 0 else 0

    return render(request, 'routines/patient_routine.html', {
        'routine': routine,
        'items': items,
        'total_items': total_items,
        'completed_items': completed_items,
        'adherence_pct': adherence_pct,
        'today': today,
    })


@patient_required
@require_POST
def patient_toggle_item_view(request, item_id):
    """
    Allows the patient member to mark an item complete or incomplete.
    Strictly enforces patient ownership: item.routine.member == request.user.
    """
    item = get_object_or_404(RoutineItem, id=item_id)

    if item.routine.member != request.user:
        raise PermissionDenied("Unauthorized attempt to modify another member's routine item.")

    # Toggle completion status
    item.is_completed = not item.is_completed
    if item.is_completed:
        item.completed_at = timezone.now()
        messages.success(request, _("Completed: %(title)s") % {'title': item.title})
    else:
        item.completed_at = None

    item.save()
    return redirect(reverse('routines:patient_routine'))
