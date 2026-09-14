from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class Role(models.TextChoices):
    PATIENT = 'PATIENT', 'Patient'
    CAREGIVER = 'CAREGIVER', 'Caregiver'


class CustomUser(AbstractUser):
    """
    Custom user model for Cognicare supporting two distinct roles:
    Patient and Caregiver.
    """
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PATIENT,
        help_text='Designates the role of the user within Cognicare.'
    )

    @property
    def is_patient(self):
        return self.role == Role.PATIENT

    @property
    def is_caregiver(self):
        return self.role == Role.CAREGIVER

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class CaregiverMemberRelationship(models.Model):
    """
    Explicit supervision relationship between a Caregiver and a Member (Patient).
    A caregiver can supervise multiple members, and a member can have multiple caregivers.
    """
    caregiver = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='caregiver_relationships',
        help_text='The user acting as caregiver (must have CAREGIVER role).'
    )
    member = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='member_relationships',
        help_text='The user acting as member (must have PATIENT role).'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Designates whether this supervision relationship is currently active.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Caregiver-Member Relationship'
        verbose_name_plural = 'Caregiver-Member Relationships'
        constraints = [
            models.UniqueConstraint(
                fields=['caregiver', 'member'],
                name='unique_caregiver_member_relationship'
            )
        ]
        indexes = [
            models.Index(fields=['caregiver', 'is_active']),
            models.Index(fields=['member', 'is_active']),
        ]

    def clean(self):
        super().clean()
        if self.caregiver_id and self.caregiver.role != Role.CAREGIVER:
            raise ValidationError({'caregiver': "Caregiver user must have the CAREGIVER role."})
        if self.member_id and self.member.role != Role.PATIENT:
            raise ValidationError({'member': "Member user must have the PATIENT role."})
        if self.caregiver_id and self.member_id and self.caregiver_id == self.member_id:
            raise ValidationError("A user cannot establish a caregiver relationship with themselves.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"Caregiver {self.caregiver.username} -> Member {self.member.username} ({status})"
