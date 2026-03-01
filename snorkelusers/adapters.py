# accounts/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re

class CustomAccountAdapter(DefaultAccountAdapter):
    
    def clean_username(self, username, shallow=False):
        """
        Validates the username. You can hook into this if you want to
        (dynamically) restrict what usernames can be chosen.
        """
        # Call parent validation (checks for existing usernames, etc.)
        username = super().clean_username(username, shallow)
        
        # Check if username contains @
        email_pattern = r'^[^@]+@[^@]+\.[^@]+$'
        if re.match(email_pattern, username):
            raise ValidationError(
                _('Username cannot be an email address. Please choose a different username.')
            )
        
        # Check length (5-20 characters)
        if len(username) < 5:
            raise ValidationError(
                _('Username must be at least 5 characters long.')
            )
        
        if len(username) > 20:
            raise ValidationError(
                _('Username must be no more than 20 characters long.')
            )
        
        # Check for valid characters only (a-z, A-Z, 0-9, -)
        if not re.match(r'^[a-zA-Z0-9-]+$', username):
            raise ValidationError(
                _('Username can only contain letters (a-z, A-Z), numbers (0-9), and hyphens (-).')
            )
        
        return username