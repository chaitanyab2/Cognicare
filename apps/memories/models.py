from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
import os
import uuid
from apps.accounts.models import Role

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def validate_image_file(file):
    """
    Validates uploaded image files without external libraries (Pillow-free).
    Checks file existence, size, extension, and binary magic bytes.
    """
    if not file:
        raise ValidationError("An image file is required.")

    # 1. Size check
    file_size = getattr(file, 'size', None)
    if file_size is not None:
        if file_size > MAX_IMAGE_SIZE_BYTES:
            raise ValidationError(
                f"Image file size ({file_size / (1024*1024):.1f} MB) exceeds maximum allowed limit of 5 MB."
            )
        if file_size == 0:
            raise ValidationError("Uploaded file is empty.")

    # 2. Extension check
    filename = getattr(file, 'name', '')
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file format '{ext}'. Allowed formats: JPEG, PNG, WEBP."
        )

    # 3. Magic bytes / header inspection
    try:
        if hasattr(file, 'open') and (not hasattr(file, 'read') or file.closed):
            file.open('rb')
        pos = file.tell() if hasattr(file, 'tell') else 0
        file.seek(0)
        header = file.read(32)
        file.seek(pos)
    except Exception:
        header = None

    if not header:
        raise ValidationError("Unable to read image header.")

    is_jpeg = header.startswith(b'\xff\xd8\xff')
    is_png = header.startswith(b'\x89PNG\r\n\x1a\n')
    is_webp = header.startswith(b'RIFF') and len(header) >= 12 and header[8:12] == b'WEBP'

    if not (is_jpeg or is_png or is_webp):
        raise ValidationError("Invalid or corrupted image format. Please upload a valid JPEG, PNG, or WEBP image.")


def familiar_person_photo_path(instance, filename):
    """
    Generates a secure, collision-safe storage path using UUID4.
    Prevents path traversal and masks original filenames.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = '.jpg'
    safe_name = f"{uuid.uuid4().hex}{ext}"
    return os.path.join('memories', 'familiar_faces', safe_name)


class Memory(models.Model):
    """
    Represents a personal reminiscence memory item for a member.
    Titles and descriptions are stored verbatim without auto-translation.
    Optional media fields prepare the data layer for future photo/voice attachments.
    """
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memories',
        help_text='The member who owns this memory (must have PATIENT role).'
    )
    title = models.CharField(
        max_length=200,
        help_text='Title or event name, preserved verbatim.'
    )
    description = models.TextField(
        blank=True,
        help_text='Reminiscence story, context, or notes, preserved verbatim.'
    )
    # Optional media fields to support future reminiscence features without modifying schema later
    image = models.FileField(
        upload_to='memories/images/',
        blank=True,
        null=True,
        help_text='Optional photograph file for visual reminiscence and cognitive wellness.'
    )
    audio_clip = models.FileField(
        upload_to='memories/audio/',
        blank=True,
        null=True,
        help_text='Optional audio voice note from family members or loved ones.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Memory'
        verbose_name_plural = 'Memories'
        indexes = [
            models.Index(fields=['member', 'created_at']),
        ]

    def clean(self):
        super().clean()
        if self.member_id and self.member.role != Role.PATIENT:
            raise ValidationError({'member': "Memory owner must have the PATIENT role."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.member.username})"


class FamiliarPerson(models.Model):
    """
    Curated profile of a familiar person (family member, loved one, or close friend)
    associated with a patient member. Used for the Familiar Faces recognition game.
    """
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='familiar_people',
        help_text='The patient this familiar person is associated with (must have PATIENT role).'
    )
    name = models.CharField(
        max_length=100,
        help_text='Display name of the familiar person (e.g., Priya, Rajesh, Dev).'
    )
    relationship = models.CharField(
        max_length=100,
        help_text='Relationship to the patient (e.g., Daughter, Son, Wife, Husband, Grandchild, Friend).'
    )
    photo = models.FileField(
        upload_to=familiar_person_photo_path,
        validators=[validate_image_file],
        help_text='Clear portrait photograph for facial recognition activity.'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Designates whether this person is included in the Familiar Faces game pool.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Familiar Person'
        verbose_name_plural = 'Familiar People'
        indexes = [
            models.Index(fields=['member', 'is_active']),
            models.Index(fields=['member', 'name']),
        ]

    def clean(self):
        super().clean()
        if self.member_id and self.member.role != Role.PATIENT:
            raise ValidationError({'member': "Familiar person owner must have the PATIENT role."})

        # Name & relationship non-empty stripped check
        if self.name is not None and not self.name.strip():
            raise ValidationError({'name': "Person name cannot be blank."})
        if self.relationship is not None and not self.relationship.strip():
            raise ValidationError({'relationship': "Relationship cannot be blank."})

        if not self.photo:
            raise ValidationError({'photo': "An image file is required."})
        else:
            try:
                validate_image_file(self.photo)
            except ValidationError as e:
                raise ValidationError({'photo': e.messages})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} ({self.relationship}) - {self.member.username} [{status}]"

