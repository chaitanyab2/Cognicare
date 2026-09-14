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
