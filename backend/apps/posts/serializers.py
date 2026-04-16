from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList

from apps.accounts.models import User
from apps.media.models import Media
from apps.media.s3_service import generate_presigned_read_url
from apps.posts.mentions import sync_mentions
from apps.posts.mixins import ReactionAnnotationMixin
from apps.posts.models import Comment, CommentMention, Post, PostMedia, Reaction
from apps.profiles.models import Profile


class ReactionUserSerializer(serializers.ModelSerializer):
    """
    Serializer for representing user reactions with additional fields.

    This class is a serializer for the `User` model. It extends the functionality of
    `ModelSerializer` by adding a custom method field `avatar_url` that provides the
    URL for the user's avatar. The serializer is configured to handle specific fields
    and ensures they are read-only for safety when used in API endpoints.

    :ivar avatar_url: A method field that computes the URL for accessing the user's
                      avatar if it exists.
    :type avatar_url: serializers.SerializerMethodField
    """

    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "avatar_url",
        ]
        read_only_fields = fields

    def get_avatar_url(self, user: User) -> str | None:
        """
        Retrieves the avatar URL for a given user. If the user has a profile and the
        profile contains an avatar, a presigned URL for reading the avatar is
        generated and returned. If either the profile or avatar does not exist, it
        returns None.

        :param user: The user object for which the avatar URL is to be retrieved.
        :type user: User
        :return: A presigned URL for accessing the avatar if it exists, otherwise
                 None.
        :rtype: Optional[str]
        """
        profile: Profile | None = getattr(user, "profile", None)
        if profile is None or profile.avatar_id is None:
            return None
        return generate_presigned_read_url(profile.avatar.s3_key)


class ReactionSerializer(serializers.ModelSerializer):
    """
    Serializer for representing Reaction model data.

    This serializer is designed to convert Reaction model instances into native
    Python data types and vice versa. It ensures data consistency and validation
    when serializing or deserializing Reaction objects. The serializer includes
    data about the user who reacted, the type of reaction, and the time at
    which the reaction was created.

    :ivar user: Read-only field representing the user associated with the reaction.
    :type user: ReactionUserSerializer
    """

    user = ReactionUserSerializer(read_only=True)

    class Meta:
        model = Reaction
        fields = ["id", "user", "type", "created_at"]
        read_only_fields = fields


class ReactionUpsertSerializer(serializers.Serializer):
    """
    Serializer for handling the creation or update of reaction data.

    This class is used to manage and validate the input data required for creating
    or updating a reaction instance. It ensures that the input data conforms to
    specified choices defined in the `Reaction.Type` enumeration.

    :ivar type: The type of reaction being upserted. The value must match one of
        the predefined choices in `Reaction.Type`.
    :type type: serializers.ChoiceField
    """

    type = serializers.ChoiceField(choices=Reaction.Type)


# creating the serializer for comment mention


class CommentMentionSerializer(serializers.ModelSerializer):
    """
    Serializer for handling comment mentions.

    This serializer is tailored specifically for managing objects of type
    `CommentMention`. It links the mentioned user's information using
    the `ReactionUserSerializer`. The serializer enforces read-only
    constraints for all retrieved fields.

    :ivar user: Information about the user who is mentioned in the comment.
    :type user: ReactionUserSerializer
    """

    user = ReactionUserSerializer(read_only=True)

    class Meta:
        model = CommentMention
        fields = ["id", "user"]
        read_only_fields = fields


class CommentAuthorSerializer(serializers.ModelSerializer):
    """
    Serializer for authoring comments, extending `serializers.ModelSerializer`.

    This serializer is designed to facilitate the representation of user data, such as
    their personal information and avatar URL. It ensures that only authorized fields
    are exposed and provides a method for resolving the avatar URL securely using a
    presigned URL, if such a URL is available.

    :ivar avatar_url: A computed field representing the URL of the user's avatar. Returns
                      None if the profile or avatar information is unavailable.
    :type avatar_url: Optional[str]
    """

    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "avatar_url",
        ]
        read_only_fields = fields

    def get_avatar_url(self, user: User) -> str | None:
        """
        Retrieve the avatar URL for a given user.

        This function fetches the avatar URL for the specified user by accessing the
        user's profile. If the user does not have a profile or the profile does not
        contain an avatar, the function returns None. The URL is generated using a
        presigned URL method.

        :param user: The user object containing a profile with avatar details.
        :type user: User
        :return: The avatar URL as a string, or None if no avatar is found.
        :rtype: Optional[str]
        """
        profile: Profile | None = getattr(user, "profile", None)
        if profile is None or profile.avatar_id is None:
            return None
        return generate_presigned_read_url(profile.avatar.s3_key)


class ReplySerializer(ReactionAnnotationMixin, serializers.ModelSerializer):
    """
    Serializer for handling reply data within a comment system.

    The `ReplySerializer` is responsible for serializing and deserializing data related
    to replies in a comment system. It supports nested serialization for authors and mentions
    and provides additional methods for calculating and retrieving reaction-based information.
    This serializer ensures read-only access to specific fields and appropriately handles
    deleted replies by obfuscating sensitive data.

    :ivar user: Serializer for the author of the reply, providing read-only access.
    :type user: CommentAuthorSerializer

    :ivar mentions: Serializer for mentions in the reply, providing read-only access to
        multiple mentions.
    :type mentions: CommentMentionSerializer(many=True)

    :ivar reactions_count: Field to retrieve the total number of reactions on the reply.
    :type reactions_count: serializers.SerializerMethodField

    :ivar reactions_breakdown: Field to retrieve a categorized breakdown of reactions for
        the reply.
    :type reactions_breakdown: serializers.SerializerMethodField

    :ivar user_reaction: Field to retrieve the reaction of the current user on the reply,
        if any.
    :type user_reaction: serializers.SerializerMethodField
    """

    user = CommentAuthorSerializer(read_only=True)
    mentions = CommentMentionSerializer(many=True, read_only=True)

    reactions_count = serializers.SerializerMethodField()
    reactions_breakdown = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "content",
            "parent",
            "is_edited",
            "is_deleted",
            "created_at",
            "updated_at",
            "mentions",
            "reactions_count",
            "reactions_breakdown",
            "user_reaction",
        ]
        read_only_fields = fields

    def to_representation(self, instance: Comment) -> dict[str, Any]:
        """
        Transforms the given `Comment` instance into its serialized representation.
        If the comment is marked as deleted, its content is replaced with "[deleted]",
        and the user information is set to `None`.

        :param instance: The `Comment` instance to be serialized.
        :type instance: Comment
        :return: A dictionary representation of the `Comment` instance.
        :rtype: Dict[str, Any]
        """
        # to ensure that deleted comments are represented as deleted
        data = super().to_representation(instance)
        if instance.is_deleted:
            data["content"] = "[deleted]"
            data["user"] = None
        return data


class CommentSerializer(ReactionAnnotationMixin, serializers.ModelSerializer):
    user = CommentAuthorSerializer(read_only=True)
    mentions = CommentMentionSerializer(read_only=True, many=True)
    replies = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()

    reactions_count = serializers.SerializerMethodField()
    reactions_breakdown = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "content",
            "parent",
            "is_edited",
            "is_deleted",
            "created_at",
            "updated_at",
            "mentions",
            "replies",
            "replies_count",
            "reactions_count",
            "reactions_breakdown",
            "user_reaction",
        ]
        read_only_fields = fields

    # get the replies for the given comment
    def get_replies(self, comment: Comment) -> ReturnList | ReturnDict:
        """
        Retrieve and serialize all replies associated with a specific comment.

        The method collects all replies linked to the given comment and serializes
        them using the provided serializer. It includes the necessary context
        for serialization.

        :param comment: The comment whose replies are to be retrieved and serialized.
        :type comment: Comment
        :return: A serialized list or a dictionary containing the replies. The format
            depends on the serializer's implementation.
        :rtype: ReturnList | ReturnDict
        """
        replies = comment.replies.all()
        return ReplySerializer(replies, many=True, context=self.context).data

    def get_replies_count(self, comment: Comment) -> int:
        """
        Retrieves the number of replies associated with a given comment. If the
        comment has a precomputed 'replies_count' attribute, it utilizes that value
        for efficiency. Otherwise, it calculates the count dynamically by
        accessing the comment's replies.

        :param comment: The Comment object for which the number of replies is to
            be determined.
        :type comment: Comment
        :return: The total number of replies associated with the comment.
        :rtype: int
        """
        count: int | None = getattr(comment, "replies_count", None)
        if count is not None:
            return count
        return comment.replies.count()

    def to_representation(self, instance: Comment) -> dict[str, Any]:
        """
        Transforms the provided Comment instance into a dictionary representation with
        modifications for deleted comments.

        The method checks if the comment instance is marked as deleted. If so,
        it replaces the value of the "content" key with "[deleted]" and sets
        the "user" key to None in the returned dictionary. Otherwise, it proceeds
        with the normal representation of the instance.

        :param instance: A Comment instance to be represented
        :type instance: Comment
        :return: A dictionary representation of the Comment instance with special
                 handling for deleted comments
        :rtype: Dict[str, Any]
        """
        data = super().to_representation(instance)
        if instance.is_deleted:
            data["content"] = "[deleted]"
            data["user"] = None
        return data


# serializer for creating the comments
class CommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating comments.

    Handles the creation of comments, including validations for the content and parent
    comment, and ensures proper association with the post and user. The serializer
    supports adding top-level comments and replying to comments with certain
    restrictions.

    :ivar Meta.model: The database model associated with this serializer.
    :type Meta.model: Comment

    :ivar Meta.fields: The fields that are serialized and deserialized.
    :type Meta.fields: list
    """

    class Meta:
        model = Comment
        fields = ["content", "parent"]

    def validate_content(self, value: str) -> str:
        """
        Validates and processes the given content by stripping whitespace and checking for emptiness.

        :param value: The string content to be validated and processed. Must be stripped of excessive
                      whitespace and non-empty.
        :return: The stripped string content if validation passes.
        :raises serializers.ValidationError: If the given content is an empty string after stripping.
        """
        stripped_comment = value.strip()
        if not stripped_comment:
            raise serializers.ValidationError(
                "Comment content cannot be empty."
            )
        return stripped_comment

    def validate_parent(self, parent: Comment | None) -> Comment | None:
        """
        Validates the parent comment to ensure it meets specific constraints such as
        not being deleted, not creating nested replies, and belonging to the correct
        post. This function is used to ensure the integrity and hierarchy of comments.

        :param parent: The parent comment to validate.
        :type parent: Optional[Comment]
        :return: The validated parent comment if it passes all checks; `None` if no
                 parent is provided.
        :rtype: Optional[Comment]
        :raises serializers.ValidationError: If the parent comment is deleted, creates
                                             a nested reply, or does not belong to the
                                             expected post.
        """
        if parent is None:
            return None
        if parent.is_deleted:
            raise serializers.ValidationError(
                "Cannot reply to a deleted comment."
            )
        if parent.parent_id is not None:
            # nested version is there
            # cannot nest further
            raise serializers.ValidationError(
                "Replies to replies are not allowed. Reply to the top-level "
                "comment and @mention the user you're responding to."
            )
        expected_post_id = self.context.get("post_id")
        if expected_post_id is not None and parent.post_id != expected_post_id:
            raise serializers.ValidationError(
                "Parent comment does not belong to this post"
            )
        return parent

    # create the comment
    def create(self, validated_data: dict[str, Any]) -> Comment:
        """
        Creates a new comment for a specific post made by a user. This method utilizes
        a database transaction to ensure atomicity during the comment creation process.
        Additionally, it processes any mentions included in the comment content.

        :param validated_data: A dictionary containing the validated fields required
                               to create the comment.
        :type validated_data: Dict[str, Any]

        :return: The newly created Comment instance.
        :rtype: Comment
        """

        # get the user who will comment
        user: User = self.context["request"].user
        # get the post where the comment is being made
        post: Post = self.context[
            "post"
        ]  # this context is getting added in the calling view

        with transaction.atomic():
            # creating the comment
            comment = Comment.objects.create(
                user=user, post=post, **validated_data
            )
            sync_mentions(comment)  # adding comment mention for the comment

        return comment

    def to_representation(self, instance) -> ReturnDict:
        """
        Transforms an instance into its serialized representation using the
        `CommentSerializer`.

        :param instance: The data instance to be serialized.
        :type instance: Model
        :return: Serialized representation of the given instance as a dictionary-like
                 object.
        :rtype: ReturnDict
        """
        return CommentSerializer(instance, context=self.context).data


# creating serializer for comment update
class CommentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating Comment objects.

    This serializer is designed to handle the update operation of the `Comment` model.
    It ensures that the content of a comment is appropriately validated, updates the necessary
    fields of the `Comment` model, and synchronizes mentions in the updated comment.
    """

    class Meta:
        model = Comment
        fields = ["content"]

    def validate_content(self, value: str) -> str:
        """
        Validates the provided content by ensuring it is not an empty or whitespace-only
        string. The input is stripped of leading and trailing whitespace before validation.

        :param value: The input string to be validated.
        :type value: str
        :raises serializers.ValidationError: If the stripped content is empty or consists
            solely of whitespace characters.
        :return: The validated and stripped string content.
        :rtype: str
        """
        stripped_comment = value.strip()
        if not stripped_comment:
            raise serializers.ValidationError(
                "Comment content cannot be empty."
            )
        return stripped_comment

    def update(
        self, instance: Comment, validated_data: dict[str, Any]
    ) -> Comment:
        """
        Update a Comment instance with new validated data.

        This method updates the content of a Comment instance if the new content
        differs from the current content. If the content is updated, the instance is
        marked as edited, and relevant fields are saved to the database within an
        atomic transaction. Additionally, it ensures that mentions in the comment
        are synchronized after the update.

        :param instance: The Comment instance to be updated.
        :param validated_data: A dictionary containing validated data for updating
                               the Comment instance.
        :return: The updated Comment instance.
        """
        new_content = validated_data.get("content", instance.content)
        if new_content != instance.content:
            with transaction.atomic():
                instance.content = new_content
                instance.is_edited = True
                instance.save(
                    update_fields=[
                        "content",
                        "is_edited",
                        "updated_at",
                    ]
                )
                sync_mentions(instance)

        return instance

    def to_representation(self, instance) -> ReturnDict:
        """
        Transforms the given instance into its serialized representation using the
        ``CommentSerializer`` and the provided context.

        :param instance: The instance to be serialized. Expected to be an object
            compatible with the ``CommentSerializer``.
        :return: The serialized representation of the instance as a ``ReturnDict``.
        :rtype: ReturnDict
        """
        return CommentSerializer(instance, context=self.context).data


class PostAuthorSerializer(serializers.ModelSerializer):
    """
    Serializes and formats author data for a post, including basic user information and
    a presigned URL for the user's avatar image.

    This serializer subclasses `serializers.ModelSerializer` and provides a custom
    field `avatar_url` to include a presigned read URL for the user's avatar image,
    facilitating secure access to avatar resources stored in an S3 bucket.

    :ivar avatar_url: Presigned URL for the user's avatar image. Computed using
        a custom method.
    :type avatar_url: SerializerMethodField
    """

    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "avatar_url",
        ]
        read_only_fields = fields

    def get_avatar_url(self, user: User) -> str | None:
        """
        Gets the avatar URL of a given user, returning a presigned read URL to access
        the avatar image stored in an S3 bucket. If the user does not have a profile
        or an associated avatar, returns None.

        :param user: The User instance for which the avatar URL needs to be fetched.
        :type user: User
        :return: A presigned URL to access the avatar image if it exists, else None.
        :rtype: Optional[str]
        """
        profile: Profile | None = getattr(user, "profile", None)
        if profile is None or profile.avatar_id is None:
            return None

        return generate_presigned_read_url(profile.avatar.s3_key)


class PostMediaSerializer(serializers.ModelSerializer):
    """
    Serializer for PostMedia model.

    This serializer is used to map the `PostMedia` model to JSON-compatible
    data structures. It includes fields related to the associated media details
    and provides a method for generating a signed URL to access the media.

    :ivar media_id: The unique identifier of the associated media.
    :type media_id: UUID
    :ivar media_type: The type of the associated media (e.g., image, video).
    :type media_type: str
    :ivar content_type: The MIME type of the associated media.
    :type content_type: str
    :ivar size: The file size of the associated media, in bytes.
    :type size: int
    :ivar url: The presigned URL for accessing the associated media file.
    :type url: str
    """

    media_id = serializers.UUIDField(source="media.id", read_only=True)
    media_type = serializers.CharField(
        source="media.media_type", read_only=True
    )
    content_type = serializers.CharField(
        source="media.content_type", read_only=True
    )
    size = serializers.IntegerField(source="media.file_size", read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = PostMedia
        fields = [
            "id",
            "media_id",
            "media_type",
            "content_type",
            "size",
            "position",
            "url",
        ]
        read_only_fields = fields

    def get_url(self, post_media: PostMedia) -> str:
        """
        Generate a pre-signed URL for reading media content.

        This method generates a pre-signed read URL for the media associated with
        the provided PostMedia instance. The URL is generated using the S3 key of
        the media.

        :param post_media: The PostMedia instance containing the media for which
            the pre-signed URL will be generated.
        :type post_media: PostMedia
        :return: A pre-signed read URL for the media content.
        :rtype: str
        """
        return generate_presigned_read_url(post_media.media.s3_key)


class PostSerializer(ReactionAnnotationMixin, serializers.ModelSerializer):
    """
    Serializer for handling the serialization and deserialization of Post model data.

    This serializer is responsible for processing data related to the Post model,
    ensuring that model instances can be serialized into JSON or other formats and
    deserialized back into Python objects. It also manages read-only fields, nested
    serializers for related objects, and the inclusion of specific attributes for
    serialization. This serializer is particularly useful for implementing APIs.

    :ivar author: Nested serializer for the author of the post. Read-only.
    :type author: PostAuthorSerializer
    :ivar media: Nested serializer for associated media of the post. Read-only, supports
        multiple entries.
    :type media: PostMediaSerializer
    """

    author = PostAuthorSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)

    reactions_count = serializers.SerializerMethodField()
    reactions_breakdown = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "content",
            "visibility",
            "adult_rating",
            "status",
            "published_at",
            "is_edited",
            "created_at",
            "updated_at",
            "media",
        ]
        read_only_fields = [
            "id",
            "author",
            "media",
            "status",
            "published_at",
            "is_edited",
            "created_at",
            "updated_at",
        ]

    def get_comments_count(self, post: Post) -> int:
        """
        Get the total number of comments for the given post.

        First, it checks the attribute `comments_count` in the provided `post` object.
        If the attribute exists and has a non-falsy value, it is returned. Otherwise, 0 is
        returned as the default when the attribute is missing or is falsy.

        :param post: The post object from which to retrieve the comments count.
        :type post: Post
        :return: The total number of comments for the given post. Defaults to 0 if the
            attribute is missing or falsy.
        :rtype: int
        """
        return getattr(post, "comments_count", 0) or 0


class PostCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and validating Post objects.

    This serializer is responsible for validating the input data required to create a
    Post object and its related media attachments. It manages the validation process to
    ensure that both content and media IDs meet the application's requirements and enforces
    business logic, such as ownership, upload status, namespace restrictions, and attachment
    count limits. Additionally, it defines the creation process for associating media with
    posts, utilizing atomic transactions for consistency.

    :ivar media_ids: UUID of media rows to attach to this post. Each row must be owned by
        the requester, completed in upload state, and stored under the "posts/" folder.
        The media in this list will determine the order for PostMedia.position.
    :type media_ids: List[str]
    """

    media_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        allow_empty=True,
        help_text=(
            "UUID of media rows to attach to this post. "
            "Each row must be owned by the requester, COMPLETED, and live "
            "in the posts/ folder. Order in this list becomes PostMedia.position."
        ),
    )

    class Meta:
        model = Post
        fields = [
            "content",
            "visibility",
            "adult_rating",
            "status",
            "media_ids",
        ]

    def validate_content(self, value: str) -> str:
        """
        Validates and processes input content.

        This method removes any leading and trailing whitespace characters
        from the provided string to ensure clean and standardized content.

        :param value: The string input to be validated and processed.
        :type value: str
        :return: The processed string with leading and trailing whitespace
            removed.
        :rtype: str
        """
        return value.strip()

    def validate_media_ids(self, ids: list[str]) -> list[str]:
        """
        Validates a list of media IDs to ensure that there are no duplicates. If duplicates
        are found, a ValidationError is raised. Returns the validated list of media IDs.

        :param ids: List of media IDs to validate
        :type ids: List[str]
        :return: The validated list of media IDs
        :rtype: List[str]
        :raises serializers.ValidationError: If the list contains duplicate media IDs
        """
        if len(ids) != len(set(ids)):
            # contains duplicates
            raise serializers.ValidationError(
                "Duplicate media_ids are not allowed"
            )
        return ids

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Validates the given attributes for creating or updating a post object. Ensures that the
        post meets content or media attachment requirements, verifies media ownership, upload
        status, storage location, and enforces attachment count limits.

        :param attrs: A dictionary of attributes for the post containing fields such as
            "content" (optional) and "media_ids" (optional).
        :type attrs: Dict[str, Any]

        :return: A validated dictionary of attributes with an added key "media_by_id", mapping
            media IDs to their corresponding media objects.
        :rtype: Dict[str, Any]

        :raises serializers.ValidationError: If the post does not have either content or media
            attachments, if any media attachments do not belong to the current user, if any
            media attachments are not in the "COMPLETED" upload state, if any media attachments
            are stored outside the "posts/" namespace, or if the count of images or videos
            exceeds the defined maximum limits as per settings.
        """
        content = attrs.get("content", "")
        media_ids = attrs.get("media_ids", [])

        if not content and not media_ids:
            raise serializers.ValidationError(
                "A post must have either text content or at least one media attachment."
            )

        if not media_ids:
            return attrs

        author: User = self.context["request"].user
        media_rows = list(
            Media.objects.filter(id__in=media_ids, uploaded_by=author)
        )

        found_ids = {media.id for media in media_rows}
        missing_media_ids = [mid for mid in media_ids if mid not in found_ids]

        if missing_media_ids:
            raise serializers.ValidationError(
                {
                    "media_ids": f"Media not found or not owned by you: {missing_media_ids}"
                }
            )

        for current_media in media_rows:
            if current_media.upload_status != Media.UploadStatus.COMPLETED:
                raise serializers.ValidationError(
                    {
                        "media_ids": (
                            f"Media {current_media.id} is not in COMPLETED state "
                            f"f(currently {current_media.upload_status}). Finish the "
                            "upload via /api/media/confirm/ first."
                        )
                    }
                )

            if not current_media.s3_key.startswith("posts/"):
                raise serializers.ValidationError(
                    {
                        "media_ids": (
                            f"Media {current_media.id} has s3 key {current_media.s3_key!r} which "
                            "is not in the posts/ namespace. Re-upload "
                            "with folder='posts'."
                        )
                    }
                )

        # will allow max 10 images
        image_count = sum(
            1
            for media in media_rows
            if media.media_type == Media.MediaType.IMAGE
        )

        # will allow max 4 videos
        video_count = sum(
            1
            for media in media_rows
            if media.media_type == Media.MediaType.VIDEO
        )

        if image_count > settings.POSTS_MAX_IMAGES_PER_POST:
            raise serializers.ValidationError(
                f"A post can have at most {settings.POSTS_MAX_IMAGES_PER_POST} images."
            )

        if video_count > settings.POSTS_MAX_VIDEOS_PER_POST:
            raise serializers.ValidationError(
                f"A post can have at most {settings.POSTS_MAX_VIDEOS_PER_POST} videos."
            )

        attrs["media_by_id"] = {m.id: m for m in media_rows}
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Post:
        """
        Creates a new Post instance with its associated media and metadata.

        This method handles the creation of a new post, associating it with the author,
        assigning media items to the post, and setting the publishing status and timestamp
        if the post is being published. It performs these operations within an atomic
        transaction to ensure data consistency.

        :param validated_data: A dictionary containing the data to create the post.
            It includes details such as media IDs, metadata, and publication status.
        :return: The created Post instance.
        :rtype: Post
        """
        media_ids = validated_data.pop("media_ids", [])
        media_by_id = validated_data.pop("media_by_id", {})
        author: User = self.context["request"].user

        # check if the post is published or not
        if (
            validated_data.get("status", Post.Status.PUBLISHED)
            == Post.Status.PUBLISHED
        ):
            validated_data["published_at"] = timezone.now()

        # updating the relevant media and all other stuff
        with transaction.atomic():
            post = Post.objects.create(author=author, **validated_data)

            join_rows = [
                PostMedia(
                    post=post,
                    media=media_by_id[media_id],
                    position=index,
                )
                for index, media_id in enumerate(media_ids)
            ]

            PostMedia.objects.bulk_create(join_rows)

        return post

    def to_representation(self, instance: Post) -> dict[str, Any]:
        return PostSerializer(instance, context=self.context).data


class PostUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating Post instances.

    This serializer is designed for handling updates to `Post` model instances. It validates
    the input data, processes updates to the specified fields, marks the instance as edited,
    and provides custom representation of the updated instance data.

    Allows only editing the content, visibility, and adult rating. Media attachments
    are immutable once the post is created, and therefore cannot be edited / added.
    """

    class Meta:
        model = Post
        fields = ["content", "visibility", "adult_rating"]

    def validate_content(self, value: str) -> str:
        """
        Validates and trims the input string content.

        This method ensures that leading and trailing whitespace
        characters are removed from the provided string.

        :param value: The string content to be validated and trimmed.
        :type value: str
        :return: The trimmed string with leading and trailing whitespace removed.
        :rtype: str
        """
        return value.strip()

    def update(self, instance: Post, validated_data: dict[str, Any]) -> Post:
        """
        Updates an instance of the Post class with the provided validated data. The method
        iterates over the validated_data items and updates the corresponding attributes of
        the instance. Additionally, it sets the is_edited attribute to True and saves the
        updated instance to the database.

        :param instance: The Post instance that will be updated.
        :type instance: Post
        :param validated_data: A dictionary containing the data to update the instance with.
        :type validated_data: Dict[str, Any]
        :return: The updated Post instance.
        :rtype: Post
        """
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.is_edited = True
        instance.save()
        return instance

    def to_representation(self, instance: Post) -> dict[str, Any]:
        """
        Transforms a given Post instance into a serializable dictionary format using
        the PostSerializer. This is used to represent the Post instance as structured
        data, typically for use in API responses or other serialization contexts.

        :param instance: The Post object to be serialized.
        :type instance: Post
        :return: A dictionary representation of the Post instance.
        :rtype: dict[str, Any]
        """
        return PostSerializer(instance, context=self.context).data
