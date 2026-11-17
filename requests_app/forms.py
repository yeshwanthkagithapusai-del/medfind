from django import forms
from .models import AvailabilityRequest

class AvailabilityRequestCreateForm(forms.ModelForm):
    class Meta:
        model = AvailabilityRequest
        fields = ['quantity_requested', 'request_message']
        widgets = {
            'quantity_requested': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1',
                'placeholder': 'Number of units needed'
            }),
            'request_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional note (e.g., urgency, when you plan to pick it up, specific brand requirement)'
            }),
        }

    def clean_quantity_requested(self):
        qty = self.cleaned_data.get('quantity_requested')
        if qty is None or qty < 1:
            raise forms.ValidationError("You must request at least 1 unit.")
        return qty


class PharmacyResponseForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=[
            ('CONFIRMED', 'Confirm Medicine Available for Pickup'),
            ('UNAVAILABLE', 'Report Medicine Unavailable / Out of Stock'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Update Availability Status"
    )

    class Meta:
        model = AvailabilityRequest
        fields = ['status', 'pharmacy_response']
        widgets = {
            'pharmacy_response': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter message for customer (e.g., Held at front counter until 7 PM, or Expecting fresh delivery tomorrow)'
            }),
        }
