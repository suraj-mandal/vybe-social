from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


# Register your models here.
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "is_verified",
        "date_joined"
    )

    list_filter = (
        "is_staff",
        "is_active",
        "is_verified",
        "date_joined",
    )

    search_fields = ("email", "username", "first_name", "last_name", "phone_number")

    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "phone_number")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_verified",
                    "groups",
                    "user_permissions"
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")})
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields" : (
                    "email",
                    "username",
                    "phone_number",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                )
            }
        )
    )
