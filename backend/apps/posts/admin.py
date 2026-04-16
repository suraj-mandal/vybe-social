from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from apps.posts.models import Comment, CommentMention, Post, PostMedia, Reaction


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    fields = (
        "media",
        "position",
        "created_at",
    )
    readonly_fields = ("created_at",)
    autocomplete_fields = ("media",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "status",
        "visibility",
        "adult_rating",
        "published_at",
        "created_at",
        "deleted_at",
    )

    list_filter = (
        "status",
        "visibility",
        "adult_rating",
        "deleted_at",
    )
    search_fields = (
        "author__username",
        "content",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "is_edited",
    )
    inlines = [PostMediaInline]

    def get_queryset(self, request):
        return Post.all_objects.all()


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "media",
        "position",
        "created_at",
    )
    list_filter = ("media__media_type",)
    search_fields = (
        "post__id",
        "media__s3_key",
    )
    readonly_fields = ("created_at",)
    autocomplete_fields = (
        "post",
        "media",
    )


class ReactionInline(GenericTabularInline):
    model = Reaction
    extra = 0
    readonly_fields = (
        "user",
        "type",
        "created_at",
    )
    can_delete = True


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "content_type",
        "object_id",
        "type",
        "created_at",
    )
    list_filter = (
        "type",
        "content_type",
        "created_at",
    )
    search_fields = (
        "user__username",
        "object_id",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    raw_id_fields = ("user",)


class CommentMentionInline(GenericTabularInline):
    model = CommentMention
    extra = 0
    readonly_fields = (
        "user",
        "created_at",
    )
    raw_id_fields = ("user",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "post",
        "preview",
        "is_edited",
        "is_deleted",
        "created_at",
    )
    list_filter = (
        "is_deleted",
        "is_edited",
        "created_at",
    )
    search_fields = (
        "user__username",
        "content",
        "post__id",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    raw_id_fields = (
        "user",
        "post",
        "parent",
    )
    inlines = (
        CommentMentionInline,
        ReactionInline,
    )

    def preview(self, comment: Comment) -> str:
        return (comment.content or "")[:60] or "[deleted]"

    preview.short_description = "Content"

    def get_queryset(self, request):
        return Comment.all_objects.get_queryset().select_related("user", "post")


@admin.register(CommentMention)
class CommentMentionAdmin(admin.ModelAdmin):
    list_display = (
        "comment",
        "user",
        "created_at",
    )
    search_fields = (
        "comment__id",
        "user__username",
    )
    readonly_fields = (
        "id",
        "created_at",
    )
    raw_id_fields = (
        "comment",
        "user",
    )
