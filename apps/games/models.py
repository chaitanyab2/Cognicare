from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from apps.accounts.models import Role


class Game(models.Model):
    """
    Registry for the approved Cognicare cognitive games.
    Configuration and descriptive metadata only at this stage.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Cognitive Game'
        verbose_name_plural = 'Cognitive Games'

    def __str__(self):
        return self.name


class GameSession(models.Model):
    """
    Represents one complete or attempted gameplay session by a member.
    Telemetry is used strictly for pacing and difficulty adaptation.
    """
    class Status(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        ABANDONED = 'ABANDONED', 'Abandoned'

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='game_sessions',
        help_text='The member playing the session (must have PATIENT role).'
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS
    )
    difficulty = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Difficulty level from 1 to 5.'
    )
    score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    max_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    accuracy = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text='Accuracy percentage (0.00 to 100.00).'
    )
    total_time_ms = models.PositiveIntegerField(
        default=0,
        help_text='Total gameplay time in milliseconds (cannot be negative).'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Game Session'
        verbose_name_plural = 'Game Sessions'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(difficulty__gte=1, difficulty__lte=5),
                name='check_difficulty_range'
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0),
                name='check_non_negative_score'
            ),
            models.CheckConstraint(
                condition=models.Q(max_score__gte=0),
                name='check_non_negative_max_score'
            ),
            models.CheckConstraint(
                condition=models.Q(accuracy__gte=0, accuracy__lte=100),
                name='check_accuracy_range'
            ),
            models.CheckConstraint(
                condition=models.Q(total_time_ms__gte=0),
                name='check_non_negative_total_time'
            ),
        ]
        indexes = [
            models.Index(fields=['member']),
            models.Index(fields=['game']),
            models.Index(fields=['member', 'game']),
            models.Index(fields=['member', 'started_at']),
            models.Index(fields=['status']),
            models.Index(fields=['started_at']),
        ]

    def clean(self):
        super().clean()
        if self.member_id and self.member.role != Role.PATIENT:
            raise ValidationError({'member': "GameSession member must have the PATIENT role."})
        if self.difficulty < 1 or self.difficulty > 5:
            raise ValidationError({'difficulty': "Difficulty level must be between 1 and 5."})
        if self.total_time_ms < 0:
            raise ValidationError({'total_time_ms': "Total gameplay time cannot be negative."})
        if self.score < 0:
            raise ValidationError({'score': "Score cannot be negative."})
        if self.max_score < 0:
            raise ValidationError({'max_score': "Max score cannot be negative."})
        if self.accuracy < 0 or self.accuracy > 100:
            raise ValidationError({'accuracy': "Accuracy must be between 0.00 and 100.00."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.game.name} - {self.member.username} (Lvl {self.difficulty}, {self.status})"


class GameRound(models.Model):
    """
    Stores one round/interaction inside a GameSession.
    Uses flexible JSONField for game-agnostic stimulus and response tracking.
    """
    session = models.ForeignKey(
        GameSession,
        on_delete=models.CASCADE,
        related_name='rounds'
    )
    round_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text='Positive sequential round number (1, 2, ...).'
    )
    stimulus_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured JSON data of stimuli presented during this round.'
    )
    expected_response = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured JSON data of expected correct response.'
    )
    actual_response = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured JSON data of actual member response.'
    )
    is_correct = models.BooleanField(default=False)
    response_time_ms = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Response latency in milliseconds (cannot be negative).'
    )
    mistake_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Number of mistaken interactions before round completion.'
    )
    hints_used = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Number of hints requested during this round.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['session', 'round_number']
        verbose_name = 'Game Round'
        verbose_name_plural = 'Game Rounds'
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'round_number'],
                name='unique_round_per_session'
            ),
            models.CheckConstraint(
                condition=models.Q(round_number__gte=1),
                name='check_positive_round_number'
            ),
            models.CheckConstraint(
                condition=models.Q(response_time_ms__gte=0),
                name='check_non_negative_response_time'
            ),
            models.CheckConstraint(
                condition=models.Q(mistake_count__gte=0),
                name='check_non_negative_mistake_count'
            ),
            models.CheckConstraint(
                condition=models.Q(hints_used__gte=0),
                name='check_non_negative_hints_used'
            ),
        ]
        indexes = [
            models.Index(fields=['session', 'round_number']),
            models.Index(fields=['is_correct']),
        ]

    def clean(self):
        super().clean()
        if self.round_number < 1:
            raise ValidationError({'round_number': "Round number must be positive (>= 1)."})
        if self.response_time_ms < 0:
            raise ValidationError({'response_time_ms': "Response time cannot be negative."})
        if self.mistake_count < 0:
            raise ValidationError({'mistake_count': "Mistake count cannot be negative."})
        if self.hints_used < 0:
            raise ValidationError({'hints_used': "Hints used cannot be negative."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        result = "Correct" if self.is_correct else "Incorrect"
        return f"Session {self.session_id} - Round {self.round_number} ({result}, {self.response_time_ms}ms)"
