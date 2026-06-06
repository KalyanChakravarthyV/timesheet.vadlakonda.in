from django.apps import AppConfig
from django.db.models.signals import post_save


class TimesheetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "timesheets"

    def ready(self):
        from django.contrib.auth.models import User
        from .models import UserProfile

        def create_user_profile(sender, instance, created, **kwargs):
            if created:
                UserProfile.objects.get_or_create(user=instance)

        post_save.connect(create_user_profile, sender=User)
