from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404

from contest.services import get_current_edition
from voting.models import Ballot

from .models import FriendGroup, GroupMembership


def user_can_edit_group_mode():
    return True


def group_has_submitted_ballots(group):
    edition = get_current_edition()
    if edition is None:
        return False
    member_ids = group.memberships.values_list("user_id", flat=True)
    return Ballot.objects.filter(
        edition=edition,
        user_id__in=member_ids,
        immutable=True,
        submitted_at__isnull=False,
    ).exists()


def create_group(*, owner, name="", includes_ukraine=True):
    group = FriendGroup.objects.create(owner=owner, name=name.strip(), includes_ukraine=includes_ukraine)
    GroupMembership.objects.get_or_create(group=group, user=owner)
    return group


def join_group(*, group, user):
    GroupMembership.objects.get_or_create(group=group, user=user)
    return group


def get_member_group_or_404(*, group_id, user):
    return get_object_or_404(
        FriendGroup.objects.filter(memberships__user=user).select_related("owner").prefetch_related("memberships__user"),
        pk=group_id,
    )


def remove_member(*, group, owner, user_id):
    if group.owner_id != owner.id:
        raise PermissionDenied("Only the group owner can remove members.")
    if group.owner_id == user_id:
        raise ValidationError("Owner cannot be removed from their own group.")
    GroupMembership.objects.filter(group=group, user_id=user_id).delete()


def update_group_settings(*, group, owner, name, includes_ukraine):
    if group.owner_id != owner.id:
        raise PermissionDenied("Only the group owner can update group settings.")
    if group.includes_ukraine != includes_ukraine and group_has_submitted_ballots(group):
        raise ValidationError("Group mode can only be changed before the first submitted ballot in this group.")
    group.name = name.strip()
    group.includes_ukraine = includes_ukraine
    group.save(update_fields=["name", "includes_ukraine", "updated_at"])
    return group


def update_group_mode(*, group, owner, includes_ukraine):
    return update_group_settings(group=group, owner=owner, name=group.name, includes_ukraine=includes_ukraine)
