from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    """
    Handles the configuration for the Profiles application within the Django project.

    This class is responsible for specifying application-specific metadata and configuration
    options for the Profiles module. It specifies default fields, the application namespace,
    and initializes necessary signals when the application is ready.

    :ivar default_auto_field: Specifies the default auto field type to use for primary keys in
        the application models.
    :type default_auto_field: str
    :ivar name: The full Python path to the application, used by Django for identification and
        loading purposes.
    :type name: str
    :ivar verbose_name: Human-readable name for the application displayed in the Django admin interface.
    :type verbose_name: str
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.profiles"
    verbose_name = "Profiles"

    def ready(self):
        import apps.profiles.signals  # noqa: F401
