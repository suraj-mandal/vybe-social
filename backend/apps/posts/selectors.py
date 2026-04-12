from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.moderation.models import Block
from apps.posts.models import Post, PostMedia


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
