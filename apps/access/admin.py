from django.contrib import admin

from .models import Blacklist, Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "restricted")
    list_filter = ("restricted",)


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ("full_name", "id_number", "active", "added_by", "created_at")
    list_filter = ("active",)
    search_fields = ("full_name", "id_number")
