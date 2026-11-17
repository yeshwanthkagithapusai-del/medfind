from django import forms
from medicines.models import Medicine
from .models import Inventory

class InventoryAddForm(forms.ModelForm):
    medicine = forms.ModelChoiceField(
        queryset=Medicine.objects.all().order_by('medicine_name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Medicine from Master Catalogue"
    )

    class Meta:
        model = Inventory
        fields = ['medicine', 'quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Enter stock units'
            }),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty < 0:
            raise forms.ValidationError("Stock quantity cannot be negative.")
        return qty


class InventoryEditForm(forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Enter stock units'
            }),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty < 0:
            raise forms.ValidationError("Stock quantity cannot be negative.")
        return qty
