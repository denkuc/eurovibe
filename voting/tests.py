from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from contest.models import ContestEdition, ContestEntry
from groups.services import create_group

from .models import ALLOWED_POINTS, Ballot, BallotItem
from .services import get_available_voting_modes, submit_ballot


class VotingDomainTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sofia", password="very-long-passphrase")
        self.other = get_user_model().objects.create_user(username="maks", password="very-long-passphrase")
        self.edition = ContestEdition.objects.create(year=2026)
        self.entries = [
            ContestEntry.objects.create(
                edition=self.edition,
                running_order=index,
                country_name=f"Country {index}",
                country_code=f"C{index}"[-3:],
                artist_name=f"Artist {index}",
                song_title=f"Song {index}",
                is_ukraine=False,
            )
            for index in range(1, 25)
        ]
        self.ukraine = ContestEntry.objects.create(
            edition=self.edition,
            running_order=25,
            country_name="Ukraine",
            country_code="UA",
            artist_name="Northern Heart",
            song_title="Ridne Svitlo",
            is_ukraine=True,
        )

    def open_voting(self):
        self.edition.open_voting()
        self.edition.save()

    def assignments(self, entries=None):
        selected_entries = entries or self.entries[:10]
        return list(zip(ALLOWED_POINTS, [entry.id for entry in selected_entries]))

    def test_available_modes_follow_user_group_memberships(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        create_group(owner=self.user, name="Without", includes_ukraine=False)

        modes = get_available_voting_modes(self.user, self.edition)

        self.assertEqual(modes, [Ballot.MODE_WITH_UKRAINE, Ballot.MODE_WITHOUT_UKRAINE])
        self.assertEqual(get_available_voting_modes(self.other, self.edition), [])

    def test_submit_ballot_creates_immutable_complete_ballot(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        self.open_voting()

        ballot = submit_ballot(
            user=self.user,
            edition=self.edition,
            mode=Ballot.MODE_WITH_UKRAINE,
            assignments=self.assignments(),
        )

        self.assertTrue(ballot.immutable)
        self.assertIsNotNone(ballot.submitted_at)
        self.assertEqual(ballot.items.count(), 10)
        self.assertTrue(ballot.is_complete)

    def test_duplicate_submit_for_same_user_mode_is_rejected(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        self.open_voting()
        submit_ballot(
            user=self.user,
            edition=self.edition,
            mode=Ballot.MODE_WITH_UKRAINE,
            assignments=self.assignments(),
        )

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITH_UKRAINE,
                assignments=self.assignments(self.entries[10:20]),
            )

    def test_submit_is_rejected_outside_voting_open(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITH_UKRAINE,
                assignments=self.assignments(),
            )

        self.open_voting()
        self.edition.close_voting()
        self.edition.save()

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITH_UKRAINE,
                assignments=self.assignments(),
            )

    def test_submit_requires_user_access_to_mode(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        self.open_voting()

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITHOUT_UKRAINE,
                assignments=self.assignments(),
            )

    def test_submit_rejects_incomplete_duplicate_or_unknown_points(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        self.open_voting()

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITH_UKRAINE,
                assignments=self.assignments()[:9],
            )

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITH_UKRAINE,
                assignments=[(1, self.entries[0].id), (1, self.entries[1].id)] + self.assignments(self.entries[2:10]),
            )

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITH_UKRAINE,
                assignments=[(9, self.entries[0].id)] + self.assignments(self.entries[1:10]),
            )

    def test_submit_rejects_entries_from_other_edition(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        other_edition = ContestEdition.objects.create(year=2027)
        other_entry = ContestEntry.objects.create(
            edition=other_edition,
            running_order=1,
            country_name="Other",
            country_code="OT",
            artist_name="Other Artist",
            song_title="Other Song",
        )
        self.open_voting()

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITH_UKRAINE,
                assignments=[(1, other_entry.id)] + list(zip(ALLOWED_POINTS[1:], [entry.id for entry in self.entries[:9]])),
            )

    def test_without_ukraine_rejects_ukraine_item(self):
        create_group(owner=self.user, name="Without", includes_ukraine=False)
        self.open_voting()

        with self.assertRaises(ValidationError):
            submit_ballot(
                user=self.user,
                edition=self.edition,
                mode=Ballot.MODE_WITHOUT_UKRAINE,
                assignments=[(1, self.ukraine.id)] + list(zip(ALLOWED_POINTS[1:], [entry.id for entry in self.entries[:9]])),
            )

    def test_ballot_item_model_rejects_ukraine_in_without_ukraine(self):
        create_group(owner=self.user, name="Without", includes_ukraine=False)
        self.open_voting()
        ballot = Ballot.objects.create(edition=self.edition, user=self.user, mode=Ballot.MODE_WITHOUT_UKRAINE)

        with self.assertRaises(ValidationError):
            BallotItem.objects.create(ballot=ballot, points=12, contest_entry=self.ukraine)


class VotingViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="olena", password="very-long-passphrase")
        self.edition = ContestEdition.objects.create(year=2026)
        self.entries = [
            ContestEntry.objects.create(
                edition=self.edition,
                running_order=index,
                country_name=f"Country {index}",
                country_code="FR",
                artist_name=f"Artist {index}",
                song_title=f"Song {index}",
            )
            for index in range(1, 25)
        ]
        self.ukraine = ContestEntry.objects.create(
            edition=self.edition,
            running_order=25,
            country_name="Ukraine",
            country_code="UA",
            artist_name="Northern Heart",
            song_title="Ridne Svitlo",
            is_ukraine=True,
        )

    def open_voting(self):
        self.edition.open_voting()
        self.edition.save()

    def post_data(self, mode=Ballot.MODE_WITH_UKRAINE, entries=None):
        selected_entries = entries or self.entries[:10]
        data = {"mode": mode}
        for points, entry in zip(ALLOWED_POINTS, selected_entries):
            data[f"points_{points}"] = str(entry.id)
        return data

    def test_voting_page_requires_login(self):
        response = self.client.get(reverse("voting:index"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('voting:index')}",
            fetch_redirect_response=False,
        )

    def test_voting_page_shows_modes_and_without_ukraine_state(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        create_group(owner=self.user, name="Without", includes_ukraine=False)
        self.open_voting()
        self.client.force_login(self.user)

        response = self.client.get(f"{reverse('voting:index')}?mode={Ballot.MODE_WITHOUT_UKRAINE}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "З Україною")
        self.assertContains(response, "Без України")
        self.assertContains(response, "vote-entry-ukraine locked")
        self.assertContains(response, "♥")
        self.assertContains(response, "Sortable.min.js")

    def test_post_submits_and_then_renders_readonly_ballot(self):
        create_group(owner=self.user, name="With", includes_ukraine=True)
        self.open_voting()
        self.client.force_login(self.user)

        response = self.client.post(reverse("voting:index"), self.post_data())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Ballot.objects.filter(user=self.user, edition=self.edition, mode=Ballot.MODE_WITH_UKRAINE).exists())

        response = self.client.get(reverse("voting:index"))

        self.assertContains(response, "Бюлетень підтверджено")
        self.assertContains(response, "Змінити бюлетень неможливо")

    def test_no_mode_access_renders_empty_state(self):
        self.open_voting()
        self.client.force_login(self.user)

        response = self.client.get(reverse("voting:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Немає доступного режиму")
