from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contest.models import ContestEdition, OfficialResult
from contest.seed_data import DEV_FINALISTS
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

    def test_import_finalists_and_open_voting_write_audit_log(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("admin_panel:dashboard"), {"action": "create_edition", "year": "2026"})

        response = self.client.post(
            reverse("admin_panel:dashboard"),
            {"action": "import_finalists", "finalists_csv": _finalists_csv()},
            follow=True,
        )

        edition = ContestEdition.objects.get(year=2026)
        self.assertContains(response, "Імпортовано фіналістів: 25")
        self.assertEqual(edition.entries.count(), 25)
        self.assertTrue(AdminAuditLog.objects.filter(action="import_finalists").exists())

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
        self.client.post(reverse("admin_panel:dashboard"), {"action": "import_finalists", "finalists_csv": _finalists_csv()})
        self.client.post(reverse("admin_panel:dashboard"), {"action": "open_voting"})

        edition = ContestEdition.objects.get(year=2026)
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

        self.client.post(reverse("admin_panel:dashboard"), {"action": "calculate_scores"})
        score = UserScore.objects.get(edition=edition, user=self.user, mode=Ballot.MODE_WITH_UKRAINE)
        self.assertEqual(score.exact_hits, 10)
        self.assertEqual(score.total_score, 20)

        self.client.post(reverse("admin_panel:dashboard"), {"action": "publish_scores"})
        edition.refresh_from_db()
        self.assertEqual(edition.state, ContestEdition.STATE_SCORES_PUBLISHED)


def _finalists_csv():
    lines = ["running_order,country_code,country_name,artist_name,song_title,is_ukraine"]
    for row in DEV_FINALISTS:
        lines.append(
            ",".join(
                [
                    str(row["running_order"]),
                    row["country_code"],
                    _csv_cell(row["country_name"]),
                    _csv_cell(row["artist_name"]),
                    _csv_cell(row["song_title"]),
                    "true" if row.get("is_ukraine") else "",
                ]
            )
        )
    return "\n".join(lines)


def _official_results_csv(edition):
    lines = ["final_rank,entry_id,country_name"]
    for rank, entry in enumerate(edition.entries.order_by("running_order"), start=1):
        lines.append(f"{rank},{entry.id},{_csv_cell(entry.country_name)}")
    return "\n".join(lines)


def _csv_cell(value):
    text = str(value)
    if any(char in text for char in [",", '"', "\n"]):
        return '"' + text.replace('"', '""') + '"'
    return text
