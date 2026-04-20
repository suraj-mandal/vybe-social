from apps.posts.models import Comment
from apps.posts.tests._base import PostCommentTestBase


class TestCommentModel(PostCommentTestBase):
    def test_create_top_level_comment(self):
        post = self._make_post()
        c = Comment.objects.create(post=post, user=self.bob, content="hi")

        assert c.parent is None
        assert c.is_edited is False
        assert c.is_deleted is False
        assert list(post.comments.all()) == [c]

    def test_create_reply_sets_parent(self):
        post = self._make_post()
        parent_comment = Comment.objects.create(
            post=post, user=self.bob, content="p"
        )
        reply = Comment.objects.create(
            post=post,
            user=self.alice,
            parent=parent_comment,
            content="r",
        )

        assert reply.parent_id == parent_comment.id
        assert list(parent_comment.replies.all()) == [reply]

    def test_default_manager_excludes_soft_deleted(self):
        post = self._make_post()
        c = Comment.objects.create(post=post, user=self.bob, content="bye")
        c.delete()  # soft-delete happens here

        assert Comment.objects.filter(pk=c.pk).exists() is False
        assert Comment.all_objects.filter(pk=c.pk).exists() is True

    def test_soft_delete_blanks_content(self):
        post = self._make_post()
        c = Comment.objects.create(post=post, user=self.bob, content="secret")
        c.delete()

        row: Comment = Comment.all_objects.get(pk=c.pk)
        assert row.is_deleted is True
        assert row.content == ""

    def test_soft_delete_preserves_replies(self):
        post = self._make_post()
        parent_comment: Comment = Comment.objects.create(
            post=post, user=self.bob, content="p"
        )
        reply: Comment = Comment.objects.create(
            post=post,
            user=self.alice,
            content="m",
            parent=parent_comment,
        )

        parent_comment.delete()

        assert Comment.objects.filter(pk=reply.pk).exists() is True

    def test_hard_delete_top_level_cascades_replies(self):
        post = self._make_post()
        parent: Comment = Comment.objects.create(
            post=post, user=self.bob, content="p"
        )
        Comment.objects.create(
            post=post,
            user=self.alice,
            parent=parent,
            content="q",
        )

        # doing hard-delete -> actually delete the row from the `comments` table
        parent.hard_delete()

        # there should not be any comment under the post
        assert Comment.all_objects.filter(post=post).count() == 0
