from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from apps.access.models import Zone

from .models import VisitorParty, VisitRequest

User = get_user_model()


class _HostChoiceMixin:
    """Hosts are staff members (Admin/Security excluded from being 'visited'?
    No — any non-visitor account can host)."""

    def _host_queryset(self):
        return User.objects.filter(is_active=True).exclude(role=User.Role.VISITOR)


class VisitRequestForm(forms.ModelForm, _HostChoiceMixin):
    """Visitor-facing pre-registration form (FR-06)."""

    class Meta:
        model = VisitRequest
        fields = [
            "full_name", "id_type", "id_number", "phone", "email",
            "is_entity", "entity_name", "vehicle_reg",
            "host", "purpose", "expected_start", "expected_end",
        ]
        widgets = {
            "expected_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "expected_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "purpose": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["host"].queryset = self._host_queryset()

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("expected_start"), cleaned.get("expected_end")
        if start and end and end <= start:
            raise forms.ValidationError("Expected end must be after the start time.")
        if cleaned.get("is_entity") and not cleaned.get("entity_name"):
            self.add_error("entity_name", "Entity name is required for group visits.")
        return cleaned


PartyFormSet = inlineformset_factory(
    VisitRequest, VisitorParty,
    fields=["full_name", "id_number"], extra=2, can_delete=False,
)


class WalkInForm(VisitRequestForm):
    """Security-facing walk-in registration (FR-09)."""

    gate = forms.CharField(max_length=60, initial="Main Gate")
    zones = forms.ModelMultipleChoiceField(
        queryset=Zone.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class DecisionForm(forms.Form):
    """Approve/deny with optional zones and reason (FR-16 zone assignment)."""

    zones = forms.ModelMultipleChoiceField(
        queryset=Zone.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    single_entry = forms.BooleanField(initial=True, required=False)
    reason = forms.CharField(max_length=255, required=False,
                             widget=forms.Textarea(attrs={"rows": 2}))


class VerifyForm(forms.Form):
    """Scan box: accepts a pasted/scanned token or a VR- reference (FR-11)."""

    code = forms.CharField(
        label="Scan QR or enter reference",
        widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "Token or VR-XXXXXX"}),
    )
    gate = forms.CharField(max_length=60, initial="Main Gate")
