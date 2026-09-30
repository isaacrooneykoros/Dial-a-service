"""Celery application for the worker.

On Windows run: celery -A config worker --pool=solo -l info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("dial_a_service")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
