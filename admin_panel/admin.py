from django.contrib import admin

from .models import AdminAuditLog


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "action")
    readonly_fields = ("actor", "action", "metadata", "created_at")
