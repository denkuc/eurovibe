from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import FeedbackMessage
from contest.models import ContestEdition, ContestEntry, OfficialResult
from groups.services import create_group
from voting.models import Ballot, UserScore
from voting.services import submit_ballot

from .models import AdminAuditLog


class AdminPanelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="denkuc", password="very-long-passphrase")
        self.user = User.objects.create_user(username="sofia", password="very-long-passphrase")

    def test_superadmin_dashboard_access_is_restricted(self):
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Backoffice")
        self.assertNotContains(response, "admin-entry-list")

    def test_dashboard_shows_core_stats_and_paginated_feedback(self):
        self.client.force_login(self.admin)
        create_group(owner=self.user, name="Friends", includes_ukraine=True)
        for index in range(10):
            FeedbackMessage.objects.create(name=f"User {index}", message=f"Message {index}")

        response = self.client.get(reverse("admin_panel:dashboard"))

        self.assertContains(response, "Зареєстровано")
        self.assertContains(response, "Групи")
        self.assertContains(response, "Сторінка 1 з 2")
        self.assertContains(response, "Message 9")
        self.assertNotContains(response, "Message 0")

        response = self.client.get(f"{reverse('admin_panel:dashboard')}?feedback_page=2")

        self.assertContains(response, "Сторінка 2 з 2")
        self.assertContains(response, "Message 0")

    def test_open_voting_write_audit_log(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_panel:dashboard"), {"action": "create_edition", "year": "2026"}, follow=True)
        edition = ContestEdition.objects.get(year=2026)

        self.assertContains(response, "Фіналістів синхронізовано: 25")
        self.assertEqual(edition.entries.count(), 25)
        self.client.post(reverse("admin_panel:dashboard"), {"action": "open_voting"})
        edition.refresh_from_db()
        self.assertEqual(edition.state, ContestEdition.STATE_VOTING_OPEN)
        self.assertTrue(AdminAuditLog.objects.filter(action="open_voting").exists())

    def test_open_voting_without_finalists_is_rejected(self):
        ContestEdition.objects.create(year=2026)
        self.client.force_login(self.admin)

        response = self.client.post(reverse("admin_panel:dashboard"), {"action": "open_voting"}, follow=True)

        self.assertContains(response, "Voting cannot be opened without finalists")
        self.assertEqual(ContestEdition.objects.get(year=2026).state, ContestEdition.STATE_SETUP)

    def test_official_results_scoring_and_publish_flow(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("admin_panel:dashboard"), {"action": "create_edition", "year": "2026"})
        edition = ContestEdition.objects.get(year=2026)
        self.client.post(reverse("admin_panel:dashboard"), {"action": "open_voting"})

        edition.refresh_from_db()
        create_group(owner=self.user, name="With", includes_ukraine=True)
        exact_points = [12, 10, 8, 7, 6, 5, 4, 3, 2, 1]
        submit_ballot(
            user=self.user,
            edition=edition,
            mode=Ballot.MODE_WITH_UKRAINE,
            assignments=list(zip(exact_points, edition.entries.order_by("running_order").values_list("id", flat=True)[:10])),
        )

        self.client.post(reverse("admin_panel:dashboard"), {"action": "close_voting"})
        edition.refresh_from_db()
        self.assertEqual(edition.state, ContestEdition.STATE_VOTING_CLOSED)

        results_csv = _official_results_csv(edition)
        response = self.client.post(
            reverse("admin_panel:dashboard"),
            {"action": "preview_official_results", "results_csv": results_csv},
        )
        self.assertContains(response, "Офіційний порядок валідний")

        self.client.post(reverse("admin_panel:dashboard"), {"action": "save_official_results", "results_csv": results_csv})
        edition.refresh_from_db()
        self.assertEqual(edition.state, ContestEdition.STATE_OFFICIAL_RESULTS_ENTERED)
        self.assertEqual(OfficialResult.objects.filter(edition=edition).count(), 25)
        first_result = OfficialResult.objects.get(edition=edition, final_rank=1)
        self.assertEqual(first_result.jury_points, 101)
        self.assertEqual(first_result.televote_points, 201)
        self.assertEqual(first_result.total_points, 302)

        self.client.post(reverse("admin_panel:dashboard"), {"action": "calculate_scores"})
        score = UserScore.objects.get(edition=edition, user=self.user, mode=Ballot.MODE_WITH_UKRAINE)
        self.assertEqual(score.exact_hits, 10)
        self.assertEqual(score.total_score, 20)

        self.client.post(reverse("admin_panel:dashboard"), {"action": "publish_scores"})
        edition.refresh_from_db()
        self.assertEqual(edition.state, ContestEdition.STATE_SCORES_PUBLISHED)


def _create_finalists(edition):
    for index in range(1, 25):
        ContestEntry.objects.create(
            edition=edition,
            running_order=index,
            country_name=f"Country {index}",
            country_code="FR",
            artist_name=f"Artist {index}",
            song_title=f"Song {index}",
        )
    ContestEntry.objects.create(
        edition=edition,
        running_order=25,
        country_name="Ukraine",
        country_code="UA",
        artist_name="Northern Heart",
        song_title="Ridne Svitlo",
        is_ukraine=True,
    )


def _official_results_csv(edition):
    lines = ["final_rank,entry_id,country_name,jury_points,televote_points,total_points"]
    for rank, entry in enumerate(edition.entries.order_by("running_order"), start=1):
        lines.append(f"{rank},{entry.id},{_csv_cell(entry.country_name)},{100 + rank},{200 + rank},{300 + rank * 2}")
    return "\n".join(lines)


def _csv_cell(value):
    text = str(value)
    if any(char in text for char in [",", '"', "\n"]):
        return '"' + text.replace('"', '""') + '"'
    return text
