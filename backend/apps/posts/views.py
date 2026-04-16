from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from posts.pagination import RepliesCursorPagination
from posts.selectors import replies_for_comment
from posts.serializers import ReplySerializer
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
)
from apps.posts.permissions import CanCommentOnPost, IsAuthorOrReadOnly
from apps.posts.selectors import (
    accessible_posts_for,
    comments_for_post,
    drafts_for,
    publish_post,
    reactions_for_target,
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
    permission_classes = [IsAuthenticated]

    def get_target(self, request: Request, pk: str):
        raise NotImplementedError

    def post(self, request: Request, pk: str):
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
    permission_classes = [IsAuthenticated]
    pagination_class = ReactionCursorPagination
    serializer_class = ReactionSerializer

    def get_target(self): ...

    def get_queryset(self):
        target = self.get_target()
        if target is None:
            return Reaction.objects.none()

        query_set = reactions_for_target(target)

        type_filter = self.request.query_params.get("type")

        if type_filter:
            if type_filter not in Reaction.Type.values:
                raise ValidationError(
                    {"type": f"must be one of {list(Reaction.Type.values)}"}
                )
            query_set = query_set.filter(type=type_filter)

        return query_set


class PostReactionsListView(_BaseReactionListView):
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
    def get_target(self, request: Request, pk: str) -> Post:
        request_user: User = request.user  # type: ignore[assignment]
        post = visible_posts_for(request_user).filter(pk=pk).first()
        if post is None:
            raise NotFound()
        return post


class CommentReactionView(_BaseReactionView):
    def get_target(self, request: Request, pk: str) -> Comment:
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
        pk = self.kwargs["pk"]
        request_user: User = self.request.user  # type: ignore[assignment]
        post = visible_posts_for(user=request_user).filter(pk=pk).first()

        if post is None:
            raise NotFound()

        return post

    def get_serializer_class(self):
        # getting the serializers based on the request method type
        if self.request.method == "POST":
            return CommentCreateSerializer
        return CommentSerializer

    def get_queryset(self):
        post = self._get_post()
        request_user: User = self.request.user  # type: ignore[assignment]
        return comments_for_post(user=request_user, post=post)

    def get_serializer_context(self):
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
        # get_object internally will call get_queryset and then check for the permissions
        # as well, so let DRF handle that part.
        return Comment.objects.select_related(
            "user__profile__avatar"
        ).prefetch_related("mentions__user")

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CommentUpdateSerializer
        return CommentSerializer

    def perform_destroy(self, instance: Comment) -> None:
        instance.delete()  # soft-delete works here, since Comment.delete method is overridden


# view representing the replies for the comment
class CommentRepliesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = RepliesCursorPagination
    serializer_class = ReplySerializer

    def _get_parent(self) -> Comment:
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
        parent = self._get_parent()
        request_user: User = self.request.user  # type: ignore[assignment]
        return replies_for_comment(user=request_user, parent=parent)
