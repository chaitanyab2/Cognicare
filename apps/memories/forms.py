from django import forms
from apps.memories.models import FamiliarPerson


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
            'photo': 'Upload a clear portrait photo (JPEG, PNG, or WEBP, max 5 MB).',
            'relationship': 'Common examples: Daughter, Son, Wife, Husband, Grandchild, Brother, Sister, Friend, Niece, Nephew.',
            'is_active': 'Include this person in the active Familiar Faces game pool.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.photo:
            self.fields['photo'].required = False
            self.fields['photo'].help_text = 'Leave blank to keep the current photograph, or upload a new image to replace it.'

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Person name cannot be blank.")
        return name

    def clean_relationship(self):
        relationship = self.cleaned_data.get('relationship', '').strip()
        if not relationship:
            raise forms.ValidationError("Relationship cannot be blank.")
        return relationship
