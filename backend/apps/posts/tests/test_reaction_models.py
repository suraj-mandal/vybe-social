from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError

from apps.posts.models import Comment, Post, Reaction
from apps.posts.tests._base import PostCommentTestBase


# testing reaction on post
class TestReactionOnPost(PostCommentTestBase):
    def test_create_reaction_on_post(self):
        post = self._make_post()
        r = Reaction.objects.create(
            user=self.bob,
            target=post,
            type=Reaction.Type.HEART,
        )

        assert r.content_type == ContentType.objects.get_for_model(Post)
        assert r.object_id == post.id
        assert r.target == post

    def test_post_reverse_relation(self):
        post = self._make_post()
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.LIKE
        )
        Reaction.objects.create(
            user=self.charlie, target=post, type=Reaction.Type.HAHA
        )

        assert post.reactions.count() == 2

    def test_unique_constraint_across_user_and_target(self):
        post = self._make_post()
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.LIKE
        )

        with self.assertRaises(IntegrityError):
            Reaction.objects.create(
                user=self.bob, target=post, type=Reaction.Type.HEART
            )

    def test_upsert_replaces_type_without_violating_constraint(self):
        post = self._make_post()
        ct = ContentType.objects.get_for_model(Post)

        r1, created1 = Reaction.objects.update_or_create(
            user=self.bob,
            content_type=ct,
            object_id=post.id,
            defaults={"type": Reaction.Type.LIKE},
        )

        r2, created2 = Reaction.objects.update_or_create(
            user=self.bob,
            content_type=ct,
            object_id=post.id,
            defaults={"type": Reaction.Type.HAHA},
        )

        assert created1 is True
        assert created2 is False
        assert r1.pk == r2.pk
        assert r2.type == Reaction.Type.HAHA
        assert Reaction.objects.filter(user=self.bob).count() == 1

    def test_hard_delete_post_cascades_reactions(self):
        post = self._make_post()
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.LIKE
        )

        post.hard_delete()  # hard delete - actually deleting the post from the db
        assert (
            Reaction.objects.count() == 0
        )  # no reaction objects should remain

    def test_soft_delete_post_retains_reactions(self):
        post = self._make_post()
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.LIKE
        )

        post.delete()  # soft delete - just set deleted_at to the current timestamp
        assert Reaction.objects.count() == 1  # reaction object should remain


class TestReactionOnComment(PostCommentTestBase):
    def test_reactions_on_post_and_comment_are_independent(self):
        post = self._make_post()
        comment = Comment.objects.create(
            post=post,
            user=self.bob,
            content="nice",
        )

        Reaction.objects.create(
            user=self.alice, target=post, type=Reaction.Type.LIKE
        )
        Reaction.objects.create(
            user=self.alice, target=comment, type=Reaction.Type.HEART
        )

        # different content_types - unique constraint should not collide here
        assert Reaction.objects.filter(user=self.alice).count() == 2
        assert post.reactions.count() == 1
        assert comment.reactions.count() == 1

    def test_hard_delete_comment_cascades_reactions(self):
        post = self._make_post()
        comment = Comment.objects.create(post=post, user=self.bob, content="x")
        Reaction.objects.create(
            user=self.alice, target=comment, type=Reaction.Type.LIKE
        )

        comment.hard_delete()  # actually deleting the comment from the row
        assert (
            Reaction.objects.count() == 0
        )  # count of the reaction object will be 0
