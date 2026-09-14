from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.accounts.models import Role


class Routine(models.Model):
    """
    Daily structured routine schedule for a member.
    Encourages daily rhythm, orientation, and independence (morning walk, hydration, gentle reading, rest).
    """
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='routines',
        help_text='The member this routine is assigned to (must have PATIENT role).'
    )
    title = models.CharField(
        max_length=200,
        help_text='Routine title (e.g., Morning Wellness Routine).'
    )
    description = models.TextField(
        blank=True,
        help_text='General notes or guidance for this routine.'
    )
    date = models.DateField(
        default=timezone.now,
        help_text='Target date for this daily routine schedule.'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Designates whether this routine schedule is active.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'title']
        verbose_name = 'Daily Routine'
        verbose_name_plural = 'Daily Routines'
        indexes = [
            models.Index(fields=['member', 'date', 'is_active']),
            models.Index(fields=['member', '-date']),
        ]

    def clean(self):
        super().clean()
        if self.member_id and self.member.role != Role.PATIENT:
            raise ValidationError({'member': "Routine owner must have the PATIENT role."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.date}) - {self.member.username}"


class RoutineItem(models.Model):
    """
    An individual daily activity, reminder, or wellness step within a Routine.
    """
    routine = models.ForeignKey(
        Routine,
        on_delete=models.CASCADE,
        related_name='items'
    )
    title = models.CharField(
        max_length=200,
        help_text='Action item (e.g., Morning Walk, Drink Glass of Water, Water the Garden).'
    )
    description = models.TextField(
        blank=True,
        help_text='Detailed instructions for the item.'
    )
    scheduled_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Planned time of day for this routine item.'
    )
    is_completed = models.BooleanField(
        default=False,
        help_text='Whether the member has marked this task as completed.'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when task was marked as completed.'
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text='Chronological sequence order within the routine.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'scheduled_time', 'created_at']
        verbose_name = 'Routine Item'
        verbose_name_plural = 'Routine Items'
        indexes = [
            models.Index(fields=['routine', 'is_completed']),
            models.Index(fields=['scheduled_time']),
        ]

    def clean(self):
        super().clean()
        if self.is_completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.is_completed:
            self.completed_at = None

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Done" if self.is_completed else "Pending"
        time_str = f" at {self.scheduled_time.strftime('%H:%M')}" if self.scheduled_time else ""
        return f"{self.title}{time_str} [{status}]"
