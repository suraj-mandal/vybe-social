# creating the parser here to parse the `@` mention in a comment
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.posts.models import Comment, CommentMention

User = get_user_model()


def extract_usernames(content: str | None) -> list[str]:
    """
    Extract unique usernames mentioned in the provided content using a predefined mention pattern.

    This function scans the given text content for all occurrences of a mention string based on a
    regular expression. It ensures that the returned list contains only unique usernames in a
    case-insensitive manner. If the input content is empty or no matches are found, it returns an empty list.

    :param content: The string content to search for mentions.
    :type content: str
    :return: A list of unique usernames extracted from the content.
    :rtype: List[str]
    """
    if not content:
        return []
    matches = re.findall(settings.MENTION_REGEX, content)
    seen: dict[str, None] = {}

    for match in matches:
        key = match.lower()
        if key not in seen:
            seen[key] = None

    return list(seen.keys())


def resolve_mentioned_users(usernames: list[str]) -> list[User]:
    """
    Resolves a list of mentioned users based on the given usernames. It performs a
    case-insensitive query to match the provided usernames with existing users in
    the database.

    :param usernames: A list of usernames for which mentioned users must be resolved.
    :return: A list of User objects corresponding to the provided usernames.
    """
    if not usernames:
        return []

    return list(User.objects.filter(username__iexact__in=usernames))


def sync_mentions(comment: Comment) -> None:
    """
    Synchronizes the mentions in a given comment.

    This function identifies all usernames mentioned within the provided comment's
    content and updates the associated comment's mentions to reflect these users.
    It performs a case-insensitive lookup for the usernames and ensures the
    database is updated atomically to maintain consistency.

    :param comment: The comment object whose mentions need to be synchronized.
    :type comment: Comment
    :return: None
    """
    usernames = extract_usernames(comment.content)

    # case-insensitive lookup here
    qs = User.objects.none()

    for username in usernames:
        qs |= User.objects.filter(username__iexact=username)

    users = list(qs.distinct())

    with transaction.atomic():
        # recreating the comment mentions here
        comment.mentions.all().delete()
        CommentMention.objects.bulk_create(
            [CommentMention(comment=comment, user=user) for user in users],
            ignore_conflicts=True,
        )
