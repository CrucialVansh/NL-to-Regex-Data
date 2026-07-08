import os

from .base import *  # noqa: F403

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-%7h^(efja9du92t@n3xe!=db*joc2=n%@uk*7bsd0t5df8!ypi",
)

CORS_ALLOW_ALL_ORIGINS = True
