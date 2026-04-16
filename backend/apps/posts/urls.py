from django.urls import path

from apps.posts import views

app_name = "posts"

urlpatterns = [
    path("", views.PostListCreateView.as_view(), name="post-list-create"),
    path("drafts/", views.DraftListView.as_view(), name="post-drafts"),
    path("<uuid:pk>/", views.PostDetailView.as_view(), name="post-detail"),
    path(
        "<uuid:pk>/publish/",
        views.PublishPostView.as_view(),
        name="post-publish",
    ),
    # reactions on posts
    path(
        "<uuid:pk>/reactions/",
        views.PostReactionView.as_view(),
        name="post-react",
    ),
    path(
        "<uuid:pk>/reactions/list",
        views.PostReactionsListView.as_view(),
        name="post-reactions-list",
    ),
    # comments on posts
    path(
        "<uuid:pk>/comments/",
        views.PostCommentsView.as_view(),
        name="post-comments",
    ),
]
