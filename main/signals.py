from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Student

User = get_user_model()


@receiver(post_delete, sender=Student)
def delete_user_with_student(sender, instance, **kwargs):
    """Удаляет связанного User при удалении Student."""
    if instance.user_id:
        User.objects.filter(pk=instance.user_id).delete()

