from django.test import TestCase

from apps.accounts.models import User
from apps.moderation.models import Block, Mute
from apps.moderation.serializers import (
    BlockedUserSerializer,
    MutedUserSerializer,
)


class TestBlockedUserSerializer(TestCase):
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
            last_name="Panda",
        )

        self.block = Block.objects.create(
            blocker=self.alice,
            blocked=self.bob,
        )

    def test_serializer_block(self):
        serializer = BlockedUserSerializer(self.block)
        data = serializer.data

        assert data["id"] == str(self.block.id)
        assert data["created_at"] is not None
        assert data["blocked_user"]["username"] == "bob"
        assert data["blocked_user"]["full_name"] == "Bob Panda"
        assert data["blocked_user"]["id"] == str(self.bob.id)

    def test_blocked_user_contains_required_fields(self):
        serializer = BlockedUserSerializer(self.block)
        blocked_user = serializer.data["blocked_user"]

        assert "id" in blocked_user
        assert "username" in blocked_user
        assert "full_name" in blocked_user

    def test_all_fields_are_read_only(self):
        serializer = BlockedUserSerializer(self.block)
        for field_name, field in serializer.fields.items():
            assert field.read_only, f"{field_name} should be read_only"


class TestMutedUserSerializer(TestCase):
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
            last_name="Panda",
        )

        self.mute = Mute.objects.create(
            muter=self.alice,
            muted=self.bob,
        )

    def test_serializes_mute(self):
        serializer = MutedUserSerializer(self.mute)
        data = serializer.data

        assert data["id"] == str(self.mute.id)
        assert data["created_at"] is not None
        assert data["muted_user"]["username"] == "bob"
        assert data["muted_user"]["full_name"] == "Bob Panda"
        assert data["muted_user"]["id"] == str(self.bob.id)

    def test_muted_user_contains_required_fields(self):
        serializer = MutedUserSerializer(self.mute)
        muted_user = serializer.data["muted_user"]

        assert "id" in muted_user
        assert "username" in muted_user
        assert "full_name" in muted_user

    def test_all_fields_are_read_only(self):
        serializer = MutedUserSerializer(self.mute)
        for field_name, field in serializer.fields.items():
            assert field.read_only, f"{field_name} should be read_only"
