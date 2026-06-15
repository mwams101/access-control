from django.contrib import admin

from .models import CheckInEvent, Pass, VisitorParty, VisitRequest


class PartyInline(admin.TabularInline):
    model = VisitorParty
    extra = 0


@admin.register(VisitRequest)
class VisitRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "display_name", "host", "status",
                    "expected_start", "expected_end")
    list_filter = ("status", "is_entity")
    search_fields = ("reference", "full_name", "entity_name", "id_number")
    date_hierarchy = "expected_start"
    inlines = [PartyInline]


@admin.register(Pass)
class PassAdmin(admin.ModelAdmin):
    list_display = ("visit", "valid_from", "valid_until", "single_entry", "revoked")
    list_filter = ("revoked", "single_entry")


@admin.register(CheckInEvent)
class CheckInEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "kind", "pass_obj", "gate", "performed_by")
    list_filter = ("kind", "gate")
    date_hierarchy = "timestamp"
