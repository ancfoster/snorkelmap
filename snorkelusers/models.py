from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class User(AbstractUser):
    """
    Custom user model for snorkelmap.
    """
    user_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    avatar_url = models.URLField(max_length=200, blank=True, null=True)
    notification_level = models.IntegerField(default="1")
    bio = models.TextField(max_length=220, blank=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    accepted_terms_conditions = models.BooleanField(blank=True, default=True)
    SNORKEL_ADMIN = 1
    MOD_LEVEL_1 = 2
    MOD_LEVEL_2 = 3
    STANDARD = 4
    STANDARD_RESTRICTED = 5
    READONLY = 6
    SUSPENDED = 7
    DELETED = 8
    
    USER_TYPES = (
        (SNORKEL_ADMIN, 'Snorkel Admin'),
        (MOD_LEVEL_1, 'Moderator Level 1'),
        (MOD_LEVEL_2, 'Moderator Level 2'),
        (STANDARD, 'Standard User'),
        (STANDARD_RESTRICTED, 'Standard User with restrictions'),
        (READONLY, 'Read-only User'),
        (SUSPENDED, 'Suspended User'),
        (DELETED, 'Deleted User'),
    )
    
    warning_level = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    account_admin_notes = models.JSONField(default=dict, blank=True)
    user_type = models.CharField(
        max_length=20,  # Adjust max_length as needed
        choices=USER_TYPES,
        default='standard',
    )
    # User contributions counter
    snorkel_sites_created = models.IntegerField(default=0)
    snorkel_site_edits = models.IntegerField(default=0)
    snorkel_site_comments = models.IntegerField(default=0)
    media_contributions = models.IntegerField(default=0)
    community_points = models.IntegerField(default=0)