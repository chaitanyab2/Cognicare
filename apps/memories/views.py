from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_GET, require_http_methods

from apps.accounts.decorators import caregiver_required, patient_required
from apps.accounts.models import CaregiverMemberRelationship
from apps.memories.forms import FamiliarPersonForm, MemoryForm
from apps.memories.models import FamiliarPerson, Memory


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
# Caregiver Memory Views
# ==============================================================================

@caregiver_required
@require_GET
def manage_memories_view(request):
    """
    Caregiver portal for viewing and managing memories of the supervised member.
    """
    member_id = request.GET.get('member')
    selected_member, authorized_members = _get_supervised_member(request.user, member_id)

    if not selected_member:
        return render(request, 'memories/manage_memories.html', {
            'has_members': False,
            'selected_member': None,
            'authorized_members': [],
            'memories': [],
        })

    memories = Memory.objects.filter(member=selected_member).order_by('-created_at')

    return render(request, 'memories/manage_memories.html', {
        'has_members': True,
        'selected_member': selected_member,
        'authorized_members': authorized_members,
        'memories': memories,
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def add_memory_view(request):
    """
    Adds a new reminiscence memory for the selected supervised member.
    """
    member_id = request.GET.get('member') or request.POST.get('member')
    selected_member, authorized_members = _get_supervised_member(request.user, member_id)

    if not selected_member:
        raise Http404("No supervised member available.")

    if request.method == 'POST':
        form = MemoryForm(request.POST, request.FILES)
        if form.is_valid():
            memory = form.save(commit=False)
            memory.member = selected_member
            memory.save()
            messages.success(request, _("Memory added successfully."))
            return redirect(f"{reverse('memories:manage_memories')}?member={selected_member.id}")
    else:
        form = MemoryForm()

    return render(request, 'memories/memory_form.html', {
        'form': form,
        'selected_member': selected_member,
        'is_edit': False,
        'action_title': _("Add Memory"),
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def edit_memory_view(request, memory_id):
    """
    Edits an existing memory profile. Strictly checks caregiver supervision.
    """
    memory = get_object_or_404(Memory, id=memory_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=memory.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to memory record.")

    if request.method == 'POST':
        form = MemoryForm(request.POST, request.FILES, instance=memory)
        if form.is_valid():
            form.save()
            messages.success(request, _("Memory updated successfully."))
            return redirect(f"{reverse('memories:manage_memories')}?member={memory.member.id}")
    else:
        form = MemoryForm(instance=memory)

    return render(request, 'memories/memory_form.html', {
        'form': form,
        'selected_member': memory.member,
        'memory': memory,
        'is_edit': True,
        'action_title': _("Edit Memory"),
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def delete_memory_view(request, memory_id):
    """
    Deletes a memory after caregiver confirmation.
    """
    memory = get_object_or_404(Memory, id=memory_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=memory.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to memory record.")

    member_id = memory.member.id
    if request.method == 'POST':
        memory.delete()
        messages.success(request, _("Memory deleted successfully."))
        return redirect(f"{reverse('memories:manage_memories')}?member={member_id}")

    return render(request, 'memories/memory_confirm_delete.html', {
        'memory': memory,
        'selected_member': memory.member,
    })


# ==============================================================================
# Patient Memory Views
# ==============================================================================

@patient_required
@require_GET
def patient_memories_view(request):
    """
    Dignified, warm personal reminiscence view for the logged-in member.
    """
    memories = Memory.objects.filter(member=request.user).order_by('-created_at')

    return render(request, 'memories/patient_memories.html', {
        'memories': memories,
    })


# ==============================================================================
# Familiar Person Views (Existing)
# ==============================================================================

@caregiver_required
@require_GET
def manage_familiar_people_view(request):
    """
    Caregiver dashboard for curating familiar people (portraits, names, relationships)
    for the selected supervised member.
    """
    member_id = request.GET.get('member')
    selected_member, authorized_members = _get_supervised_member(request.user, member_id)

    if not selected_member:
        return render(request, 'memories/manage_familiar_people.html', {
            'has_members': False,
            'selected_member': None,
            'authorized_members': [],
            'people': [],
            'active_count': 0,
            'total_count': 0,
            'is_ready': False,
            'min_required': 4,
        })

    people = FamiliarPerson.objects.filter(member=selected_member).order_by('name')
    active_count = people.filter(is_active=True).count()
    total_count = people.count()
    min_required = 4
    is_ready = active_count >= min_required

    return render(request, 'memories/manage_familiar_people.html', {
        'has_members': True,
        'selected_member': selected_member,
        'authorized_members': authorized_members,
        'people': people,
        'active_count': active_count,
        'total_count': total_count,
        'is_ready': is_ready,
        'min_required': min_required,
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def add_familiar_person_view(request):
    """
    Adds a new familiar person profile with portrait photograph for the selected member.
    """
    member_id = request.GET.get('member') or request.POST.get('member')
    selected_member, authorized_members = _get_supervised_member(request.user, member_id)

    if not selected_member:
        raise Http404("No supervised member available.")

    if request.method == 'POST':
        form = FamiliarPersonForm(request.POST, request.FILES)
        if form.is_valid():
            person = form.save(commit=False)
            person.member = selected_member
            person.save()
            messages.success(request, f"Added {person.name} ({person.relationship}) to familiar faces.")
            return redirect(f"{reverse('memories:manage_familiar_people')}?member={selected_member.id}")
    else:
        form = FamiliarPersonForm()

    return render(request, 'memories/familiar_person_form.html', {
        'form': form,
        'selected_member': selected_member,
        'is_edit': False,
        'action_title': f"Add Familiar Person for {selected_member.first_name or selected_member.username}",
    })


@caregiver_required
@require_http_methods(['GET', 'POST'])
def edit_familiar_person_view(request, person_id):
    """
    Edits an existing familiar person profile. Strictly checks caregiver supervision.
    """
    person = get_object_or_404(FamiliarPerson, id=person_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=person.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access to familiar person record.")

    if request.method == 'POST':
        form = FamiliarPersonForm(request.POST, request.FILES, instance=person)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {person.name} successfully.")
            return redirect(f"{reverse('memories:manage_familiar_people')}?member={person.member.id}")
    else:
        form = FamiliarPersonForm(instance=person)

    return render(request, 'memories/familiar_person_form.html', {
        'form': form,
        'selected_member': person.member,
        'person': person,
        'is_edit': True,
        'action_title': f"Edit {person.name} ({person.relationship})",
    })


@caregiver_required
@require_POST
def toggle_familiar_person_active_view(request, person_id):
    """
    Quick action to toggle active status of a familiar person in the game pool.
    """
    person = get_object_or_404(FamiliarPerson, id=person_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=person.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access.")

    person.is_active = not person.is_active
    person.save()
    status_str = "active in" if person.is_active else "paused from"
    messages.success(request, f"{person.name} is now {status_str} the Familiar Faces game pool.")
    return redirect(f"{reverse('memories:manage_familiar_people')}?member={person.member.id}")


@caregiver_required
@require_http_methods(['GET', 'POST'])
def delete_familiar_person_view(request, person_id):
    """
    Deletes a familiar person profile after confirmation.
    """
    person = get_object_or_404(FamiliarPerson, id=person_id)

    has_rel = CaregiverMemberRelationship.objects.filter(
        caregiver=request.user,
        member=person.member,
        is_active=True
    ).exists()
    if not has_rel:
        raise PermissionDenied("Unauthorized access.")

    member_id = person.member.id
    if request.method == 'POST':
        name = person.name
        person.delete()
        messages.success(request, f"Removed {name} from familiar people.")
        return redirect(f"{reverse('memories:manage_familiar_people')}?member={member_id}")

    return render(request, 'memories/familiar_person_confirm_delete.html', {
        'person': person,
        'selected_member': person.member,
    })
