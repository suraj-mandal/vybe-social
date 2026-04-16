from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.friendships.models import FriendRequest
from apps.posts.models import Comment, Post, Reaction
from apps.posts.pagination import (
    CommentCursorPagination,
    PostCursorPagination,
    ReactionCursorPagination,
    RepliesCursorPagination,
)
from apps.posts.permissions import CanCommentOnPost, IsAuthorOrReadOnly
from apps.posts.selectors import (
    accessible_posts_for,
    comments_for_post,
    drafts_for,
    publish_post,
    reactions_for_target,
    replies_for_comment,
    visible_posts_for,
)
from apps.posts.serializers import (
    CommentCreateSerializer,
    CommentSerializer,
    CommentUpdateSerializer,
    PostCreateSerializer,
    PostSerializer,
    PostUpdateSerializer,
    ReactionSerializer,
    ReactionUpsertSerializer,
    ReplySerializer,
)

FEED_SOURCES = {
    "all",
    "mine",
    "friends",
}

FEED_ORDERINGS = {
    "new",
    "relevance",
}


class _BaseReactionView(APIView):
    """
    Represents a base view for handling user reactions to specific targets.

    This class provides a foundational set of methods for managing reactions such
    as creating, updating, and deleting reactions for a given target. It is
    designed to ensure authenticated access and transactional integrity.

    :ivar permission_classes: Defines the permission classes required to
        access the view. By default, it ensures that only authenticated users
        can interact with this view.
    :type permission_classes: List[permissions.BasePermission]
    """

    permission_classes = [IsAuthenticated]

    def get_target(self, request: Request, pk: str):
        raise NotImplementedError

    def post(self, request: Request, pk: str):
        """
        Handles the creation or update of a reaction for a specified target object. The method
        first validates the request data using a serializer, then determines the reaction type
        to be added or updated. The target object is identified based on a provided primary
        key, and a database transaction is used to ensure atomicity when creating or updating
        the reaction. The method finally returns a serialized response containing the updated
        reaction and the appropriate HTTP status code.

        :param request: The HTTP request instance containing user, data, and metadata.
        :param pk: The primary key identifying the target object for which the reaction
            is being created or updated.
        :return: A serialized response containing the reaction data and a status
            code indicating whether the reaction was created (HTTP 201) or updated (HTTP 200).
        """
        target = self.get_target(request, pk)

        serializer = ReactionUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reaction_type = serializer.validated_data["type"]

        content_type = ContentType.objects.get_for_model(type(target))

        with transaction.atomic():
            reaction, created = Reaction.objects.update_or_create(
                user=request.user,
                content_type=content_type,
                object_id=target.pk,
                defaults={"type": reaction_type},
            )

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

        return Response(
            ReactionSerializer(reaction, context={"request": request}).data,
            status=status_code,
        )

    def delete(self, request, pk):
        """
        Handles the deletion of a reaction associated with a specific target object and user.
        Deletes the reaction data from the database and returns an appropriate HTTP response.

        :param request: The HTTP request object containing user and request data.
        :type request: HttpRequest
        :param pk: The primary key of the target object for which the reaction is to be deleted.
        :type pk: int
        :return: An HTTP response indicating that the reaction has been successfully deleted.
        :rtype: Response
        """
        target = self.get_target(request, pk)
        content_type = ContentType.objects.get_for_model(type(target))
        Reaction.objects.filter(
            user=request.user,
            content_type=content_type,
            object_id=target.pk,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# reaction list base view
class _BaseReactionListView(generics.ListAPIView):
    """
    Represents a base view for listing reactions associated with a target object.

    This class is a specialized ListAPIView designed to retrieve and display reactions
    associated with a specific target object. It provides functionality to filter reactions
    based on type, ensuring only valid reaction types are considered.

    The queryset is dynamically constructed based on the specific target object and
    query parameters provided in the request.

    :ivar permission_classes: Specifies the permissions required to access this view.
    :type permission_classes: list

    :ivar pagination_class: Defines the pagination class used for the view to manage
        paginated response for large datasets.
    :type pagination_class: type

    :ivar serializer_class: Specifies the serializer used to transform the Reaction objects
        into representations suitable for API responses.
    :type serializer_class: type
    """

    permission_classes = [IsAuthenticated]
    pagination_class = ReactionCursorPagination
    serializer_class = ReactionSerializer

    def get_target(self): ...

    def get_queryset(self):
        """
        Retrieves and filters a queryset of reactions based on a target object and an optional
        type filter provided through request query parameters.

        The method fetches a target object using the `get_target` method and retrieves the
        associated reactions using the `reactions_for_target` function. If a type filter
        is provided in the query parameters, it ensures the filter is valid and applies it
        to the reactions queryset. If the target object is not found, an empty queryset
        is returned.

        :raises ValidationError: If the `type` filter provided in query parameters is not
            among the valid values specified in `Reaction.Type`.

        :return: A queryset of reactions filtered by the provided target and type parameters.
        :rtype: QuerySet
        """
        target = self.get_target()
        if target is None:
            return Reaction.objects.none()

        query_set = reactions_for_target(target)

        type_filter = self.request.query_params.get("type")

        if type_filter:
            if type_filter not in Reaction.Type.values:
                raise ValidationError(
                    {"type": f"must be one of {list(Reaction.Type)}"}
                )
            query_set = query_set.filter(type=type_filter)

        return query_set


class PostReactionsListView(_BaseReactionListView):
    """
    Handles the listing of reaction data associated with a specific post.

    This class acts as a view to retrieve and display the reactions to a specific
    post that is visible to the requesting user. It filters the posts based on
    visibility and returns the first match according to the given primary key.
    """

    def get_target(self):
        pk = self.kwargs["pk"]
        request_user: User = self.request.user  # type: ignore[assignment]
        return visible_posts_for(user=request_user).filter(pk=pk).first()


class CommentReactionsListView(_BaseReactionListView):
    """

    GET /api/comments/<uuid:pk>/reactions/list/

    pk - represents the id of the comment whose reactions, we want to see.

    Provides a mechanism to fetch and list reactions for a specific comment. This
    view verifies the visibility of the associated post for the requesting user
    before returning a comment, ensuring appropriate access control.

    :ivar kwargs: Dictionary containing keyword arguments passed to the view.
    :type kwargs: dict
    :ivar request: The HTTP request object for the current request.
    :type request: django.http.HttpRequest
    """

    def get_target(self):
        """
        Fetches the comment based on the provided primary key while ensuring visibility
        permissions for the user. The method verifies if the user has access to the
        comment's associated post before returning the comment instance.

        :return: The comment instance if the user has visibility to the associated
            post; otherwise, None.
        :rtype: Optional[Comment]
        """

        # get the comment which will behave as the target for fetching
        # the list of comments.

        pk = self.kwargs["pk"]
        comment = Comment.objects.filter(pk=pk).first()
        if comment is None:
            return None
        request_user: User = self.request.user  # type: ignore[assignment]
        # check if the post is visible for the user or not, if not then they cannot
        # get information about the comment details as well.
        post_visible = (
            visible_posts_for(user=request_user)
            .filter(pk=comment.post_id)
            .exists()
        )
        return comment if post_visible else None


class PostReactionView(_BaseReactionView):
    """
    Handles actions related to reactions on posts.

    This class provides functionalities to interact with reactions on posts, including
    retrieving the target post for a reaction based on request data. It interacts with
    the existing visibility rules to ensure the post is accessible to the requesting user.

    """

    def get_target(self, request: Request, pk: str) -> Post:
        request_user: User = request.user  # type: ignore[assignment]
        post = visible_posts_for(request_user).filter(pk=pk).first()
        if post is None:
            raise NotFound()
        return post


class CommentReactionView(_BaseReactionView):
    """
    Provides functionality for managing reactions on comments. Ensures that
    the comment exists and the associated post is visible to the requesting
    user before allowing further operations.
    """

    def get_target(self, request: Request, pk: str) -> Comment:
        """
        Retrieve a comment by its primary key if it is accessible to the requesting user.

        A comment is considered accessible if its associated post is visible to the
        requesting user. If the comment does not exist or the post is not visible to
        the user, a NotFound exception will be raised.

        :param request: The HTTP request object containing the user instance.
        :type request: Request
        :param pk: The primary key of the comment to retrieve.
        :type pk: str
        :return: The comment instance associated with the given primary key.
        :rtype: Comment
        :raises NotFound: If the comment does not exist or the associated post is not
                         visible to the requesting user.
        """
        comment = Comment.objects.select_related("post").filter(pk=pk).first()
        if comment is None:
            # no comment is found by the given id
            raise NotFound()

        request_user: User = request.user  # type: ignore[assignment]
        post_visible = (
            visible_posts_for(user=request_user)
            .filter(pk=comment.post_id)
            .exists()
        )

        if not post_visible:
            # the post is private so, comment cannot be updated here
            raise NotFound()

        # return the comment
        return comment


class PostListCreateView(generics.ListCreateAPIView):
    """
    GET /api/posts/ → list posts visible to the requester (cursor-paginated)

    Query params:
      ?source=all|mine|friends (default: all)
      ?ordering=new|relevance (default: new; `relevance` is a Phase 6d stub)

    POST /api/posts/ → create a new post (with optional media)

    Handles the listing and creation of posts with support for filtering and ordering.

    This view is designed to provide authenticated users access to posts, either authored
    by themselves or their friends depending on specified filters. It enforces permissions
    checks and provides pagination for the returned data. The client can filter posts
    based on the source (e.g., "mine", "friends") and can order the results (e.g., by
    "new" posts). If specific sources or orderings are not allowed, a validation error
    is raised.

    The view dynamically assigns serializers for different HTTP request methods, using
    a specific serializer for post-creation and another for listing posts.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = PostCursorPagination

    def get_queryset(self) -> QuerySet[Post]:
        """
        Retrieves a filtered and ordered queryset of posts visible to the requesting user. The queryset is filtered by the
        source specified in the query parameters and subsequently ordered based on the specified ordering.

        :param self: The current view instance.
        :return: A QuerySet of Post objects filtered and ordered based on the specified query parameters.

        :param ?source: A string query parameter indicating the source of the posts.
            Accepted values include:
                - "all" (default): Includes all visible posts.
                - "mine": Includes posts authored by the requesting user.
                - "friends": Includes posts authored by the friends of the requesting user.
        :raises ValidationError: If 'source' does not belong to the list of valid feed sources.

        :param ?ordering: A string query parameter indicating the preferred ordering of the posts.
            Possible values include:
                - "new" (default): Orders posts by their creation date in descending order.
                - Other valid feed ordering options defined in the global `FEED_ORDERINGS` set.
        :raises ValidationError: If 'ordering' does not belong to the list of valid feed orderings.
        """
        request_user: User = self.request.user  # type: ignore[assignment]

        # get list of visible posts
        visible_posts = visible_posts_for(request_user)

        # getting the query params
        source = self.request.query_params.get("source", "all")

        if source not in FEED_SOURCES:
            raise ValidationError(
                {"source": f"must be one of {sorted(FEED_SOURCES)}"}
            )

        match source:
            case "mine":
                visible_posts = visible_posts.filter(author=request_user)
            case "friends":
                friend_ids = FriendRequest.objects.friends_of(
                    request_user
                ).values_list("id", flat=True)
                visible_posts = visible_posts.filter(author_id__in=friend_ids)

        ordering = self.request.query_params.get("ordering", "new")

        if ordering not in FEED_ORDERINGS:
            raise ValidationError(
                {"ordering": f"must be one of {sorted(FEED_ORDERINGS)}"}
            )

        # as of now, not checking relevance, it will be added later
        return visible_posts

    def get_serializer_class(self):
        """
        Determine and return the appropriate serializer class based on the HTTP request method.

        This method evaluates if the current request method is a POST request. If so, it returns
        the `PostCreateSerializer` serializer class, which is designed specifically for handling
        data creation. For all other request methods, it defaults to returning the `PostSerializer`
        class to handle retrieving or existing data.

        :return: The serializer class corresponding to the HTTP request method.
        :rtype: Type[Serializer]
        """
        if self.request.method == "POST":
            return PostCreateSerializer
        return PostSerializer


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    - GET    /api/posts/<uuid>/  → post detail (visibility-checked; includes own drafts)
    - PUT    /api/posts/<uuid>/  → full update (author only)
    - PATCH  /api/posts/<uuid>/  → partial update (author only)
    - DELETE /api/posts/<uuid>/  → soft delete (author only)

    Uses `accessible_posts_for()` (not `visible_posts_for()`) so the author
    can fetch and edit their own drafts via this endpoint. Non-authors still
    receive 404 for drafts — the union filter returns a draft only if the
    requester is its author.
    """

    permission_classes = [IsAuthorOrReadOnly]
    lookup_field = "pk"

    def get_queryset(self) -> QuerySet[Post]:
        """
        Provides the queryset for retrieving posts accessible to the currently authenticated user.

        This method determines the list of posts that the current user has permissions
        to access, ensuring proper filtering according to the user's access levels.

        :return: A queryset of posts accessible to the current user.
        :rtype: QuerySet[Post]
        """
        request_user: User = self.request.user  # type: ignore[assignment]
        return accessible_posts_for(request_user)

    def get_serializer_class(self):
        """
        Determines and returns the appropriate serializer class for the request's method.

        If the HTTP method of the request is either "PUT" or "PATCH", this method
        returns the `PostUpdateSerializer` class. For all other HTTP methods, it
        returns the `PostSerializer` class.

        :return: The serializer class corresponding to the HTTP request method.
        :rtype: type
        """
        if self.request.method in ("PUT", "PATCH"):
            return PostUpdateSerializer
        return PostSerializer

    def perform_destroy(self, instance: Post) -> None:
        """
        Destroys the provided instance of the Post object by deleting it from
        the database. This is typically used to perform cleanup or remove
        an existing resource.

        :param instance: Instance of the Post object to be deleted.
        :type instance: Post
        :return: None
        """
        instance.delete()


class UserPostsListView(generics.ListAPIView):
    """
    GET /api/profiles/<username>/posts/ → posts by a specific user,
                                          visibility-filtered for the requester.

    Handles fetching and displaying a list of posts authored by a specific user.

    This view provides the functionality to retrieve posts authored by a specified
    user, applying visibility and access controls to ensure that the requesting
    user only views posts they are permitted to see. Pagination, authentication,
    and serialization are also handled within this class.

    :ivar permission_classes: The list of permission classes applied to this view.
                              It enforces that the requesting user must be authenticated.
    :type permission_classes: list
    :ivar pagination_class: The pagination class used to paginate the queryset of posts.
                            This ensures efficient rendering of large datasets.
    :type pagination_class: type
    :ivar serializer_class: The serializer class used to serialize the posts for response.
    :type serializer_class: type
    """

    permission_classes = [IsAuthenticated]
    pagination_class = PostCursorPagination
    serializer_class = PostSerializer

    def get_queryset(self) -> QuerySet[Post]:
        """
        Fetches the queryset of posts made by a specific user and applies visibility
        filters based on the requesting user's permission.

        The function retrieves posts authored by a specific user, indicated by their
        username, and performs filtering based on the visibility rules applicable
        to the requesting user.

        :param self: Represents the instance of the class the method belongs to.
        :return: A QuerySet containing the filtered posts made by the specified user.
        :rtype: QuerySet[Post]
        """
        username = self.kwargs["username"]
        target = get_object_or_404(User, username=username)
        request_user: User = self.request.user  # type: ignore[assignment]
        return visible_posts_for(request_user).filter(author=target)


class DraftListView(generics.ListAPIView):
    """
    GET /api/posts/drafts/ → the authenticated user's draft posts.

    This is a strictly author-scoped endpoint — there is no notion of viewing
    someone else's drafts. The queryset is built from `drafts_for(request.user)`
    and never touches `visible_posts_for()`, because drafts bypass the whole
    visibility / block model (they're invisible to everyone but the author by
    definition).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination

    def get_queryset(self) -> QuerySet[Post]:
        """
        Retrieves a queryset of draft posts accessible by the current request's user.

        This function fetches the drafts for the authenticated user associated
        with the current request. It uses the `drafts_for` utility function
        to filter posts accordingly.

        :return: A queryset containing draft posts for the authenticated user.
        :rtype: QuerySet[Post]
        """
        request_user: User = self.request.user  # type: ignore[assignment]
        return drafts_for(request_user)


class PublishPostView(APIView):
    """
    POST /api/posts/<uuid>/publish/ → flip a draft to PUBLISHED.

    Author-only. Uses `visible_posts_for()` as the lookup base — which, because
    drafts are only visible to their author, naturally returns a 404 for:
      - Non-authors (draft is invisible to them)
      - Posts that don't exist
      - Posts authored by a blocked user (can't happen in practice since you
        can't have a draft from a user you've blocked, but the filter is free)

    Idempotent: publishing an already-published post returns 200 with the
    current state, not an error. This matches how most REST APIs handle
    idempotent transitions — easier for clients than having to remember which
    state the post is in before calling.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: str) -> Response:
        """
        Handles the publishing of a specific post by its primary key (PK) for the authorized
        user. Ensures that the post exists and belongs to the authenticated user before
        proceeding with the publishing operation.

        :param request: The HTTP request containing user information and context.
        :type request: Request
        :param pk: The primary key (PK) of the Post object to be published.
        :type pk: str
        :return: A Response object containing the serialized published post data and
            an HTTP 200 OK status code.
        :rtype: Response
        """
        post = get_object_or_404(Post, pk=pk, author=request.user)
        post = publish_post(post)

        return Response(
            PostSerializer(post, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# view representing the comments for a post
class PostCommentsView(generics.ListCreateAPIView):
    """
    GET /api/posts/<uuid:pk>/comments/ -> top-level comments + up to REPLIES_INLINE_PREVIEW
    POST /api/posts/<uuid:pk>/comments/ -> create a comment or a reply

    Handles listing and creating post comments.

    This view allows authenticated users to retrieve a paginated list of comments
    associated with a post or create new comments. Pagination is handled by the
    CommentCursorPagination class, providing cursor-based navigation through the
    comment set.

    :ivar permission_classes: List of permission classes required to access this
        view. Enforces authenticated user access.
    :type permission_classes: list
    :ivar pagination_class: The pagination class used to paginate the comments.
    :type pagination_class: type
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CommentCursorPagination

    def _get_post(self):
        """
        Retrieves a specific post that is visible to the currently authenticated user based
        on the primary key provided in the request's URL parameters. If the post does not
        exist or is not visible to the user, a NotFound error is raised.

        :raises NotFound: If the post with the given primary key does not exist or is
                          not visible to the current user.
        :return: The retrieved post that matches the primary key and is visible to
                 the requesting user.
        :rtype: Post
        """
        pk = self.kwargs["pk"]
        request_user: User = self.request.user  # type: ignore[assignment]
        post = visible_posts_for(user=request_user).filter(pk=pk).first()

        if post is None:
            raise NotFound()

        return post

    def get_serializer_class(self):
        """
        Determines and returns the appropriate serializer class based on the HTTP
        request method.

        This method checks the request method and provides the serializer class
        required to handle the processing of the request.

        :return: The serializer class corresponding to the request method.
        :rtype: type
        """

        # getting the serializers based on the request method type
        if self.request.method == "POST":
            return CommentCreateSerializer
        return CommentSerializer

    def get_queryset(self):
        """
        Retrieves the queryset of comments associated with a specific post for the current user.

        This method fetches the post object and constructs a queryset containing comments for
        the given post, filtered based on the user's permissions or context.

        :return: Queryset of comments for the specified post and user.
        :rtype: QuerySet
        """
        post = self._get_post()
        request_user: User = self.request.user  # type: ignore[assignment]
        return comments_for_post(user=request_user, post=post)

    def get_serializer_context(self):
        """
        Retrieves the serializer context with additional data when the request method is "POST".

        If the request method is "POST", this method performs object permission checking
        to verify if the requesting user is allowed to interact with the post. It also
        adds details about the post, including its ID, to the serializer's context.

        :return: A dictionary containing the serializer context, potentially augmented
            with additional data when the request method is "POST".
        :rtype: dict
        """
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            post = self._get_post()
            # check if the user can comment on the post or not
            self.check_object_permissions(self.request, post)
            # adding the post details to the context
            ctx["post"] = post
            ctx["post_id"] = post.id
        return ctx

    def get_permissions(self) -> list[BasePermission]:
        """
        Determines and returns the list of permissions required for the current request. The
        permissions are dynamically set based on the HTTP method of the request. By default,
        every request requires the user to be authenticated. Additional permissions are added
        depending on the specific method type.

        :returns: A list of permission classes specifying the access control for the current
            request.
        :rtype: list[BasePermission]
        """

        # dynamically setting the permissions based on the method type
        perms: list[BasePermission] = [IsAuthenticated()]
        if self.request.method == "POST":
            perms.append(CanCommentOnPost())
        return perms


# view representing the detail for the comment
class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/comments/<uuid:pk>/  → fetch a single comment
    PATCH  /api/comments/<uuid:pk>/  → edit content (author only)
    DELETE /api/comments/<uuid:pk>/  → soft delete (author only)

    Handles retrieval, update, and deletion of a specific comment.

    This class-based view allows authenticated users to retrieve, partially update, or delete a single comment object.
    It is designed to enforce permissions specified in `IsAuthenticated` and `IsAuthorOrReadOnly` to
    ensure that only authorized users can perform actions. The supported HTTP methods include GET, PATCH,
    DELETE, HEAD, and OPTIONS.

    :ivar permission_classes: A list of permission classes ensuring that the user is authenticated and has
        the appropriate permissions to interact with the comment object.
    :type permission_classes: list

    :ivar http_method_names: A list of allowed HTTP methods that can be used with this view.
    :type http_method_names: list
    """

    permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """
        Fetches and returns the queryset for Comment objects with related and prefetched data.

        This method is responsible for constructing a queryset that includes related data
        using `select_related` and `prefetch_related` to optimize database queries. It retrieves
        comments with their associated user profiles and avatars, as well as prefetches mentions
        and corresponding users.

        :return: A queryset of Comment objects with optimized related data fetching.
        :rtype: QuerySet
        """
        # get_object internally will call get_queryset and then check for the permissions
        # as well, so let DRF handle that part.
        return Comment.objects.select_related(
            "user__profile__avatar"
        ).prefetch_related("mentions__user")

    def get_serializer_class(self):
        """
        Determines and returns the appropriate serializer class based on the HTTP request method.

        If the request method is `PATCH`, the `CommentUpdateSerializer` class is returned.
        For all other methods, the `CommentSerializer` class is used.

        :return: The serializer class appropriate for the request method.
        :rtype: type
        """
        if self.request.method == "PATCH":
            return CommentUpdateSerializer
        return CommentSerializer

    def perform_destroy(self, instance: Comment) -> None:
        """
        Deletes the given instance by calling its delete method.

        This method will delete the provided instance of the Comment model,
        utilizing the overridden delete method to ensure the intended deletion
        process (e.g., soft-delete if implemented) is properly executed.

        :param instance: The Comment instance to be deleted.
        :return: None
        """
        instance.delete()  # soft-delete works here, since Comment.delete method is overridden


# view representing the replies for the comment
class CommentRepliesView(generics.ListAPIView):
    """
    Represents a view for listing replies to a specific comment.

    This class-based view fetches and paginates replies associated with a
    specific top-level comment. It ensures proper authentication and checks
    post visibility, allowing only authorized users to access replies.

    :ivar permission_classes: List of permissions required to access this view.
    :type permission_classes: list
    :ivar pagination_class: Specifies the pagination style used for listing replies.
    :type pagination_class: type
    :ivar serializer_class: The serializer class used for serializing the reply objects.
    :type serializer_class: type
    """

    permission_classes = [IsAuthenticated]
    pagination_class = RepliesCursorPagination
    serializer_class = ReplySerializer

    def _get_parent(self) -> Comment:
        """
        Retrieves the parent comment of a given comment based on its primary key, ensuring
        that the parent comment is valid and the associated post is visible to the
        requesting user.

        :param self: The instance of the ViewSet that contains the request and URL parameters.
        :return: The parent comment associated with the provided primary key in the URL if it
            exists and is accessible by the requesting user.
        :rtype: Comment
        :raises NotFound: If the parent comment does not exist, or the associated post is
            not visible to the requesting user.
        """
        pk = self.kwargs["pk"]
        parent = Comment.objects.filter(pk=pk, parent__isnull=True).first()
        if parent is None:
            raise NotFound()
        request_user: User = self.request.user  # type: ignore[assignment]
        post_visible = (
            visible_posts_for(user=request_user)
            .filter(pk=parent.post_id)
            .exists()
        )

        if not post_visible:
            raise NotFound()

        return parent

    def get_queryset(self) -> QuerySet[Comment]:
        """
        Retrieve a queryset of replies for a specific comment and user.

        This method fetches all replies that belong to a comment, based on the parent
        comment and the requesting user.

        :return: A queryset containing replies for the specified comment and user.
        :rtype: QuerySet[Comment]
        """
        parent = self._get_parent()
        request_user: User = self.request.user  # type: ignore[assignment]
        return replies_for_comment(user=request_user, parent=parent)
