from django.contrib import admin

from .models import Ballot, BallotItem


class BallotItemInline(admin.TabularInline):
    model = BallotItem
    extra = 0
    readonly_fields = ["points", "contest_entry"]
    can_delete = False


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    list_display = ["user", "edition", "mode", "submitted_at", "immutable"]
    list_filter = ["edition", "mode", "immutable"]
    search_fields = ["user__username"]
    inlines = [BallotItemInline]


@admin.register(BallotItem)
class BallotItemAdmin(admin.ModelAdmin):
    list_display = ["ballot", "points", "contest_entry"]
    list_filter = ["points", "ballot__edition", "ballot__mode"]
    search_fields = ["ballot__user__username", "contest_entry__country_name"]
