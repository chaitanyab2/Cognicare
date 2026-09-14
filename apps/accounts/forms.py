from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import CustomUser, Role


class BaseRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text=_("Required. A valid email address.")
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label=_("First Name")
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label=_("Last Name")
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("A user with this email address already exists."))
        return email


class PatientRegistrationForm(BaseRegistrationForm):
    """Registration form tailored for Patient accounts."""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = Role.PATIENT
        if commit:
            user.save()
        return user


class CaregiverRegistrationForm(BaseRegistrationForm):
    """Registration form tailored for Caregiver accounts."""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = Role.CAREGIVER
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Standard authentication form for Cognicare."""
    error_messages = {
        'invalid_login': _("Invalid username or password. Please try again."),
        'inactive': _("This account is currently inactive."),
    }
