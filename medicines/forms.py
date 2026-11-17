from django import forms
from .models import Medicine

class MedicineForm(forms.ModelForm):
    class Meta:
        model = Medicine
        fields = ['medicine_name', 'generic_name', 'strength', 'dosage_form', 'category', 'description']
        widgets = {
            'medicine_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Paracetamol / Dolo 650'}),
            'generic_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Acetaminophen'}),
            'strength': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 650mg'}),
            'dosage_form': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Usage indications or warnings'}),
        }
