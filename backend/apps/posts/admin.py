from django.contrib import admin

from apps.posts.models import Post, PostMedia


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
