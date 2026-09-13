from django.contrib import admin

from .models import Contribution


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    """Read-only on purpose: the ledger is written by the code paths
    that accept contributions, and a total that can be edited by hand
    is not a total anybody can rely on."""

    list_display = ("user", "kind", "points", "location", "created_at")
    list_filter = ("kind",)
    search_fields = ("user__username",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
