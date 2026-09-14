from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import os

from apps.memories.models import FamiliarPerson, Memory, validate_image_file

MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.webm'}


def validate_audio_file(file):
    """Validates uploaded audio notes for memories."""
    if not file:
        return
    file_size = getattr(file, 'size', None)
    if file_size is not None and file_size > MAX_AUDIO_SIZE_BYTES:
        raise ValidationError(
            f"Audio file size ({file_size / (1024*1024):.1f} MB) exceeds maximum limit of 10 MB."
        )
    filename = getattr(file, 'name', '')
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValidationError(
            f"Unsupported audio format '{ext}'. Allowed formats: MP3, WAV, OGG, M4A, WEBM."
        )


class FamiliarPersonForm(forms.ModelForm):
    """
    Form for caregivers to create and edit familiar people records.
    Provides suggested relationship hints without restricting input.
    """
    class Meta:
        model = FamiliarPerson
        fields = ['name', 'relationship', 'photo', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Priya, Rajesh, Aarav',
                'autocomplete': 'off',
                'required': 'required',
            }),
            'relationship': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Daughter, Son, Wife, Husband, Grandchild, Friend',
                'autocomplete': 'off',
                'required': 'required',
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'style': 'width: 20px; height: 20px; accent-color: var(--primary-main); cursor: pointer;',
            }),
        }
        help_texts = {
            'photo': _('Upload a clear portrait photo (JPEG, PNG, or WEBP, max 5 MB).'),
            'relationship': _('Common examples: Daughter, Son, Wife, Husband, Grandchild, Brother, Sister, Friend, Niece, Nephew.'),
            'is_active': _('Include this person in the active Familiar Faces game pool.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.photo:
            self.fields['photo'].required = False
            self.fields['photo'].help_text = _('Leave blank to keep the current photograph, or upload a new image to replace it.')

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError(_("Person name cannot be blank."))
        return name

    def clean_relationship(self):
        relationship = self.cleaned_data.get('relationship', '').strip()
        if not relationship:
            raise forms.ValidationError(_("Relationship cannot be blank."))
        return relationship


class MemoryForm(forms.ModelForm):
    """
    Form for caregivers to record and update personal reminiscence memories.
    Titles and descriptions are preserved verbatim without automatic translation.
    """
    class Meta:
        model = Memory
        fields = ['title', 'description', 'image', 'audio_clip']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Family Trip to Kaziranga, Summer Harvest, First Day in Guwahati',
                'autocomplete': 'off',
                'required': 'required',
                'id': 'id_title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 4,
                'placeholder': 'Share the story, cherished details, loved ones present, and fond memories...',
                'id': 'id_description',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp',
            }),
            'audio_clip': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': '.mp3,.wav,.ogg,.m4a,.webm,audio/*',
            }),
        }
        help_texts = {
            'image': _('Optional photograph for visual reminiscence (JPEG, PNG, WEBP, max 5 MB).'),
            'audio_clip': _('Optional voice note or audio memory from family (MP3, WAV, OGG, M4A, WEBM, max 10 MB).'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.image:
                self.fields['image'].help_text = _('Leave blank to keep current photo, or upload a new photo to replace it.')
            if self.instance.audio_clip:
                self.fields['audio_clip'].help_text = _('Leave blank to keep current audio note, or upload new audio to replace it.')

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError(_("Memory title cannot be blank."))
        return title

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'file'):
            validate_image_file(image)
        return image

    def clean_audio_clip(self):
        audio = self.cleaned_data.get('audio_clip')
        if audio and hasattr(audio, 'file'):
            validate_audio_file(audio)
        return audio
