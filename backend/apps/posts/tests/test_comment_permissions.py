from rest_framework.test import APIRequestFactory

from apps.posts.permissions import CanCommentOnPost
from apps.posts.tests._base import PostCommentTestBase


class TestCanCommentOnPost(PostCommentTestBase):
    def setUp(self):
        super().setUp()
        self.perm = CanCommentOnPost()
        self.factory = APIRequestFactory()
