from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contest.models import ContestEdition, ContestEntry
from groups.services import create_group, join_group
from voting.models import Ballot, BallotItem

from .services import get_global_country_leaderboard, get_group_country_leaderboard


class CountryLeaderboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sofia", password="very-long-passphrase")
        self.other = get_user_model().objects.create_user(username="maks", password="very-long-passphrase")
        self.outsider = get_user_model().objects.create_user(username="ira", password="very-long-passphrase")
        self.edition = ContestEdition.objects.create(year=2026)
        names = [
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
            "Epsilon",
            "Zeta",
            "Eta",
            "Theta",
            "Iota",
            "Kappa",
            "Ukraine",
        ]
        self.entries = [
            ContestEntry.objects.create(
                edition=self.edition,
                running_order=index,
                country_name=name,
                country_code="UA" if name == "Ukraine" else "FR",
                artist_name=f"Artist {name}",
                song_title=f"Song {name}",
                is_ukraine=name == "Ukraine",
            )
            for index, name in enumerate(names, start=1)
        ]

    def add_item(self, *, user, mode, entry, points):
        ballot, _created = Ballot.objects.get_or_create(edition=self.edition, user=user, mode=mode)
        return BallotItem.objects.create(ballot=ballot, contest_entry=entry, points=points)

    def test_global_leaderboard_is_public_and_handles_empty_data(self):
        response = self.client.get(reverse("leaderboards:global_countries"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Рейтинги")
        self.assertContains(response, "Глобально")
        self.assertContains(response, "Alpha")
        self.assertContains(response, "0")

    def test_top_navigation_uses_rankings_label(self):
        response = self.client.get(reverse("leaderboards:global_countries"))

        self.assertContains(response, ">Рейтинги</a>")
        self.assertNotContains(response, "Глобальні рейтинги")

    def test_global_sorting_uses_deterministic_tie_breaks(self):
        alpha, beta, gamma = self.entries[:3]
        self.add_item(user=self.user, mode=Ballot.MODE_WITH_UKRAINE, entry=alpha, points=12)
        self.add_item(user=self.user, mode=Ballot.MODE_WITH_UKRAINE, entry=beta, points=6)
        self.add_item(user=self.other, mode=Ballot.MODE_WITH_UKRAINE, entry=beta, points=6)
        self.add_item(user=self.other, mode=Ballot.MODE_WITH_UKRAINE, entry=gamma, points=10)

        rows = get_global_country_leaderboard(edition=self.edition)

        self.assertEqual([row.country_name for row in rows[:3]], ["Beta", "Alpha", "Gamma"])

    def test_group_leaderboard_uses_group_mode_and_members_only(self):
        group = create_group(owner=self.user, name="No Ukraine", includes_ukraine=False)
        join_group(group=group, user=self.other)
        alpha, beta = self.entries[:2]
        self.add_item(user=self.user, mode=Ballot.MODE_WITHOUT_UKRAINE, entry=alpha, points=12)
        self.add_item(user=self.user, mode=Ballot.MODE_WITH_UKRAINE, entry=beta, points=12)
        self.add_item(user=self.outsider, mode=Ballot.MODE_WITHOUT_UKRAINE, entry=beta, points=12)

        rows = get_group_country_leaderboard(edition=self.edition, group=group)

        self.assertEqual(rows[0].country_name, "Alpha")
        self.assertEqual(rows[0].total_points, 12)
        beta_row = next(row for row in rows if row.country_name == "Beta")
        self.assertEqual(beta_row.total_points, 0)

    def test_group_leaderboard_requires_membership(self):
        group = create_group(owner=self.user, name="Private", includes_ukraine=True)
        self.client.force_login(self.outsider)

        response = self.client.get(reverse("leaderboards:group_countries", args=[group.id]))

        self.assertEqual(response.status_code, 404)

    def test_group_leaderboard_view_for_member(self):
        group = create_group(owner=self.user, name="Friends", includes_ukraine=True)
        other_group = create_group(owner=self.user, name="Office", includes_ukraine=False)
        self.client.force_login(self.user)

        response = self.client.get(reverse("leaderboards:group_countries", args=[group.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Friends")
        self.assertContains(response, "Office")
        self.assertContains(response, reverse("leaderboards:group_countries", args=[other_group.id]))
        self.assertContains(response, "з Україною")
