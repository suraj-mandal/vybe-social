from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.media.models import Media
from apps.media.s3_service import generate_presigned_read_url
from apps.posts.models import Post, PostMedia


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
        profile = getattr(user, "profile", None)
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


class PostSerializer(serializers.ModelSerializer):
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
        return PostSerializer(instance, context=self.context).data
