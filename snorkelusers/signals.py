from django.dispatch import receiver
from allauth.account.signals import email_confirmed
from snorkelusers.utils import get_country_code_from_ip

@receiver(email_confirmed)
def set_user_country(sender, request, email_address, **kwargs):
    """
    Signal receiver that sets the user's country code upon email confirmation.

    Triggered by allauth's `email_confirmed` signal. Extracts the country code
    from the confirmation request's IP address and saves it to the user's profile.
    If the country code cannot be determined, no changes are made.
    """
    user = email_address.user
    country_code = get_country_code_from_ip(request)
    if country_code:
        user.country_code = country_code
        user.save()