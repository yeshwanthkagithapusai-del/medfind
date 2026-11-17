from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from pharmacies.models import Pharmacy

User = get_user_model()

class CustomerRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
        label="First Name"
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
        label="Last Name"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create strong password', 'id': 'id_cust_password'}),
        min_length=6,
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password', 'id': 'id_cust_confirm_password'}),
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone_number']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. john_doe'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 9876543210'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        # Enforce Django AUTH_PASSWORD_VALIDATORS
        if password:
            temp_user = User(
                username=cleaned_data.get('username', ''),
                email=cleaned_data.get('email', '')
            )
            try:
                password_validation.validate_password(password, user=temp_user)
            except ValidationError as e:
                self.add_error('password', e)

        return cleaned_data


class PharmacyRegistrationForm(forms.ModelForm):
    # User fields
    owner_first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Owner First Name'}),
        label="Owner First Name"
    )
    owner_last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Owner Last Name'}),
        label="Owner Last Name"
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username for login'}),
        label="Owner Username"
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'owner@pharmacy.com'}),
        label="Official Email"
    )
    owner_phone = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Owner mobile number'}),
        label="Owner Phone"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password', 'id': 'id_pharm_password'}),
        min_length=6,
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password', 'id': 'id_pharm_confirm_password'}),
        label="Confirm Password"
    )

    class Meta:
        model = Pharmacy
        fields = [
            'pharmacy_name',
            'registration_number',
            'address',
            'city',
            'state',
            'pincode',
            'phone_number',
            'latitude',
            'longitude',
        ]
        widgets = {
            'pharmacy_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. City Life Pharmacy'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DL-PH-2024-9988'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Building, Street, Landmark'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Hyderabad'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Telangana'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '500001'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pharmacy phone'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '17.385044', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '78.486671', 'step': '0.000001'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_registration_number(self):
        reg_no = self.cleaned_data.get('registration_number', '').strip()
        if Pharmacy.objects.filter(registration_number__iexact=reg_no).exists():
            raise forms.ValidationError("A pharmacy with this license / registration number is already registered.")
        return reg_no

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        # Enforce Django AUTH_PASSWORD_VALIDATORS
        if password:
            temp_user = User(
                username=cleaned_data.get('username', ''),
                email=cleaned_data.get('email', '')
            )
            try:
                password_validation.validate_password(password, user=temp_user)
            except ValidationError as e:
                self.add_error('password', e)

        return cleaned_data


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email


class PharmacyProfileForm(forms.ModelForm):
    """Allows pharmacy owners to update contact and location details without altering approval status."""
    class Meta:
        model = Pharmacy
        fields = [
            'pharmacy_name',
            'phone_number',
            'address',
            'city',
            'state',
            'pincode',
            'latitude',
            'longitude',
        ]
        widgets = {
            'pharmacy_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
        }
