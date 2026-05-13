"""WSGI config for eurovibe project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eurovibe.settings")

application = get_wsgi_application()
