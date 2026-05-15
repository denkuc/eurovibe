from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import ContestEdition, ContestEntry, OfficialResult
from .services import can_edit_finalists, can_publish_scores, can_vote, get_current_edition


class ContestStateTests(TestCase):
    def test_current_edition_returns_latest_year(self):
        ContestEdition.objects.create(year=2025)
        latest = ContestEdition.objects.create(year=2026)

        self.assertEqual(get_current_edition(), latest)

    def test_open_voting_requires_finalists(self):
        edition = ContestEdition.objects.create(year=2026)

        with self.assertRaises(ValidationError):
            edition.open_voting()

    def test_open_voting_sets_state_and_can_vote(self):
        edition = ContestEdition.objects.create(year=2026)
        ContestEntry.objects.create(
            edition=edition,
            running_order=1,
            country_name="Ukraine",
            country_code="ua",
            artist_name="Northern Heart",
            song_title="Ridne Svitlo",
            is_ukraine=True,
        )

        edition.open_voting()
        edition.save()

        self.assertEqual(edition.state, ContestEdition.STATE_VOTING_OPEN)
        self.assertIsNotNone(edition.voting_open_at)
        self.assertTrue(can_vote(edition))
        self.assertFalse(can_edit_finalists(edition))

    def test_can_publish_scores_only_after_official_results_entered(self):
        edition = ContestEdition.objects.create(year=2026)
        self.assertFalse(can_publish_scores(edition))

        edition.state = ContestEdition.STATE_OFFICIAL_RESULTS_ENTERED
        self.assertTrue(can_publish_scores(edition))


class ContestEntryTests(TestCase):
    def test_year_is_unique(self):
        ContestEdition.objects.create(year=2026)

        with self.assertRaises(IntegrityError):
            ContestEdition.objects.create(year=2026)

    def test_running_order_is_unique_per_edition(self):
        edition = ContestEdition.objects.create(year=2026)
        ContestEntry.objects.create(
            edition=edition,
            running_order=1,
            country_name="Denmark",
            country_code="DK",
            artist_name="Soren Torpegaard Lund",
            song_title="For Vi Gar Hjem",
        )

        with self.assertRaises(ValidationError):
            ContestEntry.objects.create(
                edition=edition,
                running_order=1,
                country_name="Germany",
                country_code="DE",
                artist_name="Sarah Engels",
                song_title="Fire",
            )

    def test_only_one_ukraine_entry_per_edition(self):
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

        with self.assertRaises(ValidationError):
            ContestEntry.objects.create(
                edition=edition,
                running_order=2,
                country_name="Ukraine Two",
                country_code="UA",
                artist_name="Other",
                song_title="Other Song",
                is_ukraine=True,
            )

    def test_finalists_cannot_be_edited_after_setup(self):
        edition = ContestEdition.objects.create(year=2026, state=ContestEdition.STATE_VOTING_OPEN)

        with self.assertRaises(ValidationError):
            ContestEntry.objects.create(
                edition=edition,
                running_order=1,
                country_name="Denmark",
                country_code="DK",
                artist_name="Soren Torpegaard Lund",
                song_title="For Vi Gar Hjem",
            )


class ContestSeedTests(TestCase):
    def test_seed_creates_2026_edition_and_current_finalists_idempotently(self):
        call_command("seed_dev_contest")
        call_command("seed_dev_contest")

        edition = ContestEdition.objects.get(year=2026)
        self.assertEqual(edition.entries.count(), 25)
        self.assertEqual(edition.entries.filter(is_ukraine=True).count(), 1)
        self.assertEqual(edition.entries.get(running_order=7).country_name, "Ukraine")

    def test_seed_is_blocked_after_setup(self):
        edition = ContestEdition.objects.create(year=2026, state=ContestEdition.STATE_VOTING_OPEN)

        with self.assertRaises(CommandError):
            with transaction.atomic():
                call_command("seed_dev_contest")

        self.assertEqual(edition.entries.count(), 0)


class ContestViewsTests(TestCase):
    def test_finalist_list_renders_current_entries(self):
        call_command("seed_dev_contest")

        response = self.client.get(reverse("contest:finalist_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Фіналісти")
        self.assertContains(response, "Ukraine")
        self.assertContains(response, "🇺🇦")
        self.assertContains(response, "Ridnym")
        self.assertNotContains(response, "<span>DZ</span>", html=True)

    def test_finalist_list_uses_official_result_order_and_scores(self):
        edition = ContestEdition.objects.create(year=2026)
        winner = ContestEntry.objects.create(
            edition=edition,
            running_order=2,
            country_name="Germany",
            country_code="DE",
            artist_name="Sarah Engels",
            song_title="Fire",
        )
        runner_up = ContestEntry.objects.create(
            edition=edition,
            running_order=1,
            country_name="Denmark",
            country_code="DK",
            artist_name="Soren Torpegaard Lund",
            song_title="For Vi Gar Hjem",
        )
        OfficialResult.objects.create(
            edition=edition,
            final_rank=1,
            contest_entry=winner,
            jury_points=120,
            televote_points=180,
            total_points=300,
        )
        OfficialResult.objects.create(
            edition=edition,
            final_rank=2,
            contest_entry=runner_up,
            jury_points=100,
            televote_points=150,
            total_points=250,
        )

        response = self.client.get(reverse("contest:finalist_list"))
        html = response.content.decode()

        self.assertLess(html.find("Germany"), html.find("Denmark"))
        self.assertContains(response, "Журі")
        self.assertContains(response, "Глядачі")
        self.assertContains(response, "300")
