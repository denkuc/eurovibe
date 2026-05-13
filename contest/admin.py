from django.contrib import admin

from .models import ContestEdition, ContestEntry, OfficialResult


class ContestEntryInline(admin.TabularInline):
    model = ContestEntry
    extra = 0


@admin.register(ContestEdition)
class ContestEditionAdmin(admin.ModelAdmin):
    list_display = ("year", "state", "voting_open_at", "voting_closed_at", "updated_at")
    list_filter = ("state", "year")
    inlines = [ContestEntryInline]


@admin.register(ContestEntry)
class ContestEntryAdmin(admin.ModelAdmin):
    list_display = ("running_order", "country_name", "country_code", "artist_name", "song_title", "is_ukraine")
    list_filter = ("edition", "is_ukraine")
    search_fields = ("country_name", "country_code", "artist_name", "song_title")


@admin.register(OfficialResult)
class OfficialResultAdmin(admin.ModelAdmin):
    list_display = ("edition", "final_rank", "contest_entry")
    list_filter = ("edition",)
    search_fields = ("contest_entry__country_name", "contest_entry__artist_name")
