from django.conf import settings

from apps.posts.models import Comment
from apps.posts.selectors import comments_for_post, replies_for_comment
from apps.posts.tests._base import PostCommentTestBase


class TestCommentsForPost(PostCommentTestBase):
    def test_only_top_level(self):
        post = self._make_post()
        parent = Comment.objects.create(user=self.bob, post=post, content="p")
        Comment.objects.create(
            post=post,
            user=self.alice,
            content="r",
            parent=parent,
        )

        qs = comments_for_post(self.bob, post)
        assert list(qs.values_list("pk", flat=True)) == [parent.pk]

    def test_newest_first(self):
        post = self._make_post()
        a = Comment.objects.create(post=post, user=self.bob, content="first")
        b = Comment.objects.create(post=post, user=self.alice, content="second")

        ordered = list(
            comments_for_post(self.bob, post).values_list("pk", flat=True)
        )
        assert ordered == [b.pk, a.pk]

    def test_excludes_soft_deleted(self):
        post = self._make_post()
        keep = Comment.objects.create(post=post, user=self.bob, content="keep")
        gone = Comment.objects.create(
            post=post, user=self.alice, content="gone"
        )

        gone.delete()

        ids = set(
            comments_for_post(self.bob, post).values_list("pk", flat=True)
        )
        assert ids == {keep.pk}

    def test_inline_replies_capped(self):
        post = self._make_post()
        parent = Comment.objects.create(post=post, user=self.bob, content="p")
        # create more replies than the inline preview cap
        total_replies = settings.REPLIES_INLINE_PREVIEW + 5

        for i in range(total_replies):
            Comment.objects.create(
                post=post,
                user=self.alice,
                parent=parent,
                content=f"r{i}",
            )

        row: Comment = comments_for_post(self.bob, post).get(pk=parent.pk)
        prefetched = list(row.replies.all())

        assert len(prefetched) == settings.REPLIES_INLINE_PREVIEW
        assert row.replies_count == total_replies

    def test_inline_replies_newest_first(self):
        post = self._make_post()
        parent = Comment.objects.create(post=post, user=self.bob, content="p")

        first = Comment.objects.create(
            post=post,
            user=self.alice,
            content="1",
            parent=parent,
        )

        second = Comment.objects.create(
            post=post,
            user=self.alice,
            content="2",
            parent=parent,
        )

        row: Comment = comments_for_post(self.bob, post).get(pk=parent.pk)
        ordered = [r.pk for r in row.replies.all()]
        assert ordered.index(second.pk) < ordered.index(first.pk)


class TestRepliesForComment(PostCommentTestBase):
    def test_only_direct_children(self):
        post = self._make_post()
        p1 = Comment.objects.create(post=post, user=self.bob, content="p1")
        p2 = Comment.objects.create(post=post, user=self.bob, content="p2")

        r1: Comment = Comment.objects.create(
            post=post, user=self.alice, content="r1", parent=p1
        )

        Comment.objects.create(
            post=post, user=self.alice, content="r2", parent=p2
        )

        ids = set(
            replies_for_comment(self.bob, p1).values_list("pk", flat=True)
        )

        assert ids == {r1.pk}

    def test_newest_first(self):
        post = self._make_post()
        parent = Comment.objects.create(post=post, user=self.bob, content="p")
        older = Comment.objects.create(
            post=post, user=self.alice, content="old", parent=parent
        )
        newer = Comment.objects.create(
            post=post, user=self.alice, content="new", parent=parent
        )

        ordered = list(
            replies_for_comment(self.bob, parent).values_list("pk", flat=True)
        )
        assert ordered == [newer.pk, older.pk]
