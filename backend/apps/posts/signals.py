from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.posts.models import Comment, CommentMention, Reaction

# on saving the reaction


@receiver(post_save, sender=Reaction)
def on_reaction_save(sender, instance: Reaction, created: bool, **kwargs):
    """TODO: fire NotificationCreated (kind='reaction')."""
    pass


@receiver(post_save, sender=Comment)
def on_comment_save(sender, instance: Comment, created: bool, **kwargs):
    """TODO: fire NotificationCreated (kind='comment'|'reply')"""
    pass


@receiver(post_save, sender=CommentMention)
def on_mention_save(sender, instance: CommentMention, created: bool, **kwargs):
    """TODO: fire MentionNotification (unless self-mention)."""
    pass
