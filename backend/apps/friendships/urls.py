from django.urls import path

from apps.friendships import views

app_name = "friendships"

urlpatterns = [
    path("request/<uuid:user_id>/", views.SendFriendRequestView.as_view(), name="send-request"),
    path("accept/<uuid:request_id>/", views.AcceptFriendRequestView.as_view(), name="accept-request"),
    path("decline/<uuid:request_id>/", views.DeclineFriendRequestView.as_view(), name="decline-request"),
    path("cancel/<uuid:request_id>/", views.CancelFriendRequestView.as_view(), name="cancel-request"),
    path("<uuid:user_id>/", views.UnfriendView.as_view(), name="unfriend"),
    path("", views.FriendsListView.as_view(), name="friends-list"),
    path("requests/pending/", views.PendingReceivedRequestsView.as_view(), name="pending-received"),
    path("requests/sent/", views.PendingSentRequestsView.as_view(), name="pending-sent"),
]
