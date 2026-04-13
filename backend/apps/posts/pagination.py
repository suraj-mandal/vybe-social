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
