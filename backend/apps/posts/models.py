import uuid
from datetime import datetime

from django.conf import settings
from django.contrib.contenttypes.fields import (
    GenericForeignKey,
    GenericRelation,
)
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.posts.managers import CommentManager, PostManager


# Create your models here.
class Post(models.Model):
    """
    Represents a post created by a user with content, visibility, status, and other metadata.

    This model is used to store and manage user-generated posts. Each post can have associated content,
    visibility restrictions, adult content ratings, and status information. It supports both soft and
    hard delete operations and uses specific timestamps to manage publishing and deletion functionalities.

    :ivar id: Unique identifier for the post.
    :type id: UUID
    :ivar author: Reference to the user who authored the post.
    :type author: ForeignKey
    :ivar content: Text content of the post (optional if media is attached).
    :type content: str
    :ivar visibility: Defines the visibility of the post (public, friends, or private).
    :type visibility: str
    :ivar adult_rating: Declares if the post has adult content, marked by the author.
    :type adult_rating: str
    :ivar status: Indicates whether the post is a draft or published.
    :type status: str
    :ivar reactions: Generic relation field to capture user reactions to the post.
    :type reactions: GenericRelation
    :ivar published_at: Timestamp indicating when the post was transitioned to published.
    :type published_at: datetime
    :ivar is_edited: Boolean flag representing if the post has been edited.
    :type is_edited: bool
    :ivar created_at: Timestamp when the post was created.
    :type created_at: datetime
    :ivar updated_at: Timestamp when the post was last updated.
    :type updated_at: datetime
    :ivar deleted_at: Timestamp marking when the post was soft deleted.
    :type deleted_at: datetime
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        FRIENDS = "friends", "Friends"
        PRIVATE = "private", "Private"

    class AdultRating(models.TextChoices):
        UNCLASSIFIED = "unclassified", "Unclassified"
        SAFE = "safe", "Safe (author-marked)"
        ADULT = "adult", "Adult (18+)"

    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )

    content = models.TextField(
        max_length=5000,
        blank=True,
        help_text="Post body text. Optional if media is attached.",
    )

    visibility = models.CharField(
        max_length=10,
        choices=Visibility,
        default=Visibility.PUBLIC,
    )

    adult_rating = models.CharField(
        max_length=12,
        choices=AdultRating,
        default=AdultRating.UNCLASSIFIED,
        help_text=(
            "Author-declared adult content rating. UNCLASSIFIED and SAFE posts "
            "are sent to the AI Moderator. ADULT posts skip the moderation. "
            "as of now not enforced, once DOB compliance is met, it will be done."
        ),
    )

    status = models.CharField(
        max_length=10,
        choices=Status,
        default=Status.PUBLISHED,
        help_text=(
            "DRAFT posts are author-only and invisible to everyone else. "
            "PUBLISHED posts follow the `visibility` field's rules."
        ),
    )

    # adding reactions field to the post
    reactions = GenericRelation(
        "posts.Reaction",
        related_query_name="post",
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Set when the post transitions to PUBLISHED. NULL while the post "
            "is a draft. Feed ordering uses this, not created_at, "
            "so a post drafted for a week and then published sorts by its "
            "publish time."
        ),
    )

    is_edited = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # ruff: noqa: DJ012
    objects = PostManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "post"
        verbose_name_plural = "posts"
        ordering = [
            "-created_at",
            "-id",
        ]
        indexes = [
            models.Index(
                fields=[
                    "-created_at",
                    "-id",
                ]
            ),
            models.Index(
                fields=[
                    "author",
                    "-id",
                ]
            ),
            models.Index(
                fields=[
                    "visibility",
                    "-created_at",
                ]
            ),
            models.Index(
                fields=[
                    "author",
                    "status",
                    "-created_at",
                ]
            ),
        ]

    def __str__(self) -> str:
        """
        Generate a string representation of the object, providing a concise preview of its content.

        :returns: A formatted string containing the author's name and a preview of the content (up to 30 characters).
         :rtype: str
        """
        preview = (self.content or "")[:30]
        return (
            f"{self.author} - {preview}..."
            if preview
            else f"{self.author} (media)"
        )

    def delete(self, using=None, keep_parents=False):
        """
        Marks the current instance as deleted by setting the `deleted_at` field to the
        current timestamp and saving the changes.

        :param using: The database alias to use for saving the instance.
        :param keep_parents: Whether to keep the parents intact when saving changes.
        :return: None
        """
        self.deleted_at: datetime = timezone.now()
        self.save(
            update_fields=[
                "deleted_at",
            ]
        )

    def hard_delete(self, using=None, keep_parents=False):
        """
        Deletes the current instance from the database completely.
        Should be used by ADMINs only.

        This method overrides the default delete behavior to perform a hard delete,
        allowing the object to be permanently removed from the database rather than being
        soft deleted or retained in any way.

        :param using: The database alias to use for the deletion. If not provided,
            the "default" database will be used.
        :type using: Optional[str]
        :param keep_parents: A boolean flag indicating whether the related parent
            objects should be retained after deletion. Defaults to False.
        :type keep_parents: bool
        :return: None
        """
        super().delete(using=using, keep_parents=keep_parents)


class PostMedia(models.Model):
    """
    Represents the linking of media objects with posts in the application.

    This class defines a many-to-one relationship between posts and media, ensuring
    that each media object is uniquely linked to a specific post with a defined
    position for ordering. It serves as a bridge linking the Post model with the
    Media model, and is utilized for managing media attachments to posts.

    :ivar id: The unique identifier for the PostMedia instance.
    :type id: UUIDField
    :ivar post: The foreign key linking to the parent post.
    :type post: ForeignKey
    :ivar media: The foreign key linking to the associated media. It references
        a "Media" model row and ensures the relationship with an actual S3 object.
    :type media: ForeignKey
    :ivar position: The position of the media in the post for ordering purposes.
    :type position: PositiveSmallIntegerField
    :ivar created_at: The timestamp indicating when the PostMedia instance was created.
    :type created_at: DateTimeField
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="media",
    )

    media = models.ForeignKey(
        "media.Media",
        on_delete=models.PROTECT,
        related_name="+",
        help_text=(
            "The Media row holding the actual S3 object. "
            "Attached posts reference it via this FK - no duplicated fields."
        ),
    )

    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "post media"
        verbose_name_plural = "post media"
        ordering = [
            "position",
            "created_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["post", "media"],
                name="unique_postmedia_post_media",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "post",
                    "position",
                ]
            )
        ]

    def __str__(self) -> str:
        """
        Provides a string representation of a PostMedia object, including associated post ID, media ID,
        and its position.

        :return: A formatted string representing the PostMedia object.
        :rtype: str
        """
        return f"PostMedia({self.post.id} <- {self.media.id} @ {self.position})"


class Reaction(models.Model):
    """
    Represents a reaction made by a user on a target object.

    This class is used to store and manage user reactions on various objects in the system.
    Reactions can be of different types such as "like", "heart", or "haha", and they are tied
    to a specific user and target object. The `GenericForeignKey` is used to associate the reaction
    with the target model instance.

    :ivar id: The unique identifier for the reaction.
    :type id: UUID
    :ivar user: The user who made the reaction.
    :type user: ForeignKey
    :ivar content_type: The content type of the target object.
    :type content_type: ForeignKey
    :ivar object_id: The ID of the target object that the reaction is associated with.
    :type object_id: UUID
    :ivar target: A generic relation to the target object.
    :type target: GenericForeignKey
    :ivar type: The type of reaction, such as "like" or "heart".
    :type type: str
    :ivar created_at: The timestamp when the reaction was created.
    :type created_at: datetime
    :ivar updated_at: The timestamp when the reaction was last updated.
    :type updated_at: datetime
    """

    class Type(models.TextChoices):
        LIKE = "like", "Like"
        HEART = (
            "heart",
            "HEART",
        )
        HAHA = (
            "haha",
            "Haha",
        )
        WOW = "wow", "Wow"
        SAD = "sad", "Sad"
        ANGRY = "angry", "Angry"
        EXCITED = "excited", "Excited"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reactions",
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )

    object_id = models.UUIDField()

    target = GenericForeignKey()

    type = models.CharField(max_length=10, choices=Type)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "reaction"
        verbose_name_plural = "reactions"
        ordering = [
            "-created_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "content_type",
                    "object_id",
                ],
                name="uniq_reaction_per_user_target",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "content_type",
                    "object_id",
                    "type",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "-created_at",
                ]
            ),
        ]

    def __str__(self) -> str:
        """
        Generate a string representation of the object.

        This method returns a formatted string representation of the object,
        showing specific attributes in a concatenated format. It provides a
        concise and readable output that is useful for logging or debugging purposes.

        :return: A string combining the `user`, `type`, `content_type`, and
            `object_id` attributes in a specific format.
        :rtype: str
        """
        return f"{self.user} {self.type} {self.content_type}:{self.object_id}"


class Comment(models.Model):
    """
    Represents a comment within a post, allowing for nested replies, user interaction,
    and reactions. Includes features for marking comments as edited or deleted.

    This model supports top-level comments and single-level replies to those comments.
    Replies-to-replies are modeled as sibling replies with the ability to include
    @mentions for clarity. The class provides methods for soft-delete and hard-delete,
    allowing flexibility to preserve or permanently remove comment data.

    :ivar id: Unique identifier for the comment.
    :type id: UUID

    :ivar user: Reference to the user who authored the comment.
    :type user: ForeignKey

    :ivar post: Reference to the post where the comment belongs.
    :type post: ForeignKey

    :ivar parent: Reference to the parent comment if the comment is a reply.
    :type parent: ForeignKey

    :ivar content: The main content of the comment, limited to 2000 characters.
    :type content: str

    :ivar is_edited: Indicates whether the comment has been edited.
    :type is_edited: bool

    :ivar is_deleted: Indicates whether the comment has been marked as deleted.
    :type is_deleted: bool

    :ivar created_at: The timestamp when the comment was created.
    :type created_at: datetime

    :ivar updated_at: The timestamp when the comment was last updated.
    :type updated_at: datetime

    :ivar reactions: Generic relation to manage reactions (e.g., likes or emoticons)
        associated with the comment.
    :type reactions: GenericRelation
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
        help_text=(
            "Parent comment for replies. NULL for top-level. Max depth is 1 "
            "(enforced at the serializer). Replies-to-replies are modeled "
            "as sibling replies with @mentions."
        ),
    )

    content = models.TextField(max_length=2000)

    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    reactions = GenericRelation(
        "posts.Reaction",
        related_query_name="comment",
    )

    # ruff: noqa: DJ012
    objects = CommentManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "comment"
        verbose_name_plural = "comments"
        ordering = [
            "-created_at",
            "-id",
        ]
        indexes = [
            models.Index(
                fields=[
                    "post",
                    "-created_at",
                ]
            ),
            models.Index(
                fields=[
                    "parent",
                    "created_at",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "created_at",
                ]
            ),
        ]

    def __str__(self) -> str:
        """
        Provides a string representation of the object.

        The method generates a string that uniquely represents an instance by
        combining information about the associated user, the related post ID,
        and a short preview of the content or a "[deleted]" tag if the object
        is marked as deleted. The content preview will only include the first
        30 characters.

        :return: A string representing the object, including user information,
            the post ID, and either a content preview or "[deleted]".
        :rtype: str
        """
        preview = (self.content or "")[:30]
        tag = "[deleted]" if self.is_deleted else preview
        return f"{self.user} on {self.post.id}: {tag}"

    def delete(self, using=None, keep_parents=False):
        """
        Deletes the content of an object and marks it as deleted. Performs updates to
        the database to save these changes.

        :param using: The database alias used for saving this object, if necessary.
        :param keep_parents: Determines whether to cascade the delete operation
            to parent objects. Defaults to False.
        :return: None
        """
        self.content = ""
        self.is_deleted = True
        self.save(
            update_fields=[
                "content",
                "is_deleted",
                "updated_at",
            ]
        )

    def hard_delete(self, using=None, keep_parents=False):
        """
        Deletes the object from the database permanently. Unlike a soft delete, this method
        removes the record entirely from the database, making it unrecoverable. It also provides
        the capability to specify a database alias and whether to keep parent records intact.

        :param using: The alias of the database to use. Defaults to None, which uses the
                      default database connection.
        :param keep_parents: A boolean flag indicating whether to keep the records of parent
                             models in the case of multi-table inheritance. Defaults to False.
        :return: None
        """
        super().delete(using=using, keep_parents=keep_parents)


class CommentMention(models.Model):
    """
    Represents a mention of a user in a comment.

    Provides a mechanism to associate a specific user with a comment, identifying that
    the user has been mentioned in the comment. Supports querying all mentions for a
    specific user or across multiple comments, and enforces the uniqueness of mentions
    per comment and user.

    :ivar id: Universally unique identifier for the mention instance.
    :type id: UUIDField
    :ivar comment: Reference to the `Comment` instance in which the user is mentioned.
    :type comment: ForeignKey
    :ivar user: Reference to the user being mentioned in a comment.
    :type user: ForeignKey
    :ivar created_at: Timestamp indicating when the mention was created.
    :type created_at: DateTimeField
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="mentions"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_mentions",
        help_text="The user being mentioned.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comment mention"
        verbose_name_plural = "comment mentions"
        ordering = [
            "created_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "comment",
                    "user",
                ],
                name="uniq_mention_per_comment_user",
            )
        ]
        indexes = [
            models.Index(
                fields=[
                    "user",
                    "-created_at",
                ]
            )
        ]

    def __str__(self) -> str:
        """
        Provides a string representation of the object.

        This method generates a string that uniquely identifies the relationship
        between the comment and user associated with the object.

        :return: String in the format "comment_id -> user"
        :rtype: str
        """
        return f"{self.comment.id} -> {self.user}"
