from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class User(AbstractUser):
    """
    Custom user model for snorkelmap.
    """

    class UserType(models.IntegerChoices):
        """What an account is allowed to do, most senior first.

        An IntegerChoices rather than a tuple of constants, so the
        values and the labels are one thing rather than two that have
        to be kept in step, and so the field can be a real integer
        column: it used to be a CharField whose choices were integers,
        which meant everything came back as "1" and "2" and any
        comparison written the obvious way was quietly false.

        The order is the authority order, which is what lets a
        permission be written as "this type or more senior".
        """

        SNORKEL_ADMIN = 1, "Snorkel Admin"
        MOD_LEVEL_1 = 2, "Moderator Level 1"
        MOD_LEVEL_2 = 3, "Moderator Level 2"
        STANDARD = 4, "Standard User"
        STANDARD_RESTRICTED = 5, "Standard User with restrictions"
        READONLY = 6, "Read-only User"
        SUSPENDED = 7, "Suspended User"
        DELETED = 8, "Deleted User"

    user_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    avatar_url = models.URLField(max_length=200, blank=True, null=True)
    notification_level = models.IntegerField(default=1)
    bio = models.TextField(max_length=220, blank=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    accepted_terms_conditions = models.BooleanField(blank=True, default=True)

    warning_level = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    account_admin_notes = models.JSONField(default=dict, blank=True)
    user_type = models.PositiveSmallIntegerField(
        choices=UserType.choices,
        default=UserType.STANDARD,
    )

    # User contributions counter
    snorkel_sites_created = models.IntegerField(default=0)
    snorkel_site_edits = models.IntegerField(default=0)
    snorkel_site_comments = models.IntegerField(default=0)
    media_contributions = models.IntegerField(default=0)
    community_points = models.IntegerField(default=0)

    def is_at_least(self, user_type):
        """Whether this account is that type or a more senior one.

        The types are numbered with the admin at one, so more senior
        means a smaller number. Written here so that nothing else has
        to remember which way round that is.
        """
        return self.user_type <= user_type
