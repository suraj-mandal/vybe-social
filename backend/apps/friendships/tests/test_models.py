from django.db import IntegrityError
from django.db.models import QuerySet
from django.test import TestCase

from apps.accounts.models import User
from apps.friendships.models import FriendRequest, are_friends


class TestFriendRequestModel(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")
        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")
        self.charlie = User.objects.create_user(
            email="charlie@example.com", username="charlie", password="TestPass123!"
        )

    def test_create_friend_request(self):
        request: FriendRequest = FriendRequest.objects.create(sender=self.alice, receiver=self.bob)

        assert request.status == FriendRequest.Status.PENDING
        assert request.sender == self.alice
        assert request.receiver == self.bob
        assert request.message == ""
        assert request.responded_at is None

    def test_create_friend_request_with_message(self):
        greeting_message: str = "Hey Bob, we met yesterday at DjangoCon!!"

        request: FriendRequest = FriendRequest.objects.create(
            sender=self.alice, receiver=self.bob, message=greeting_message
        )

        assert request.message == greeting_message

    def test_str_representation(self):
        request: FriendRequest = FriendRequest.objects.create(sender=self.alice, receiver=self.bob)

        assert str(request) == f"{self.alice} -> {self.bob} (pending)"

    def test_unique_constraint_prevents_duplicate_request(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)

        with self.assertRaises(IntegrityError):
            FriendRequest.objects.create(sender=self.alice, receiver=self.bob)

    def test_reverse_request_blocked_at_db_level(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)

        with self.assertRaises(IntegrityError):
            FriendRequest.objects.create(sender=self.bob, receiver=self.alice)

    def test_check_constraint_prevents_self_request(self):
        with self.assertRaises(IntegrityError):
            FriendRequest.objects.create(sender=self.alice, receiver=self.alice)

    def test_cascade_delete_sender(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        self.alice.delete()

        assert FriendRequest.objects.count() == 0

    def test_cascade_delete_receiver(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        self.bob.delete()

        assert FriendRequest.objects.count() == 0

    def test_related_name_sent_requests(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        FriendRequest.objects.create(sender=self.alice, receiver=self.charlie)

        assert self.alice.sent_friend_requests.count() == 2
        assert self.bob.sent_friend_requests.count() == 0
        assert self.charlie.sent_friend_requests.count() == 0

    def test_related_name_received_requests(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob)
        FriendRequest.objects.create(sender=self.charlie, receiver=self.bob)
        FriendRequest.objects.create(sender=self.charlie, receiver=self.alice)

        assert self.alice.received_friend_requests.count() == 1
        assert self.charlie.received_friend_requests.count() == 0
        assert self.bob.received_friend_requests.count() == 2


class TestFriendRequestManager(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")
        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")
        self.charlie = User.objects.create_user(
            email="charlie@example.com", username="charlie", password="TestPass123!"
        )
        self.dave = User.objects.create_user(email="dave@example.com", username="dave", password="TestPass123!")

    def test_are_friends_returns_true_for_accepted_request(self):
        FriendRequest.objects.create(sender=self.alice, receiver=self.bob, status=FriendRequest.Status.ACCEPTED)

        assert FriendRequest.objects.are_friends(self.alice, self.bob) is True

    def test_are_friends_is_bidirectional(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
        )

        assert FriendRequest.objects.are_friends(self.alice, self.bob) is True
        assert FriendRequest.objects.are_friends(self.bob, self.alice) is True

    def test_are_friends_returns_false_for_pending(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.PENDING,
        )

        assert FriendRequest.objects.are_friends(self.alice, self.bob) is False

    def test_are_friends_returns_false_for_declined(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.DECLINED,
        )

        assert FriendRequest.objects.are_friends(self.alice, self.bob) is False

    def test_are_friends_returns_false_for_no_request(self):
        assert FriendRequest.objects.are_friends(self.alice, self.bob) is False

    def test_friends_of_returns_all_friends(self):
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

        FriendRequest.objects.create(
            sender=self.dave,
            receiver=self.alice,
            status=FriendRequest.Status.PENDING,
        )

        friends: QuerySet = FriendRequest.objects.friends_of(self.alice)
        friend_ids = set(friends.values_list("id", flat=True))

        assert friend_ids == {self.bob.id, self.charlie.id}
        assert self.dave.id not in friend_ids

    def friends_of_returns_empty_for_no_friends(self):
        friends: QuerySet = FriendRequest.objects.friends_of(self.alice)
        assert friends.count() == 0

    def test_pending_received(self):
        FriendRequest.objects.create(sender=self.bob, receiver=self.alice)
        FriendRequest.objects.create(sender=self.charlie, receiver=self.alice)
        FriendRequest.objects.create(sender=self.dave, receiver=self.alice, status=FriendRequest.Status.ACCEPTED)

        pending: QuerySet = FriendRequest.objects.pending_received(self.alice)
        assert pending.count() == 2

    def test_pending_sent(self):
        FriendRequest.objects.create(receiver=self.bob, sender=self.alice)
        FriendRequest.objects.create(receiver=self.charlie, sender=self.alice)
        FriendRequest.objects.create(sender=self.dave, receiver=self.alice, status=FriendRequest.Status.ACCEPTED)

        pending: QuerySet = FriendRequest.objects.pending_sent(self.alice)
        assert pending.count() == 2


class TestAreFriendsConvenience(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")
        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")

    def test_convenience_function_works(self):
        FriendRequest.objects.create(
            sender=self.alice,
            receiver=self.bob,
            status=FriendRequest.Status.ACCEPTED,
        )

        assert are_friends(self.alice, self.bob) is True

    def test_convenience_function_returns_false(self):
        assert are_friends(self.alice, self.bob) is False
