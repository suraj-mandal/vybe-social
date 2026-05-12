from apps.posts.mentions import extract_usernames, sync_mentions
from apps.posts.models import Comment
from apps.posts.tests._base import PostCommentTestBase


class TestExtractUsernames(PostCommentTestBase):
    def test_happy_path(self):
        assert extract_usernames("hi @alice and @bob") == [
            "alice",
            "bob",
        ]

    def test_dedupe_preserves_order(self):
        assert extract_usernames("hi @alice @bob @alice") == [
            "alice",
            "bob",
        ]

    def test_empty(self):
        assert extract_usernames("") == []

    def test_none_safe(self):
        assert extract_usernames(None) == []

    def test_no_mentions(self):
        assert extract_usernames("no mentions here") == []

    def test_case_preserved_in_extraction(self):
        assert extract_usernames("@Alice @BOB") == ["alice", "bob"]

    def test_adjacent_punctuation(self):
        assert extract_usernames("hi @alice! @bob.") == [
            "alice",
            "bob.",
        ]


class TestSyncMentions(PostCommentTestBase):
    def _make_comment(self, content: str) -> Comment:
        post = self._make_post()
        return Comment.objects.create(
            post=post, user=self.charlie, content=content
        )

    def test_creates_mention_for_existing_user(self):
        c: Comment = self._make_comment("hey @alice")
        sync_mentions(c)

        mentions = list(c.mentions.all())
        assert len(mentions) == 1
        assert mentions[0].user_id == self.alice.id

    def test_case_insensitive_user_lookup(self):
        c = self._make_comment("hey @ALICE")
        sync_mentions(c)

        mentions = list(c.mentions.all())
        assert len(mentions) == 1
        assert mentions[0].user_id == self.alice.id

    def test_unknown_username_silently_ignored(self):
        c = self._make_comment("hey @nobody here.")
        sync_mentions(c)

        assert c.mentions.count() == 0

    def test_mixed_known_and_unknown(self):
        c = self._make_comment("@alice @ghost @bob")
        sync_mentions(c)

        user_ids = set(c.mentions.values_list("user_id", flat=True))
        assert user_ids == {self.alice.id, self.bob.id}

    def test_idempotent_on_second_run(self):
        c = self._make_comment("@alice")
        sync_mentions(c)
        sync_mentions(c)

        assert c.mentions.count() == 1

    def test_removes_stale_mentions_on_content_change(self):
        c = self._make_comment("@alice")
        sync_mentions(c)

        c.content = "@bob"
        c.save()
        sync_mentions(c)

        user_ids = set(c.mentions.values_list("user_id", flat=True))
        assert user_ids == {self.bob.id}

    def test_self_mention_allowed(self):
        c = self._make_comment("@charlie talking to myself")
        sync_mentions(c)

        assert c.mentions.filter(user_id=self.charlie.id).exists()
