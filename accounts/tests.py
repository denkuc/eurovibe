from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .roles import is_superadmin


class AccountsTests(TestCase):
    def test_register_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "sofia",
                "password1": "very-long-passphrase",
                "password2": "very-long-passphrase",
            },
        )

        self.assertRedirects(response, reverse("groups:list"))
        self.assertTrue(get_user_model().objects.filter(username="sofia").exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), get_user_model().objects.get(username="sofia").id)

    def test_register_rejects_duplicate_username(self):
        get_user_model().objects.create_user(username="sofia", password="very-long-passphrase")

        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "sofia",
                "password1": "another-long-passphrase",
                "password2": "another-long-passphrase",
            },
        )

        self.assertEqual(response.status_code, 200)
        username_errors = response.context["form"].errors.as_data()["username"]
        self.assertEqual(username_errors[0].code, "unique")

    def test_register_rejects_short_password(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "shortpass",
                "password1": "too-short",
                "password2": "too-short",
            },
        )

        self.assertEqual(response.status_code, 200)
        password_errors = response.context["form"].errors.as_data()["password2"]
        self.assertEqual(password_errors[0].code, "password_too_short")

    def test_login_logout_flow(self):
        get_user_model().objects.create_user(username="maks", password="very-long-passphrase")

        login_response = self.client.post(
            reverse("accounts:login"),
            {"username": "maks", "password": "very-long-passphrase"},
        )
        self.assertRedirects(login_response, reverse("groups:list"))

        logout_response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(logout_response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_private_dashboard_redirects_to_login_with_next(self):
        response = self.client.get(reverse("accounts:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:dashboard')}",
            fetch_redirect_response=False,
        )

    def test_login_honors_safe_next(self):
        get_user_model().objects.create_user(username="maks", password="very-long-passphrase")

        response = self.client.post(
            f"{reverse('accounts:login')}?next=/accounts/dashboard/",
            {"username": "maks", "password": "very-long-passphrase"},
        )

        self.assertRedirects(response, reverse("accounts:dashboard"))

    def test_is_superadmin_helper(self):
        user = get_user_model().objects.create_user(username="regular")
        denkuc = get_user_model().objects.create_user(username="denkuc")
        staff = get_user_model().objects.create_user(username="staff", is_staff=True)

        self.assertFalse(is_superadmin(user))
        self.assertTrue(is_superadmin(denkuc))
        self.assertTrue(is_superadmin(staff))

    def test_superadmin_placeholder_requires_superadmin_role(self):
        regular = get_user_model().objects.create_user(username="regular", password="very-long-passphrase")
        self.client.force_login(regular)
        response = self.client.get(reverse("accounts:superadmin_dashboard"))
        self.assertEqual(response.status_code, 403)

        denkuc = get_user_model().objects.create_user(username="denkuc", password="very-long-passphrase")
        self.client.force_login(denkuc)
        response = self.client.get(reverse("accounts:superadmin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Superadmin placeholder")
