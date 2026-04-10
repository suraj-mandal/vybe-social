from django.test import TestCase

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.friendships.serializers import (
    FriendRequestSerializer,
    FriendSummarySerializer,
)


class TestFriendRequestSerializer(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
            first_name="Alice",
            last_name="Smith",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="TestPass123!",
            first_name="Bob",
            last_name="Jones",
        )

        self.request_obj: FriendRequest = FriendRequest.objects.create(
            sender=self.alice, receiver=self.bob
        )

    def test_serializes_friend_request(self):
        serializer = FriendRequestSerializer(self.request_obj)
        data = serializer.data

        assert data["id"] == str(self.request_obj.id)
        assert data["status"] == "pending"
        assert data["message"] == ""
        assert data["responded_at"] is None
        assert data["sender"]["username"] == "alice"
        assert data["sender"]["full_name"] == "Alice Smith"
        assert data["receiver"]["username"] == "bob"
        assert data["receiver"]["full_name"] == "Bob Jones"

    def test_serializes_message(self):
        self.request_obj.message = "Hey, let's connect!"
        self.request_obj.save()

        serializer = FriendRequestSerializer(self.request_obj)
        assert serializer.data["message"] == "Hey, let's connect!"

    def test_sender_contains_required_fields(self):
        serializer = FriendRequestSerializer(self.request_obj)
        sender = serializer.data["sender"]

        assert "id" in sender
        assert "username" in sender
        assert "full_name" in sender

    def test_receiver_contains_required_fields(self):
        serializer = FriendRequestSerializer(self.request_obj)
        receiver = serializer.data["receiver"]

        assert "id" in receiver
        assert "username" in receiver
        assert "full_name" in receiver

    def test_all_fields_are_read_only(self):
        serializer = FriendRequestSerializer()
        for field_name, field in serializer.fields.items():
            assert field.read_only, f"{field_name} should be read_only"


class TestFriendSummarySerializer(TestCase):
    def setUp(self):
        self.alice: User = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="TestPass123!",
            first_name="Alice",
            last_name="Smith",
        )

    def test_serializes_user_as_friend(self):
        serializer = FriendSummarySerializer(self.alice)
        data = serializer.data

        assert data["id"] == str(self.alice.id)
        assert data["username"] == "alice"
        assert data["full_name"] == "Alice Smith"

    def test_full_name_falls_back_to_email(self):
        user: User = User.objects.create_user(
            email="noname@example.com",
            username="noname",
            password="TestPass123!",
        )

        serializer = FriendSummarySerializer(user)
        assert serializer.data["full_name"] == "noname@example.com"
