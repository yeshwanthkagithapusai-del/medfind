from django import forms
from .models import Pharmacy

class PharmacyEditForm(forms.ModelForm):
    class Meta:
        model = Pharmacy
        fields = [
            'pharmacy_name',
            'address',
            'city',
            'state',
            'pincode',
            'phone_number',
            'latitude',
            'longitude',
        ]
        widgets = {
            'pharmacy_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
        }
