from django.urls import path

from apps.posts import views

app_name = "comments"

urlpatterns = [
    path(
        "<uuid:pk>/",
        views.CommentDetailView.as_view(),
        name="comment-detail",
    ),
    path(
        "<uuid:pk>/reactions/",
        views.CommentReactionView.as_view(),
        name="comment-react",
    ),
    path(
        "<uuid:pk>/reactions/list/",
        views.CommentReactionsListView.as_view(),
        name="comment-reactions-list",
    ),
    path(
        "<uuid:pk>/replies/",
        views.CommentRepliesView.as_view(),
        name="comment-replies",
    ),
]
