import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.friendships.models import FriendRequest


class TestSendFriendRequestView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def test_send_friend_request(self):
        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending"
        assert response.data["message"] == ""
        assert response.data["sender"]["username"] == "alice"
        assert response.data["receiver"]["username"] == "bob"
        assert response.data["responded_at"] is None

        assert FriendRequest.objects.count() == 1

    def test_send_friend_request_with_message(self):
        response = self.client.post(
            f"/api/friends/request/{self.bob.id}/",
            {"message": "Hey bob, we met at pycon!!"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Hey bob, we met at pycon!!"
        assert FriendRequest.objects.count() == 1

    def test_message_is_truncated_at_300_chars(self):
        long_message = "a" * 500
        response = self.client.post(
            f"/api/friends/request/{self.bob.id}/",
            {"message": long_message},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["message"]) == 300

    def test_cannot_send_to_self(self):
        response = self.client.post(f"/api/friends/request/{self.alice.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in response.data["detail"].lower()

    def test_cannot_send_duplicate_pending(self):
        self.client.post(f"/api/friends/request/{self.bob.id}/")
        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pending" in response.data["detail"].lower()

    def test_cannot_send_if_already_friends(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
        )

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already friends" in response.data["detail"].lower()

    def test_cannot_send_when_reverse_pending_exists(self):
        FriendRequest.objects.create(sender=self.bob, receiver=self.alice)

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pending" in response.data["detail"].lower()

        assert FriendRequest.objects.count() == 1

    def test_cooldown_blocks_resend_within_period(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now(),
        )

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "try again" in response.data["detail"].lower()

    def test_decliner_can_send_freely(self):
        declined: FriendRequest = FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.bob)
        response = self.client.post(f"/api/friends/request/{self.alice.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["sender"]["username"] == "bob"
        assert response.data["receiver"]["username"] == "alice"

        # same row, updated - sender/receiver swapped
        assert FriendRequest.objects.count() == 1

        declined.refresh_from_db()

        # checking the status once again
        assert declined.status == FriendRequest.Status.PENDING
        assert declined.sender == self.bob
        assert declined.receiver == self.alice
        assert declined.responded_at is None

    def test_decliner_resend_ignores_permanent_block(self):
        """Even with permanent cooldown, the decliner can still send a request block"""
        self.alice.profile.friend_request_cooldown = 0
        self.alice.profile.save()

        FriendRequest.objects.create(
            sender=self.bob,
            receiver=self.alice,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now(),
        )

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["sender"]["username"] == "alice"
        assert response.data["receiver"]["username"] == "bob"
        assert response.data["status"] == "pending"
        assert response.data["responded_at"] is None

    def test_can_resend_after_cooldown_expires(self):
        """Can resend after cooldown has expired"""
        declined: FriendRequest = FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now() - timedelta(days=21),
        )

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED

        assert FriendRequest.objects.count() == 1

        declined.refresh_from_db()

        assert declined.status == FriendRequest.Status.PENDING
        assert declined.responded_at is None

    def test_permanent_cooldown_blocks_forever(self):
        self.bob.profile.friend_request_cooldown = 0
        self.bob.profile.save()

        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now() - timedelta(days=999),
        )

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "does not accept re-requests" in response.data["detail"].lower()

    def test_receiver_custom_cooldown_overrides_default(self):
        self.bob.profile.friend_request_cooldown = 5
        self.bob.profile.save()

        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now() - timedelta(days=6),
        )

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED

    def test_receiver_custom_cooldown_still_blocks_within_period(self):
        self.bob.profile.friend_request_cooldown = 30
        self.bob.profile.save()

        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now() - timedelta(days=25),
        )

        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_returns_404_for_nonexistent_user(self):
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/friends/request/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAcceptFriendRequestView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.friend_request: FriendRequest = FriendRequest.objects.create(
            sender=self.alice, receiver=self.bob
        )
        self.client.force_authenticate(user=self.bob)

    def test_accept_pending_request(self):
        response = self.client.post(
            f"/api/friends/accept/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "accepted"
        assert response.data["responded_at"] is not None

        self.friend_request.refresh_from_db()

        assert self.friend_request.status == FriendRequest.Status.ACCEPTED

    def test_only_receiver_can_accept(self):
        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/friends/accept/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_accept_non_pending_request(self):
        self.friend_request.status = FriendRequest.Status.ACCEPTED
        self.friend_request.save()

        response = self.client.post(
            f"/api/friends/accept/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_404_for_nonexistent_request(self):
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/friends/accept/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.post(f"/api/friends/accept/{self.bob.id}/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDeclineFriendRequestView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.friend_request: FriendRequest = FriendRequest.objects.create(
            sender=self.alice, receiver=self.bob
        )
        self.client.force_authenticate(user=self.bob)

    def test_decline_pending_request(self):
        response = self.client.post(
            f"/api/friends/decline/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "declined"
        assert response.data["responded_at"] is not None

        self.friend_request.refresh_from_db()

        assert self.friend_request.status == FriendRequest.Status.DECLINED

    def test_only_receiver_can_decline(self):
        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/friends/decline/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_decline_non_pending_request(self):
        self.friend_request.status = FriendRequest.Status.DECLINED
        self.friend_request.save()

        response = self.client.post(
            f"/api/friends/decline/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_404_for_nonexistent_request(self):
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/friends/decline/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.post(f"/api/friends/decline/{self.bob.id}/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCancelFriendRequestView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.friend_request: FriendRequest = FriendRequest.objects.create(
            sender=self.alice, receiver=self.bob
        )
        self.client.force_authenticate(user=self.alice)

    def test_cancel_pending_request(self):
        response = self.client.delete(
            f"/api/friends/cancel/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert FriendRequest.objects.count() == 0

    def test_only_sender_can_cancel(self):
        self.client.force_authenticate(user=self.bob)

        response = self.client.delete(
            f"/api/friends/cancel/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_cancel_non_pending_request(self):
        self.friend_request.status = FriendRequest.Status.ACCEPTED
        self.friend_request.save()

        response = self.client.delete(
            f"/api/friends/cancel/{self.friend_request.id}/"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUnfriendView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.friend_request: FriendRequest = FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
            responded_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.alice)

    def test_sender_can_unfriend(self):
        response = self.client.delete(f"/api/friends/{self.bob.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert FriendRequest.objects.count() == 0

    def test_receiver_can_unfriend(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.delete(f"/api/friends/{self.alice.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert FriendRequest.objects.count() == 0

    def test_cannot_unfriend_non_friend(self):
        charlie = User.objects.create_user(
            email="charlie@example.com",
            username="charlie",
            password="TestPass123!",
        )
        response = self.client.delete(f"/api/friends/{charlie.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_404_for_nonexistent_request(self):
        fake_id = uuid.uuid4()
        response = self.client.delete(f"/api/friends/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestFriendsListView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.charlie: User = User.objects.create_user(
            email="charlie@example.com",
            username="charlie",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def test_returns_accepted_friends(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
        )

        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.charlie,
            status=FriendRequest.Status.PENDING,
        )

        response = self.client.get("/api/friends/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["username"] == "bob"

    def test_returns_empty_list_when_no_friends(self):
        response = self.client.get("/api/friends/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_includes_friends_from_both_directions(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
        )

        FriendRequest.objects.create(
            sender=self.charlie,
            receiver=self.alice,
            status=FriendRequest.Status.ACCEPTED,
        )

        response = self.client.get("/api/friends/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        usernames = {f["username"] for f in response.data["results"]}
        assert usernames == {"bob", "charlie"}

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.get("/api/friends/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestPendingReceivedRequestsView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.charlie: User = User.objects.create_user(
            email="charlie@example.com",
            username="charlie",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def tests_returns_pending_requests_received(self):
        FriendRequest.objects.create(sender=self.bob, receiver=self.alice)
        FriendRequest.objects.create(sender=self.charlie, receiver=self.alice)

        response = self.client.get("/api/friends/requests/pending/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_excludes_sent_requests(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)

        response = self.client.get("/api/friends/requests/pending/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_excludes_accepted_requests(self):
        FriendRequest.objects.create(
            sender=self.bob,
            receiver=self.alice,
            status=FriendRequest.Status.ACCEPTED,
        )

        response = self.client.get("/api/friends/requests/pending/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


class TestPendingSentRequestsView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob: User = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def tests_returns_pending_requests_sent(self):
        FriendRequest.objects.create(receiver=self.bob, sender=self.alice)

        response = self.client.get("/api/friends/requests/sent/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["receiver"]["username"] == "bob"

    def test_excludes_received_requests(self):
        FriendRequest.objects.create(sender=self.bob, receiver=self.alice)

        response = self.client.get("/api/friends/requests/sent/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_excludes_accepted_requests(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
        )

        response = self.client.get("/api/friends/requests/sent/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
