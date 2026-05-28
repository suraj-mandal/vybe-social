from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.profiles.models import Profile


class TestGenderUpdateOnProfile(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )

        self.client: APIClient = APIClient()

    def _auth(self, user: User | None):
        self.client.force_authenticate(user=user)

    def test_update_profile_with_valid_gender_returns_200(self):
        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {"gender": "female"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["gender"] == "female"
        assert response.data["username"] == "alice"

        # checking if the profile was updated as well
        alice_profile: Profile = self.alice.profile

        # refresh the database
        alice_profile.refresh_from_db()

        assert alice_profile.gender == "female"

        # the response now exposes the first name and the last name fields as well
        # let us see if we can see them or not
        assert response.data["first_name"] == ""
        assert response.data["last_name"] == ""
        assert response.data["onboarding_complete"] is False

    def test_update_profile_with_invalid_choice_returns_400(self):
        self._auth(user=self.alice)

        response = self.client.patch(
            "/api/profiles/me/",
            {"gender": "invalid"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_should_not_patch_gender_without_authentication(self):
        response = self.client.patch(
            "/api/profiles/me/",
            {"gender": "invalid"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        self.alice.refresh_from_db()

        assert self.alice.profile.gender != "invalid"


class TestProfileOnboardingAndMeEndpoint(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )

        self.client: APIClient = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_new_profile_defaults_to_onboarding_incomplete(self):
        assert self.alice.profile.onboarding_complete is False

    def test_patch_first_name_writes_through_to_user(self):
        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {"first_name": "Alice"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "Alice"

        self.alice.refresh_from_db()

        assert self.alice.first_name == "Alice"

    def test_patch_first_and_last_name_updates_both_fields(self):
        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {"first_name": "Alice", "last_name": "Walker"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "Alice"

        self.alice.refresh_from_db()

        assert self.alice.first_name == "Alice"
        assert self.alice.last_name == "Walker"

    def test_patch_combines_user_and_profile_fields_atomically(self):
        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {
                "first_name": "Alice",
                "bio": "Hello from the test suite",
                "onboarding_complete": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        self.alice.refresh_from_db()
        alice_profile = self.alice.profile

        alice_profile.refresh_from_db()

        assert self.alice.first_name == "Alice"
        assert alice_profile.bio == "Hello from the test suite"
        assert alice_profile.onboarding_complete is True

    def test_patch_blank_first_name_is_allowed(self):
        self.alice.first_name = "Alice"
        self.alice.save(update_fields=["first_name"])

        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {"first_name": ""},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        self.alice.refresh_from_db()

        assert self.alice.first_name == ""

    def test_username_remains_read_only(self):
        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {
                "username": "hacker",
                "bio": "ok",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        self.alice.refresh_from_db()

        assert self.alice.username == "alice"  # should remain unchanged

    def test_patch_onboarding_complete_persists(self):
        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {"onboarding_complete": True},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["onboarding_complete"] is True

        self.alice.profile.refresh_from_db()
        assert self.alice.profile.onboarding_complete is True

    def test_patch_without_onboarding_field_does_not_change_it(self):
        self.alice.profile.onboarding_complete = True
        self.alice.profile.save(update_fields=["onboarding_complete"])

        self._auth(user=self.alice)
        response = self.client.patch(
            "/api/profiles/me/",
            {"bio": "changing bio only"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        self.alice.profile.refresh_from_db()

        assert self.alice.profile.onboarding_complete is True

    def test_explicit_onboarding_complete_set_to_false_does_not_revert_onboarding_status(
        self,
    ):
        self.alice.profile.onboarding_complete = True
        self.alice.profile.save(update_fields=["onboarding_complete"])

        self._auth(user=self.alice)

        response = self.client.patch(
            "/api/profiles/me/",
            {"onboarding_complete": False},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["onboarding_complete"] is True

        self.alice.refresh_from_db()

        assert self.alice.profile.onboarding_complete is True
