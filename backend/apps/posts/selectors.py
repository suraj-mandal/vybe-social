from typing import Any

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    F,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Window,
)
from django.db.models.aggregates import Count
from django.db.models.functions import RowNumber
from django.utils import timezone

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.moderation.models import Block
from apps.posts.models import Comment, Post, PostMedia, Reaction


# creating selectors for reactions for the user
def _reaction_annotations(user: User, model_class) -> dict[str, Any]:
    """
    Generates reaction-related metadata for a given comment or post, including counts
    for various reaction types and the current user's reaction, if any. The function
    works for any model passed as `model_class` and uses a single reaction per
    comment/post for a given user.

    :param user: The user object for which the reaction metadata will include the user's
                 specific reaction, if present.
    :type user: User
    :param model_class: The model class to determine the type of content (e.g., Post or
                        Comment) for reaction analysis.
    :type model_class: type
    :return: A dictionary containing metadata about reactions, including counts of
             distinct reactions, counts for specific reaction types (like, heart, wow,
             etc.), and the current user's specific reaction (if present).
    :rtype: Dict[str, Any]
    """

    # depending upon the current user case, content_type will be either
    # 1. Post, 2. Comment
    content_type = ContentType.objects.get_for_model(model_class)

    # here the user will have only one reaction per comment/post
    # still reinforcing the [:1] here instead of relying on the unique
    # constraints.
    # This is a sequence that will be generated to check whether the
    # user has reacted to the comment/post
    user_reaction_sq = Reaction.objects.filter(
        content_type=content_type,
        user=user,
        object_id=OuterRef("pk"),
    ).values("type")[:1]

    # returns the reaction related metadata for a given comment / post
    return {
        "reactions_count": Count("reactions", distinct=True),
        "reactions_like": Count(
            "reactions", filter=Q(reactions__type=Reaction.Type.LIKE)
        ),
        "reactions_heart": Count(
            "reactions", filter=Q(reactions__type=Reaction.Type.HEART)
        ),
        "reactions_wow": Count(
            "reactions", filter=Q(reactions__type=Reaction.Type.WOW)
        ),
        "reactions_haha": Count(
            "reactions", filter=Q(reactions__type=Reaction.Type.HAHA)
        ),
        "reactions_sad": Count(
            "reactions", filter=Q(reactions__type=Reaction.Type.SAD)
        ),
        "reactions_angry": Count(
            "reactions", filter=Q(reactions__type=Reaction.Type.ANGRY)
        ),
        "reactions_excited": Count(
            "reactions", filter=Q(reactions__type=Reaction.Type.EXCITED)
        ),
        "user_reaction": Subquery(user_reaction_sq),
    }


def _preview_reply_ids_subquery() -> QuerySet[Comment]:
    """
    Generates a queryset that retrieves a subset of comment replies based on a specific
    ranking criteria for inline preview purposes. The subset is determined by ordering
    replies by the creation date and ID within each parent comment group, and selecting
    a limited number of replies per parent as defined by a system setting.

    :return: A queryset of Comment objects that meet the specified ranking and selection
             criteria.
    :rtype: QuerySet[Comment]
    """
    ranked = Comment.objects.filter(parent__isnull=False).annotate(
        rn=Window(
            expression=RowNumber(),
            partition_by=[F("parent_id")],
            order_by=[F("created_at").desc(), F("id").desc()],
        )
    )

    return Comment.objects.filter(
        id__in=Subquery(
            ranked.filter(rn__lte=settings.REPLIES_INLINE_PREVIEW).values("id")
        )
    )


def _media_prefetch() -> Prefetch:
    """
    Generates a Prefetch object for efficiently preloading associated media objects in
    a database query. The Prefetch specifies the queryset to prefetch related `PostMedia`
    objects, sorting them by their `position` and automatically selecting related
    `media` objects for optimized performance.

    :return: Prefetch object configured for preloading `media` objects within querysets
    :rtype: Prefetch
    """
    return Prefetch(
        "media",
        queryset=PostMedia.objects.select_related("media").order_by("position"),
    )


def visible_posts_for(user: User) -> QuerySet[Post]:
    """
    Determines the posts visible to a given user based on their relationships and
    privacy settings. The method computes the set of friends, blocked users, and
    users who have blocked the given user. Posts are filtered to include only
    those that match the visibility constraints and exclude posts from blocked
    users or users who have blocked the requesting user.

    :param user: The user for whom visible posts are to be retrieved.
    :type user: User
    :return: A queryset containing posts that are visible to the given user
        according to their relationships, post visibility settings, and blocking
        rules.
    :rtype: QuerySet[Post]
    """
    friend_ids = set(
        FriendRequest.objects.friends_of(user).values_list("id", flat=True)
    )
    blocked_ids = Block.objects.blocked_user_ids(user)
    blocked_by_ids = Block.objects.blocked_by_user_ids(user)
    excluded_ids = blocked_ids | blocked_by_ids

    # get the associated comments, reactions associated with the post
    return (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .filter(
            Q(visibility=Post.Visibility.PUBLIC)
            | Q(visibility=Post.Visibility.FRIENDS, author_id__in=friend_ids)
            | Q(author=user)
        )
        .exclude(author_id__in=excluded_ids)
        .select_related("author__profile__avatar")
        .prefetch_related(_media_prefetch())
        .annotate(
            **_reaction_annotations(user, Post),
            comments_count=Count(
                "comments",
                filter=Q(comments__is_deleted=False),
                distinct=True,
            ),
        )
    )


def drafts_for(user: User) -> QuerySet[Post]:
    """
    Retrieves a queryset of draft posts authored by the specified user. The resulting
    queryset is optimized with selected related and prefetched related objects, as
    well as ordered by the last updated timestamp and ID in descending order.

    :param user: The user whose draft posts are to be retrieved.
    :type user: User
    :return: A queryset of draft posts authored by the given user.
    :rtype: QuerySet[Post]
    """
    return (
        Post.objects.filter(author=user, status=Post.Status.DRAFT)
        .select_related("author__profile__avatar")
        .prefetch_related(_media_prefetch())
        .order_by("-updated_at", "-id")
    )


def accessible_posts_for(user: User) -> QuerySet[Post]:
    """
    Retrieve the posts accessible to a given user, considering the user's friendships,
    blocked users, and visibility and publication status of the posts.

    This function determines which posts are visible to the given user by applying
    the following rules:

    - Include published posts with visibility set to public.
    - Include published posts with visibility set to friends if the author is a friend of the user.
    - Include the user's own published and draft posts.
    - Exclude posts from users who have blocked the given user or have been blocked
      by the user.

    The results will include author profile avatars and prefetch related media for
    optimization.

    :param user: The user for whom accessible posts are being retrieved.
    :type user: User
    :return: A queryset of posts that the user can access based on visibility,
        friendship, and block rules.
    :rtype: QuerySet[Post]
    """
    friend_ids = set(
        FriendRequest.objects.friends_of(user).values_list("id", flat=True)
    )
    blocked_ids = Block.objects.blocked_user_ids(user)
    blocked_by_ids = Block.objects.blocked_by_user_ids(user)
    excluded_ids = blocked_ids | blocked_by_ids

    published_visible = Q(status=Post.Status.PUBLISHED) & (
        Q(visibility=Post.Visibility.PUBLIC)
        | Q(visibility=Post.Visibility.FRIENDS, author_id__in=friend_ids)
        | Q(author=user)
    )

    own_drafts = Q(status=Post.Status.DRAFT)

    return (
        Post.objects.filter(published_visible | own_drafts)
        .exclude(author_id__in=excluded_ids)
        .select_related("author__profile__avatar")
        .prefetch_related(_media_prefetch())
        .annotate(
            **_reaction_annotations(user, Post),
            comments_count=Count(
                "comments",
                filter=Q(comments__is_deleted=False),
                distinct=True,
            ),
        )
    )


def publish_post(post: Post) -> Post:
    """
    Publishes a given post if it is not already published.

    This function updates the status of the provided post to 'PUBLISHED'.
    If the post is already in the 'PUBLISHED' state, the function does not
    alter the object and returns it as is. Otherwise, it updates the
    `status` and `published_at` fields, saves the post, and returns the
    updated post.

    :param post: The post object to be published.
    :type post: Post
    :return: The published post object.
    :rtype: Post
    """
    if post.status == Post.Status.PUBLISHED:
        return post

    post.status = Post.Status.PUBLISHED
    post.published_at = timezone.now()
    post.save(
        update_fields=[
            "status",
            "published_at",
            "updated_at",
        ]
    )

    return post


def comments_for_post(user: User, post: Post) -> QuerySet[Comment]:
    """
    Fetches the queryset of top-level comments for a given post. The resulting queryset is annotated
    with additional metadata, including reactions and replies count, and includes related data
    for efficient access.

    :param user: The user for whom the comments are being fetched. This is used for personalizing
        reaction annotations within the comments.
    :type user: User
    :param post: The post instance for which the comments are being retrieved.
    :type post: Post
    :return: A queryset of `Comment` objects, filtered to contain only top-level comments for the
        provided post. The queryset is annotated with reactions, replies count, and prefetches
        related data for optimal performance.
    :rtype: QuerySet[Comment]
    """
    replies_preview_query_set = (
        _preview_reply_ids_subquery()
        .select_related("user__profile__avatar")
        .prefetch_related("mentions__user")
        .annotate(**_reaction_annotations(user, Comment))
        .order_by("-created_at", "-id")
    )

    replies_prefetch = Prefetch("replies", queryset=replies_preview_query_set)

    # will be fixed by redis at later stages.
    return (
        Comment.objects.filter(post=post, parent__isnull=True)
        .select_related("user__profile__avatar")
        .prefetch_related(replies_prefetch, "mentions__user")
        .annotate(
            **_reaction_annotations(user, Comment),
            replies_count=Count("replies", distinct=True),
        )
        .order_by("-created_at", "-id")
    )


def replies_for_comment(user: User, parent: Comment) -> QuerySet[Comment]:
    """
    Retrieve replies for a given parent comment with additional annotations and related data.

    This function generates a queryset of comments that are replies to the given parent comment.
    The returned queryset is enriched with related user and avatar data, prefetches mentions,
    and includes reaction annotations tailored for a specific user.

    :param user: The user for whom the replies are being retrieved.
    :type user: User
    :param parent: The parent comment object for which replies are fetched.
    :type parent: Comment
    :return: A queryset containing comments that are replies to the parent comment,
             enriched with related data and annotations.
    :rtype: QuerySet[Comment]
    """

    # no need for db level pagination here, as this queryset will be
    # clubbed with comment cursor level pagination, in order
    # to get the pagination required.
    return (
        Comment.objects.filter(parent=parent)
        .select_related("user__profile__avatar")
        .prefetch_related("mentions__user")
        .annotate(**_reaction_annotations(user, Comment))
        .order_by("-created_at", "-id")
    )


def reactions_for_target(target) -> QuerySet[Reaction]:
    """
    Retrieve all reactions associated with a specific target object. The target object can represent
    any model instance (e.g., a post or a comment). The function filters reactions by their
    content type and object ID, ensuring that only relevant reactions are retrieved. The output
    also includes related user profile data for convenience.

    :param target: The model instance for which reactions are to be retrieved. It must have a `pk`
                   attribute representing its primary key and should be compatible with Django's
                   `ContentType` mechanism.
    :type target: Any
    :return: A queryset containing `Reaction` instances ordered by their creation date in descending
             order, with related user profile and avatar data preloaded for each reaction.
    :rtype: QuerySet[Reaction]
    """
    content_type = ContentType.objects.get_for_model(target.__class__)

    # this returns the list of users who have reacted to the given post or comment
    return (
        Reaction.objects.filter(content_type=content_type, object_id=target.pk)
        .select_related("user__profile__avatar")
        .order_by("-created_at")
    )
