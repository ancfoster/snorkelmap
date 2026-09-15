import uuid
from django.db import models
from django.conf import settings

class ModerationItem(models.Model):
    class ItemType(models.TextChoices):
        LOCATION = 'location', 'Location Listing'
        REVIEW = 'review', 'Review'
        VISIBILITY_REPORT = 'visibility', 'Visibility Report'
        MEDIA = 'media', 'Location Media'

    class Status(models.IntegerChoices):
        PENDING = 0, 'Pending'
        FURTHER_INVESTIGATION = 1, 'Further Investigation'
        ESCALATED = 2, 'Escalated'
        CLOSED = 3, 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Target Object Fields
    item_type = models.CharField(max_length=20, choices=ItemType.choices, db_index=True)
    object_uuid = models.UUIDField(db_index=True, help_text="UUID of the target object (e.g., SnorkelLocation)")
    
    # Reporte by fields
    reported_by_account_user = models.BooleanField(default=False)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_moderation_reports'
    )
    
    #  State
    status = models.IntegerField(choices=Status.choices, default=Status.PENDING, db_index=True)
    mod_comments = models.JSONField(default=dict, blank=True, help_text="Store internal admin notes, timestamps, and history")
    action_taken = models.TextField(null=True, blank=True)

    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['item_type', 'object_uuid']),
        ]

    def __str__(self):
        return f"{self.get_item_type_display()} | {self.get_status_display()} ({self.object_uuid})"
