from django.db.models import Manager, QuerySet


class PostManager(Manager):
    def get_queryset(self) -> QuerySet:
        # since soft-delete in place, only get the posts that have deleted at as null
        return super().get_queryset().filter(deleted_at__isnull=True)


class CommentManager(Manager):
    def get_queryset(self) -> QuerySet:
        # soft deleting the comment in place.
        return super().get_queryset().filter(is_deleted=False)
