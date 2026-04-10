import uuid

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.moderation.models import Block, Mute


class TestBlockUserView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com", username="bob", password="TestPass123!"
        )
        self.client.force_authenticate(user=self.alice)

    def test_block_user(self):
        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert Block.objects.count() == 1
        assert Block.objects.is_blocked(self.alice, self.bob) is True

    def test_block_removes_accepted_friendship(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
            responded_at=timezone.now(),
        )

        # now Alice blocks Bob
        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert FriendRequest.objects.count() == 0

    def test_block_removes_pending_friend_request(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
        )

        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert FriendRequest.objects.count() == 0

    def test_block_removes_reverse_pending_friend_request(self):
        FriendRequest.objects.create(
            sender=self.bob,
            receiver=self.alice,
        )

        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert FriendRequest.objects.count() == 0

    def test_block_removes_declined_friend_request(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
            responded_at=timezone.now(),
        )

        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert FriendRequest.objects.count() == 0

    def test_cannot_block_self(self):
        response = self.client.post(f"/api/moderation/blocks/{self.alice.id}/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_block_already_blocked_user(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already blocked" in response.data["detail"].lower()

    def test_block_user_who_is_not_friend(self):
        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert Block.objects.count() == 1

    def test_returns_404_for_nonexistent_user(self):
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/moderation/blocks/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.post(f"/api/moderation/blocks/{self.bob.id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUnblockUserView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self.client.force_authenticate(user=self.alice)

    def test_unblock_user(self):
        # unblock bob
        response = self.client.delete(
            f"/api/moderation/blocks/{self.bob.id}/unblock/"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Block.objects.count() == 0

    def test_blocked_user_cannot_unblock(self):
        self.client.force_authenticate(user=self.bob)

        # Bob tries to unblock the block that Alice imposed, so he tries the other
        # way round, which is not possible
        response = self.client.delete(
            f"/api/moderation/blocks/{self.alice.id}/unblock/"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not blocked" in response.data["detail"].lower()

    def test_unblock_user_not_blocked(self):
        charlie = User.objects.create_user(
            email="charlie@example.com",
            username="charlie",
            password="TestPass123!",
        )
        response = self.client.delete(
            f"/api/moderation/blocks/{charlie.id}/unblock/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.delete(
            f"/api/moderation/blocks/{self.bob.id}/unblock/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestBlockedUsersListView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.charlie = User.objects.create_user(
            email="charlie@example.com",
            username="charlie",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def test_returns_blocked_users(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        Block.objects.create(blocker=self.alice, blocked=self.charlie)

        response = self.client.get("/api/moderation/blocks/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_excludes_blocks_by_others(self):
        Block.objects.create(blocker=self.bob, blocked=self.alice)

        response = self.client.get("/api/moderation/blocks/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_returns_empty_when_no_blocks(self):
        response = self.client.get("/api/moderation/blocks/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.get("/api/moderation/blocks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMuteUserView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def test_mute_user(self):
        response = self.client.post(f"/api/moderation/mutes/{self.bob.id}/")

        assert response.status_code == status.HTTP_201_CREATED
        assert Mute.objects.count() == 1
        assert Mute.objects.is_muted(self.alice, self.bob) is True

    def test_cannot_mute_self(self):
        response = self.client.post(f"/api/moderation/mutes/{self.alice.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in response.data["detail"].lower()

    def test_cannot_mute_already_muted_user(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)

        # trying to mute again
        response = self.client.post(f"/api/moderation/mutes/{self.bob.id}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already muted" in response.data["detail"].lower()

    def test_returns_404_for_nonexistent_user(self):
        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/moderation/mutes/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.post(f"/api/moderation/mutes/{self.bob.id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUnmuteUserView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        Mute.objects.create(muter=self.alice, muted=self.bob)
        self.client.force_authenticate(user=self.alice)

    def test_unmute_user(self):
        response = self.client.delete(
            f"/api/moderation/mutes/{self.bob.id}/unmute/"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Mute.objects.count() == 0

    def test_muted_user_cannot_unmute(self):
        self.client.force_authenticate(user=self.bob)

        response = self.client.delete(
            f"/api/moderation/mutes/{self.alice.id}/unmute/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unmute_user_cannot_be_unmuted(self):
        charlie = User.objects.create_user(
            email="charlie@example.com",
            password="TestPass123!",
            username="charlie",
        )

        response = self.client.delete(
            f"/api/moderation/mutes/{charlie.id}/unmute/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.delete(
            f"/api/moderation/mutes/{self.bob.id}/unmute/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMutedUsersListView(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.charlie = User.objects.create_user(
            email="charlie@example.com",
            username="charlie",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def test_returns_muted_users(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        Mute.objects.create(muter=self.alice, muted=self.charlie)

        response = self.client.get("/api/moderation/mutes/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_excludes_mutes_by_others(self):
        Mute.objects.create(muter=self.bob, muted=self.alice)

        response = self.client.get("/api/moderation/mutes/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_returns_empty_when_no_mutes(self):
        response = self.client.get("/api/moderation/mutes/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_requires_authentication(self):
        self.client.force_authenticate()
        response = self.client.get("/api/moderation/mutes/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Testing integration with friend requests
class TestBlockIntegrationWithFriendRequests(TestCase):
    def setUp(self):
        self.client: APIClient = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
        )
        self.client.force_authenticate(user=self.alice)

    def test_blocked_cannot_send_friend_request_to_blocker(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        # Bob tries to send Alice friend request
        self.client.force_authenticate(user=self.bob)
        response = self.client.post(f"/api/friends/request/{self.alice.id}/")

        # The user will not be seen anymore.
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_blocker_cannot_send_friend_request_to_blocked(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        # Alice tries to send friend request to bob
        response = self.client.post(f"/api/friends/request/{self.bob.id}/")

        # The user will not be seen anymore.
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_can_send_friend_request_after_unblock(self):
        block = Block.objects.create(blocker=self.alice, blocked=self.bob)
        block.delete()

        # after unblock, bob tries to send friend request to alice
        self.client.force_authenticate(user=self.bob)
        response = self.client.post(f"/api/friends/request/{self.alice.id}/")

        assert response.status_code == status.HTTP_201_CREATED
