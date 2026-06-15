from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class VisitorSignUpForm(UserCreationForm):
    """Self-registration for visitors (FR-02). Staff accounts are created by Admin."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    image = forms.ImageField(required=True, label="Profile photo")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "image")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.VISITOR
        if commit:
            user.save()
        return user
