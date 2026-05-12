from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.posts"
    verbose_name = "Posts"

    def ready(self) -> None:
        from apps.posts import signals  # noqa: F401
