import uuid
from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.posts.managers import PostManager


# Create your models here.
class Post(models.Model):
    """
    Represents a social media post with various metadata, visibility settings, and
    content controls.

    The `Post` class enables the creation, modification, and deletion of posts
    authored by users. Posts allow for different statuses (e.g., DRAFT or PUBLISHED),
    visibility levels (e.g., PUBLIC or PRIVATE), and adult content ratings. This
    model supports logical deletion, tracking of edits, and dynamic feed ordering
    using a publish timestamp (`published_at`).

    :ivar id: Unique identifier for the post.
    :type id: UUID

    :ivar author: Reference to the user who authored the post.
    :type author: ForeignKey

    :ivar content: Text body of the post, optional if media is attached.
    :type content: str

    :ivar visibility: Defines the visibility setting of the post, indicating
        who can view the post (e.g., PUBLIC, FRIENDS, PRIVATE).
    :type visibility: str

    :ivar adult_rating: Author-declared rating indicating adult content. Posts
        marked as ADULT skip moderation.
    :type adult_rating: str

    :ivar status: Indicates whether the post is a DRAFT or PUBLISHED. Drafts
        remain visible only to the author.
    :type status: str

    :ivar published_at: Timestamp indicating when the post was published. NULL
        for drafts. The feed ordering uses this timestamp over `created_at`.
    :type published_at: datetime

    :ivar is_edited: Boolean flag indicating whether the post has been edited.
    :type is_edited: bool

    :ivar created_at: Timestamp of when the post was originally created.
    :type created_at: datetime

    :ivar updated_at: Timestamp of the last update to the post.
    :type updated_at: datetime

    :ivar deleted_at: Soft delete timestamp; posts marked as deleted are hidden
        from most queries but remain in the database.
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
