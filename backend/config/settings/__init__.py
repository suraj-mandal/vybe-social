import os

# default to development settings if DJANGO_SETTINGS_MODULE Is not set.

environment = os.environ.get("DJANGO_ENVIRONMENT", "dev")

match environment:
    case "prod":
        from .prod import *  # noqa: F401, F403
    case "dev":
        from .dev import *  # noqa: F401, F403
    case _:
        from .dev import *  # noqa: F401, F403
