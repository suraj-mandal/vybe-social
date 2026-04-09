from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.moderation.models import Block, Mute, is_blocked, is_either_blocked, is_muted


class TestBlockModel(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")
        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")
        self.charlie = User.objects.create_user(
            email="charlie@example.com", username="charlie", password="TestPass123!"
        )

    def test_create_block(self):
        """Testing block created between two users"""
        block = Block.objects.create(blocker=self.alice, blocked=self.bob)

        assert block.blocker == self.alice
        assert block.blocked == self.bob
        assert block.created_at is not None

    def test_str_representation(self):
        block = Block.objects.create(
            blocker=self.alice,
            blocked=self.bob,
        )

        assert str(block) == f"{self.alice} blocked {self.bob}"

    def test_unique_constraint_prevents_duplicate_block(self):
        """cannot block the same user twice"""
        Block.objects.create(
            blocker=self.alice,
            blocked=self.bob,
        )

        with self.assertRaises(IntegrityError):
            Block.objects.create(
                blocker=self.alice,
                blocked=self.bob,
            )

    def test_reverse_block_is_allowed(self):
        Block.objects.create(
            blocker=self.alice,
            blocked=self.bob,
        )
        reverse = Block.objects.create(blocker=self.bob, blocked=self.alice)

        assert reverse.blocker == self.bob
        assert Block.objects.count() == 2

    def test_check_constraint_prevents_self_block(self):
        with self.assertRaises(IntegrityError):
            Block.objects.create(blocker=self.alice, blocked=self.alice)

    def test_cascade_delete_blocked(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self.bob.delete()

        assert Block.objects.count() == 0

    def test_related_name_blocks_given(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        Block.objects.create(blocker=self.alice, blocked=self.charlie)

        assert self.alice.blocks_given.count() == 2
        assert self.bob.blocks_given.count() == 0
        assert self.charlie.blocks_given.count() == 0

    def test_related_name_blocks_received(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        Block.objects.create(blocker=self.charlie, blocked=self.bob)

        assert self.bob.blocks_received.count() == 2
        assert self.alice.blocks_received.count() == 0


class TestBlockManager(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")
        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")
        self.charlie = User.objects.create_user(
            email="charlie@example.com", username="charlie", password="TestPass123!"
        )

    def test_is_blocked_returns_true(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        assert Block.objects.is_blocked(self.alice, self.bob) is True

    def test_is_blocked_is_directional(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        assert Block.objects.is_blocked(self.alice, self.bob) is True
        assert Block.objects.is_blocked(self.bob, self.alice) is False

    def test_is_blocked_returns_false_when_no_block(self):
        assert Block.objects.is_blocked(self.alice, self.bob) is False

    def test_is_either_blocked_forward(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        assert Block.objects.is_either_blocked(self.alice, self.bob) is True

    def test_is_either_blocked_reverse(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        assert Block.objects.is_either_blocked(self.bob, self.alice) is True

    def test_is_either_blocked_returns_false(self):
        assert Block.objects.is_either_blocked(self.bob, self.alice) is False

    def test_blocked_user_ids(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        Block.objects.create(blocker=self.alice, blocked=self.charlie)

        ids = Block.objects.blocked_user_ids(self.alice)
        assert ids == {self.bob.id, self.charlie.id}

    def test_blocked_user_ids_empty(self):
        ids = Block.objects.blocked_user_ids(self.alice)
        assert ids == set()

    def test_blocked_by_user_ids(self):
        Block.objects.create(blocked=self.alice, blocker=self.bob)
        Block.objects.create(blocked=self.alice, blocker=self.charlie)

        ids = Block.objects.blocked_by_user_ids(self.alice)
        assert ids == {self.bob.id, self.charlie.id}


class TestMuteModel(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")

        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")

    def test_create_mute(self):
        mute = Mute.objects.create(
            muter=self.alice,
            muted=self.bob,
        )

        assert mute.muter == self.alice
        assert mute.muted == self.bob
        assert mute.created_at is not None
        assert Mute.objects.count() == 1

    def test_str_representation(self):
        mute = Mute.objects.create(
            muter=self.alice,
            muted=self.bob,
        )

        assert str(mute) == f"{self.alice} muted {self.bob}"

    def test_unique_constraint_prevents_duplicate_mute(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)

        with self.assertRaises(IntegrityError):
            Mute.objects.create(muter=self.alice, muted=self.bob)

    def test_reverse_mute_is_allowed(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)

        Mute.objects.create(muter=self.bob, muted=self.alice)

        assert Mute.objects.count() == 2

    def test_check_constraint_prevents_self_mute(self):
        with self.assertRaises(IntegrityError):
            Mute.objects.create(
                muter=self.alice,
                muted=self.alice,
            )

    def test_cascade_delete_muter(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        self.alice.delete()

        assert Mute.objects.count() == 0

    def test_cascade_delete_muted(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        self.bob.delete()

        assert Mute.objects.count() == 0

    def test_related_name_mutes_given(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        assert self.alice.mutes_given.count() == 1
        assert self.bob.mutes_given.count() == 0

    def test_related_names_mutes_received(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        assert self.alice.mutes_received.count() == 0
        assert self.bob.mutes_received.count() == 1


class TestMuteManager(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")
        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")
        self.charlie = User.objects.create_user(
            email="charlie@example.com", username="charlie", password="TestPass123!"
        )

    def test_is_muted_returns_true(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        assert Mute.objects.is_muted(self.alice, self.bob) is True

    def test_is_muted_is_directional(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)

        assert Mute.objects.is_muted(self.alice, self.bob) is True
        assert Mute.objects.is_muted(self.bob, self.alice) is False

    def test_is_muted_returns_false(self):
        assert Mute.objects.is_muted(self.alice, self.bob) is False

    def test_muted_user_ids(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        Mute.objects.create(muter=self.alice, muted=self.charlie)

        ids = Mute.objects.muted_user_ids(self.alice)
        assert ids == {self.bob.id, self.charlie.id}

    def test_muted_user_ids_empty(self):
        ids = Mute.objects.muted_user_ids(self.alice)
        assert ids == set()


class TestConvenienceFunctions(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email="alice@example.com", username="alice", password="TestPass123!")

        self.bob = User.objects.create_user(email="bob@example.com", username="bob", password="TestPass123!")

    def test_is_blocked_convenience(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        assert is_blocked(self.alice, self.bob) is True
        assert is_blocked(self.bob, self.alice) is False

    def test_is_either_blocked_convenience(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        assert is_either_blocked(self.alice, self.bob) is True
        assert is_either_blocked(self.bob, self.alice) is True

    def test_is_muted_convenience(self):
        Mute.objects.create(muter=self.alice, muted=self.bob)
        assert is_muted(self.alice, self.bob) is True
        assert is_muted(self.bob, self.alice) is False
