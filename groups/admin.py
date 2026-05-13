from django.contrib import admin

from .models import FriendGroup, GroupMembership


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    readonly_fields = ["joined_at"]


@admin.register(FriendGroup)
class FriendGroupAdmin(admin.ModelAdmin):
    list_display = ["display_name", "owner", "includes_ukraine", "join_code", "created_at"]
    search_fields = ["name", "owner__username", "join_code"]
    list_filter = ["includes_ukraine", "created_at"]
    readonly_fields = ["join_code", "invite_token", "created_at", "updated_at"]
    inlines = [GroupMembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["group", "user", "joined_at"]
    search_fields = ["group__name", "user__username"]
    readonly_fields = ["joined_at"]
