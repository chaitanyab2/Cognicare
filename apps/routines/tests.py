from datetime import time, date
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.routines.models import Routine, RoutineItem

CustomUser = get_user_model()


class RoutineModelTests(TestCase):
    """Tests for Routine and RoutineItem data models."""

    def setUp(self):
        self.member = CustomUser.objects.create_user(
            username='routine_member',
            email='rm@example.com',
            password='Password123!',
            role=Role.PATIENT
        )
        self.caregiver = CustomUser.objects.create_user(
            username='routine_caregiver',
            email='rc@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )

    def test_valid_routine_creation(self):
        routine = Routine.objects.create(
            member=self.member,
            title='Daily Morning Wellness',
            description='Morning routine checklist.',
            date=date(2026, 9, 14),
            is_active=True
        )
        self.assertEqual(routine.member, self.member)
        self.assertEqual(routine.title, 'Daily Morning Wellness')
        self.assertTrue(routine.is_active)
        self.assertIn('Daily Morning Wellness', str(routine))

    def test_routine_multiple_items_and_ordering(self):
        routine = Routine.objects.create(
            member=self.member,
            title='Full Day Routine'
        )
        item1 = RoutineItem.objects.create(
            routine=routine,
            title='Morning Stretch',
            scheduled_time=time(8, 30),
            display_order=1
        )
        item2 = RoutineItem.objects.create(
            routine=routine,
            title='Midday Hydration',
            scheduled_time=time(11, 0),
            display_order=2
        )
        item3 = RoutineItem.objects.create(
            routine=routine,
            title='Evening Walk',
            scheduled_time=time(17, 0),
            display_order=3
        )
        self.assertEqual(routine.items.count(), 3)
        items = list(routine.items.all())
        self.assertEqual(items[0], item1)
        self.assertEqual(items[1], item2)
        self.assertEqual(items[2], item3)

    def test_routine_item_completion(self):
        routine = Routine.objects.create(member=self.member, title='Test Routine')
        item = RoutineItem.objects.create(
            routine=routine,
            title='Drink Water',
            is_completed=False
        )
        self.assertIsNone(item.completed_at)
        self.assertIn("Pending", str(item))

        # Mark completed
        item.is_completed = True
        item.save()
        self.assertIsNotNone(item.completed_at)
        self.assertIn("Done", str(item))

        # Unmark completed
        item.is_completed = False
        item.save()
        self.assertIsNone(item.completed_at)

    def test_caregiver_cannot_be_routine_owner(self):
        with self.assertRaises(ValidationError):
            routine = Routine(
                member=self.caregiver,  # Invalid: has Role.CAREGIVER
                title='Invalid Routine'
            )
            routine.save()

from django.test import Client
from django.urls import reverse
from apps.accounts.models import CaregiverMemberRelationship


class RoutineViewTests(TestCase):
    """Tests for caregiver Routine CRUD views and patient daily routine checklist."""

    def setUp(self):
        self.client = Client()
        self.patient_1 = CustomUser.objects.create_user(
            username='routine_patient_1',
            email='rp1@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Sunita'
        )
        self.patient_2 = CustomUser.objects.create_user(
            username='routine_patient_2',
            email='rp2@example.com',
            password='Password123!',
            role=Role.PATIENT,
            first_name='Deben'
        )
        self.caregiver_1 = CustomUser.objects.create_user(
            username='routine_cg_1',
            email='rcg1@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        self.caregiver_2 = CustomUser.objects.create_user(
            username='routine_cg_2',
            email='rcg2@example.com',
            password='Password123!',
            role=Role.CAREGIVER
        )
        # Link caregiver_1 -> patient_1
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver_1,
            member=self.patient_1,
            is_active=True
        )
        # Link caregiver_2 -> patient_2
        CaregiverMemberRelationship.objects.create(
            caregiver=self.caregiver_2,
            member=self.patient_2,
            is_active=True
        )
        # Create routine for patient_1
        self.routine_1 = Routine.objects.create(
            member=self.patient_1,
            title='Morning Rhythm',
            description='Calm morning routine.',
            date=timezone.now().date(),
            is_active=True
        )
        self.item_1 = RoutineItem.objects.create(
            routine=self.routine_1,
            title='Drink Glass of Warm Water',
            description='Stay hydrated before breakfast.',
            scheduled_time=time(8, 0),
            display_order=1
        )
        self.item_2 = RoutineItem.objects.create(
            routine=self.routine_1,
            title='Morning Stroll',
            scheduled_time=time(8, 30),
            display_order=2
        )

    def test_anonymous_redirected_from_routines(self):
        res = self.client.get(reverse('routines:manage_routines'))
        self.assertEqual(res.status_code, 302)
        res_patient = self.client.get(reverse('routines:patient_routine'))
        self.assertEqual(res_patient.status_code, 302)

    def test_caregiver_can_view_routines(self):
        self.client.login(username='routine_cg_1', password='Password123!')
        res = self.client.get(reverse('routines:manage_routines') + f'?member={self.patient_1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Morning Rhythm')
        self.assertContains(res, 'Drink Glass of Warm Water')

    def test_caregiver_can_create_routine(self):
        self.client.login(username='routine_cg_1', password='Password123!')
        res = self.client.post(
            reverse('routines:add_routine') + f'?member={self.patient_1.id}',
            data={
                'title': 'Evening Relaxation',
                'description': 'Calm evening activities.',
                'date': timezone.now().date().isoformat(),
                'is_active': True,
            }
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Routine.objects.filter(title='Evening Relaxation', member=self.patient_1).exists())

    def test_caregiver_can_edit_routine(self):
        self.client.login(username='routine_cg_1', password='Password123!')
        res = self.client.post(
            reverse('routines:edit_routine', args=[self.routine_1.id]),
            data={
                'title': 'Morning Rhythm Updated',
                'description': 'Updated description.',
                'date': self.routine_1.date.isoformat(),
                'is_active': True,
            }
        )
        self.assertEqual(res.status_code, 302)
        self.routine_1.refresh_from_db()
        self.assertEqual(self.routine_1.title, 'Morning Rhythm Updated')

    def test_caregiver_can_add_item_to_routine(self):
        self.client.login(username='routine_cg_1', password='Password123!')
        res = self.client.post(
            reverse('routines:add_routine_item', args=[self.routine_1.id]),
            data={
                'title': 'Healthy Breakfast',
                'description': 'Warm oats and fruit.',
                'scheduled_time': '09:00:00',
                'display_order': 3,
            }
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(self.routine_1.items.filter(title='Healthy Breakfast').exists())

    def test_caregiver_can_edit_and_delete_item(self):
        self.client.login(username='routine_cg_1', password='Password123!')
        # Edit item
        res_edit = self.client.post(
            reverse('routines:edit_routine_item', args=[self.item_1.id]),
            data={
                'title': 'Drink 2 Glasses of Water',
                'description': 'Hydration is key.',
                'display_order': 1,
            }
        )
        self.assertEqual(res_edit.status_code, 302)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.title, 'Drink 2 Glasses of Water')

        # Delete item
        res_del = self.client.post(reverse('routines:delete_routine_item', args=[self.item_1.id]))
        self.assertEqual(res_del.status_code, 302)
        self.assertFalse(RoutineItem.objects.filter(id=self.item_1.id).exists())

    def test_patient_can_view_today_routine(self):
        self.client.login(username='routine_patient_1', password='Password123!')
        res = self.client.get(reverse('routines:patient_routine'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Morning Rhythm')
        self.assertContains(res, 'Drink Glass of Warm Water')

    def test_patient_can_toggle_item_completion(self):
        self.client.login(username='routine_patient_1', password='Password123!')
        self.assertFalse(self.item_1.is_completed)
        self.assertIsNone(self.item_1.completed_at)

        # Mark complete
        res = self.client.post(reverse('routines:toggle_item', args=[self.item_1.id]))
        self.assertEqual(res.status_code, 302)
        self.item_1.refresh_from_db()
        self.assertTrue(self.item_1.is_completed)
        self.assertIsNotNone(self.item_1.completed_at)

        # Toggle back to pending
        res2 = self.client.post(reverse('routines:toggle_item', args=[self.item_1.id]))
        self.assertEqual(res2.status_code, 302)
        self.item_1.refresh_from_db()
        self.assertFalse(self.item_1.is_completed)
        self.assertIsNone(self.item_1.completed_at)

    def test_cross_tenant_patient_blocked_from_toggling_others_item(self):
        # Patient 2 tries to toggle Patient 1's item
        self.client.login(username='routine_patient_2', password='Password123!')
        res = self.client.post(reverse('routines:toggle_item', args=[self.item_1.id]))
        self.assertEqual(res.status_code, 403)

    def test_cross_tenant_caregiver_blocked(self):
        # Caregiver 2 tries to access caregiver 1's member's routine
        self.client.login(username='routine_cg_2', password='Password123!')
        res = self.client.post(
            reverse('routines:edit_routine', args=[self.routine_1.id]),
            data={'title': 'Hacked Routine', 'date': '2026-09-14'}
        )
        self.assertEqual(res.status_code, 403)

    def test_routine_form_speech_to_text_bindings(self):
        self.client.login(username='routine_cg_1', password='Password123!')
        res = self.client.get(reverse('routines:add_routine') + f'?member={self.patient_1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-speech-target="id_title"')
        self.assertContains(res, 'data-speech-target="id_description"')
        self.assertContains(res, 'btn-speech')

    def test_user_created_routine_preserved_in_assamese(self):
        self.client.post(reverse('set_language'), data={'language': 'as'}, follow=True)
        self.client.login(username='routine_patient_1', password='Password123!')
        res = self.client.get(reverse('routines:patient_routine'))
        self.assertEqual(res.status_code, 200)
        # User content preserved
        self.assertContains(res, 'Morning Rhythm')
        self.assertContains(res, 'Drink Glass of Warm Water')
        # System UI translated
        self.assertContains(res, 'আজিৰ দিনলিপি')
