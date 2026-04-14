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
