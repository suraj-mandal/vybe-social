from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender: type[User], instance: User, created: bool, **kwargs: dict[str, Any]) -> None:
    """
    Signal receiver function that creates a user profile whenever a new user is created.
    This function listens for the `post_save` signal emitted by the user model. When a new user
    is successfully saved, it automatically creates a corresponding profile for the user.

    :param sender: The model class that sent the signal.
    :param instance: The instance of the user that was saved.
    :param created: A boolean indicating whether a new user was created (True) or an existing
        user was updated (False).
    :param kwargs: Additional keyword arguments passed by the signal.

    :return: None
    """
    if created:
        Profile.objects.create(user=instance)
