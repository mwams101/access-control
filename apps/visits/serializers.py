from rest_framework import serializers

from .models import CheckInEvent, Pass, VisitorParty, VisitRequest


class VisitorPartySerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitorParty
        fields = ["full_name", "id_number"]


class VisitRequestSerializer(serializers.ModelSerializer):
    party = VisitorPartySerializer(many=True, required=False)
    host_name = serializers.CharField(source="host.get_full_name", read_only=True)
    masked_id = serializers.CharField(read_only=True)

    class Meta:
        model = VisitRequest
        fields = [
            "id", "reference", "full_name", "masked_id", "id_type", "phone", "email",
            "is_entity", "entity_name", "vehicle_reg", "host", "host_name",
            "purpose", "expected_start", "expected_end", "status", "created_at", "party",
        ]
        read_only_fields = ["reference", "status", "created_at"]
        extra_kwargs = {"id_number": {"write_only": True}}

    def create(self, validated_data):
        party = validated_data.pop("party", [])
        visit = VisitRequest.objects.create(**validated_data)
        for member in party:
            VisitorParty.objects.create(visit=visit, **member)
        return visit


class PassSerializer(serializers.ModelSerializer):
    visit = VisitRequestSerializer(read_only=True)

    class Meta:
        model = Pass
        fields = ["id", "visit", "valid_from", "valid_until", "single_entry", "revoked"]


class CheckInEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckInEvent
        fields = ["id", "kind", "gate", "note", "timestamp"]
