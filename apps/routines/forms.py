from django import forms
from django.utils.translation import gettext_lazy as _
from apps.routines.models import Routine, RoutineItem


class RoutineForm(forms.ModelForm):
    """
    Form for caregivers to create and update daily routine schedules for supervised members.
    Routine titles and descriptions are preserved verbatim without translation.
    """
    class Meta:
        model = Routine
        fields = ['title', 'description', 'date', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Daily Morning Wellness, Afternoon Rhythm',
                'autocomplete': 'off',
                'required': 'required',
                'id': 'id_title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'General guidance or notes for this daily routine schedule...',
                'id': 'id_description',
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
                'required': 'required',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'style': 'width: 20px; height: 20px; accent-color: var(--primary-main); cursor: pointer;',
            }),
        }
        help_texts = {
            'date': _('Target date for this daily routine schedule.'),
            'is_active': _('Active routines are displayed on the member portal and caregiver adherence reports.'),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError(_("Routine title cannot be blank."))
        return title


class RoutineItemForm(forms.ModelForm):
    """
    Form for caregivers to configure specific tasks, reminders, and activities within a routine.
    """
    class Meta:
        model = RoutineItem
        fields = ['title', 'description', 'scheduled_time', 'display_order']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Morning Medication, Drink Water, Gentle Stroll in Garden',
                'autocomplete': 'off',
                'required': 'required',
                'id': 'id_title',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Helpful step-by-step instructions or supportive notes...',
                'id': 'id_description',
            }),
            'scheduled_time': forms.TimeInput(attrs={
                'class': 'form-input',
                'type': 'time',
            }),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
                'style': 'max-width: 120px;',
            }),
        }
        help_texts = {
            'scheduled_time': _('Optional planned time of day (e.g., 08:30 AM). Leave blank for anytime today.'),
            'display_order': _('Order in which this activity appears in the schedule (lower numbers appear first).'),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError(_("Item title cannot be blank."))
        return title
