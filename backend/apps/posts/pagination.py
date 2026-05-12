from django.conf import settings
from rest_framework.pagination import CursorPagination


class PostCursorPagination(CursorPagination):
    """
    Pagination class for handling cursor-based pagination of posts.

    This class is used to paginate collections of posts efficiently by employing
    a cursor mechanism. It determines the size of each page, the ordering of the
    retrieved items, and the query parameter used for the cursor.

    :ivar page_size: Number of posts to display per page. This is configured
        through the POSTS_PAGE_SIZE setting.
    :type page_size: int
    :ivar ordering: Tuple defining the default ordering of posts. Posts are ordered
        by descending creation timestamp and then by ascending ID.
    :type ordering: tuple
    :ivar cursor_query_param: Name of the query parameter used for the pagination
        cursor.
    :type cursor_query_param: str
    """

    page_size = settings.POSTS_PAGE_SIZE
    ordering = ("-created_at", "id")
    cursor_query_param = "cursor"


# pagination for reactions
class ReactionCursorPagination(CursorPagination):
    """
    ReactionCursorPagination manages pagination for reaction records.

    This class is specifically designed to provide cursor-based pagination
    functionality, allowing for efficient querying of reaction records in a list.
    It uses specified ordering and pagination settings for optimized performance
    and user experience.

    :ivar page_size: The number of records to include on a single page, based on
        the REACTIONS_PAGE_SIZE setting.
    :type page_size: int
    :ivar ordering: The fields to order query results by. Records will be ordered
        first by `-created_at` in descending order and then by `id`.
    :type ordering: tuple
    :ivar cursor_query_param: The query parameter name used to provide the cursor
        for accessing paginated results.
    :type cursor_query_param: str
    """

    page_size = settings.REACTIONS_PAGE_SIZE
    ordering = ("-created_at", "id")
    cursor_query_param = "cursor"


# pagination for comments
class CommentCursorPagination(CursorPagination):
    page_size = settings.COMMENTS_PAGE_SIZE
    ordering = ("-created_at", "-id")
    cursor_query_param = "cursor"


# pagination for comment replies
class RepliesCursorPagination(CursorPagination):
    """
    Provides cursor-based pagination for replies.

    This class is designed to paginate the replies in a specific comment
    and supports custom cursor query parameters. The page size is determined
    by application settings.

    :ivar page_size: Number of items per page for pagination.
    :type page_size: int
    :ivar ordering: Ordering criteria for pagination, defined as a tuple of field names.
    :type ordering: tuple
    :ivar cursor_query_param: Query parameter used to pass the cursor for pagination.
    :type cursor_query_param: str
    """

    page_size = settings.REPLIES_PAGE_SIZE
    ordering = (
        "-created_at",
        "-id",
    )
    cursor_query_param = "cursor"
