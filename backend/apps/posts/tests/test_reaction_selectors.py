from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.posts.models import Comment, Post, Reaction
from apps.posts.selectors import _reaction_annotations
from apps.posts.tests._base import PostCommentTestBase


class TestReactionAnnotationsOnPost(PostCommentTestBase):
    def test_counts_and_breakdown(self):
        post = self._make_post()
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.HEART
        )
        Reaction.objects.create(
            user=self.charlie, target=post, type=Reaction.Type.HEART
        )
        Reaction.objects.create(
            user=self.alice, target=post, type=Reaction.Type.HAHA
        )

        qs = Post.objects.filter(pk=post.pk).annotate(
            **_reaction_annotations(self.bob, Post)
        )

        row = qs.first()

        assert row.reactions_count == 3
        assert row.reactions_heart == 2
        assert row.reactions_haha == 1
        assert row.reactions_like == 0
        assert row.user_reaction == Reaction.Type.HEART

    def test_user_reaction_none_when_not_reacted(self):
        post = self._make_post()
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.LIKE
        )

        qs = Post.objects.filter(pk=post.pk).annotate(
            **_reaction_annotations(self.charlie, Post)
        )

        assert qs.first().user_reaction is None

    def test_user_reaction_returns_own_type(self):
        post = self._make_post()
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.WOW
        )

        qs = Post.objects.filter(pk=post.pk).annotate(
            **_reaction_annotations(self.bob, Post)
        )

        assert qs.first().user_reaction == Reaction.Type.WOW

    def test_annotations_do_not_leak_across_posts(self):
        a = self._make_post(content="one")
        b = self._make_post(content="two")

        Reaction.objects.create(
            user=self.bob, target=a, type=Reaction.Type.LIKE
        )

        qs = Post.objects.filter(pk__in=[a.pk, b.pk]).annotate(
            **_reaction_annotations(self.bob, Post)
        )

        by_id = {p.pk: p for p in qs}

        assert by_id[a.pk].reactions_count == 1
        assert by_id[b.pk].reactions_count == 0


class TestReactionAnnotationsOnComment(PostCommentTestBase):
    def test_comment_reactions_counted_independently(self):
        post = self._make_post()
        c = Comment.objects.create(post=post, user=self.alice, content="x")
        Reaction.objects.create(
            user=self.bob, target=post, type=Reaction.Type.LIKE
        )  # reacting on the post
        Reaction.objects.create(
            user=self.bob, target=c, type=Reaction.Type.HEART
        )  # reacting on the comment

        qs = Comment.objects.filter(pk=c.pk).annotate(
            **_reaction_annotations(self.bob, Comment)
        )

        row = qs.first()
        assert row.reactions_count == 1
        assert row.reactions_heart == 1
        assert row.user_reaction == Reaction.Type.HEART


class TestReactionAnnotationsQueryCount(PostCommentTestBase):
    def test_single_query_regardless_of_row_count(self):
        posts = [self._make_post(content=f"p{i}") for i in range(5)]

        for p in posts:
            Reaction.objects.create(
                user=self.bob, target=p, type=Reaction.Type.LIKE
            )
            Reaction.objects.create(
                user=self.charlie, target=p, type=Reaction.Type.HEART
            )

        with CaptureQueriesContext(connection) as ctx:
            qs = Post.objects.filter(pk__in=[p.pk for p in posts]).annotate(
                **_reaction_annotations(self.bob, Post)
            )

            # force evaluation here, since annotations are lazy till evaluation
            rows = list(qs)

            assert len(rows)
            assert len(ctx.captured_queries) == 1, (
                f"expected 1 query, got {len(ctx.captured_queries)}:\n"
                + "\n---\n".join(q["sql"] for q in ctx.captured_queries)
            )

    def test_count_scales_flat_with_rows(self):
        # 1 row vs 20 rows should be a single SELECT
        one = self._make_post()
        with CaptureQueriesContext(connection) as ctx1:
            list(
                Post.objects.filter(pk=one.pk).annotate(
                    **_reaction_annotations(self.bob, Post)
                )
            )

        many = [self._make_post(content=f"m{i}") for i in range(20)]
        with CaptureQueriesContext(connection) as ctx20:
            list(
                Post.objects.filter(pk__in=[p.pk for p in many]).annotate(
                    **_reaction_annotations(self.bob, Post)
                )
            )

        assert len(ctx1.captured_queries) == 1
        assert len(ctx20.captured_queries) == 1
