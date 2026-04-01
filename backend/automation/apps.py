import sys
from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'automation'
    verbose_name = 'Automation Rules'

    def ready(self):
        # Only start the engine when actually running the server, not during
        # management commands (migrate, makemigrations, shell, check, etc.)
        management_commands = {'migrate', 'makemigrations', 'shell', 'check',
                               'test', 'collectstatic', 'createsuperuser'}
        argv = sys.argv
        if len(argv) > 1 and argv[1] in management_commands:
            return
        # Avoid double-start in Django's autoreloader (parent process)
        import os
        if os.environ.get('RUN_MAIN') == 'true':
            return
        from .engine import start_engine
        start_engine()
