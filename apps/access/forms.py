from django import forms

from .models import Blacklist, Zone


class ZoneForm(forms.ModelForm):
    class Meta:
        model = Zone
        fields = ["name", "description", "restricted"]


class BlacklistForm(forms.ModelForm):
    class Meta:
        model = Blacklist
        fields = ["full_name", "id_number", "reason", "active"]

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("full_name") and not cleaned.get("id_number"):
            raise forms.ValidationError("Provide at least a full name or an ID number.")
        return cleaned
