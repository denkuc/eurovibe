from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from contest.models import ContestEdition, ContestEntry
from voting.models import Ballot

from .models import FriendGroup, GroupMembership
from .services import create_group


class GroupModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sofia", password="very-long-passphrase")

    def test_create_group_defaults_name_and_membership(self):
        group = create_group(owner=self.user, name="", includes_ukraine=True)

        self.assertEqual(group.name, "Група sofia")
        self.assertEqual(group.join_code, group.join_code.upper())
        self.assertEqual(len(group.join_code), 6)
        self.assertGreaterEqual(len(group.invite_token), 32)
        self.assertTrue(GroupMembership.objects.filter(group=group, user=self.user).exists())

    def test_user_can_create_multiple_groups_and_join_many(self):
        other = get_user_model().objects.create_user(username="maks")

        first = create_group(owner=self.user, name="First", includes_ukraine=True)
        second = create_group(owner=self.user, name="Second", includes_ukraine=False)
        third = create_group(owner=other, name="Third", includes_ukraine=True)
        GroupMembership.objects.create(group=third, user=self.user)

        self.assertEqual(GroupMembership.objects.filter(user=self.user).count(), 3)
        self.assertEqual({first.owner_id, second.owner_id}, {self.user.id})


class GroupViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sofia", password="very-long-passphrase")
        self.other = get_user_model().objects.create_user(username="maks", password="very-long-passphrase")
        self.client.force_login(self.user)

    def test_group_list_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("groups:list"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('groups:list')}",
            fetch_redirect_response=False,
        )

    def test_create_group_view_adds_owner_as_member(self):
        response = self.client.post(reverse("groups:create"), {"name": "", "includes_ukraine": "on"})

        group = FriendGroup.objects.get(owner=self.user)
        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertEqual(group.name, "Група sofia")
        self.assertTrue(GroupMembership.objects.filter(group=group, user=self.user).exists())

    def test_create_group_form_checkbox_is_unchecked_by_default(self):
        response = self.client.get(reverse("groups:create"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"]["includes_ukraine"].value())

    def test_create_group_form_does_not_default_to_ukraine_mode(self):
        response = self.client.post(reverse("groups:create"), {"name": ""})

        group = FriendGroup.objects.get(owner=self.user)
        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertFalse(group.includes_ukraine)

    def test_detail_is_available_only_to_members(self):
        group = create_group(owner=self.other, name="Private", includes_ukraine=True)

        response = self.client.get(reverse("groups:detail", args=[group.id]))

        self.assertEqual(response.status_code, 404)

    def test_detail_shows_member_voting_status_for_group_mode(self):
        group = create_group(owner=self.user, name="Owned", includes_ukraine=False)
        GroupMembership.objects.create(group=group, user=self.other)
        edition = ContestEdition.objects.create(year=2026)
        Ballot.objects.create(edition=edition, user=self.user, mode=Ballot.MODE_WITH_UKRAINE)
        Ballot.objects.create(edition=edition, user=self.other, mode=Ballot.MODE_WITHOUT_UKRAINE)

        response = self.client.get(reverse("groups:detail", args=[group.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ще не голосував")
        self.assertContains(response, "Проголосував")

    def test_join_by_code_is_case_insensitive_and_does_not_duplicate(self):
        group = create_group(owner=self.other, name="Joinable", includes_ukraine=False)

        response = self.client.post(reverse("groups:join_by_code"), {"join_code": group.join_code.lower()})
        second_response = self.client.post(reverse("groups:join_by_code"), {"join_code": group.join_code})

        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertRedirects(second_response, reverse("groups:detail", args=[group.id]))
        self.assertEqual(GroupMembership.objects.filter(group=group, user=self.user).count(), 1)

    def test_join_by_invite_does_not_duplicate(self):
        group = create_group(owner=self.other, name="Invite", includes_ukraine=True)

        response = self.client.get(reverse("groups:join_by_invite", args=[group.invite_token]))
        second_response = self.client.get(reverse("groups:join_by_invite", args=[group.invite_token]))

        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertRedirects(second_response, reverse("groups:detail", args=[group.id]))
        self.assertEqual(GroupMembership.objects.filter(group=group, user=self.user).count(), 1)

    def test_anonymous_invite_is_saved_until_login(self):
        group = create_group(owner=self.other, name="Invite", includes_ukraine=True)
        self.client.logout()

        response = self.client.get(reverse("groups:join_by_invite", args=[group.invite_token]))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('groups:join_by_invite', args=[group.invite_token])}",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.session["pending_group_invite_token"], group.invite_token)

        login_response = self.client.post(
            reverse("accounts:login"),
            {"username": "sofia", "password": "very-long-passphrase"},
        )

        self.assertRedirects(login_response, reverse("groups:detail", args=[group.id]))
        self.assertTrue(GroupMembership.objects.filter(group=group, user=self.user).exists())

    def test_owner_can_remove_other_member_but_not_self(self):
        group = create_group(owner=self.user, name="Owned", includes_ukraine=True)
        GroupMembership.objects.create(group=group, user=self.other)

        response = self.client.post(reverse("groups:remove_member", args=[group.id, self.other.id]))

        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertFalse(GroupMembership.objects.filter(group=group, user=self.other).exists())

        response = self.client.post(reverse("groups:remove_member", args=[group.id, self.user.id]))

        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertTrue(GroupMembership.objects.filter(group=group, user=self.user).exists())

    def test_non_owner_cannot_remove_member_or_rotate_invite(self):
        group = create_group(owner=self.other, name="Owned elsewhere", includes_ukraine=True)
        GroupMembership.objects.create(group=group, user=self.user)

        remove_response = self.client.post(reverse("groups:remove_member", args=[group.id, self.other.id]))
        rotate_response = self.client.post(reverse("groups:rotate_invite", args=[group.id]))

        self.assertEqual(remove_response.status_code, 403)
        self.assertEqual(rotate_response.status_code, 403)

    def test_owner_can_rotate_join_code_and_invite_token(self):
        group = create_group(owner=self.user, name="Owned", includes_ukraine=True)
        old_code = group.join_code
        old_token = group.invite_token

        response = self.client.post(reverse("groups:rotate_invite", args=[group.id]))

        group.refresh_from_db()
        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertNotEqual(group.join_code, old_code)
        self.assertNotEqual(group.invite_token, old_token)

    def test_owner_can_change_mode_only_in_setup(self):
        group = create_group(owner=self.user, name="Owned", includes_ukraine=True)

        response = self.client.post(reverse("groups:update_mode", args=[group.id]), {"includes_ukraine": ""})
        group.refresh_from_db()

        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertFalse(group.includes_ukraine)

        edition = ContestEdition.objects.create(year=2026)
        ContestEntry.objects.create(
            edition=edition,
            running_order=1,
            country_name="Ukraine",
            country_code="UA",
            artist_name="Northern Heart",
            song_title="Ridne Svitlo",
            is_ukraine=True,
        )
        edition.open_voting()
        edition.save()

        response = self.client.post(reverse("groups:update_mode", args=[group.id]), {"includes_ukraine": "on"})
        group.refresh_from_db()

        self.assertRedirects(response, reverse("groups:detail", args=[group.id]))
        self.assertFalse(group.includes_ukraine)

    def test_model_blocks_duplicate_membership(self):
        group = create_group(owner=self.user, name="Owned", includes_ukraine=True)

        with self.assertRaises(IntegrityError):
            GroupMembership.objects.create(group=group, user=self.user)
