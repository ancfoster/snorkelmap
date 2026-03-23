from ninja import Router
from ninja.throttling import UserRateThrottle

from django.contrib.auth import get_user_model

from .schemas import UsernameCheckResponse

User = get_user_model()

router = Router()

@router.get('/check_username_availability/{username}', response={200: UsernameCheckResponse}, throttle=[UserRateThrottle('250/h')])
def check_username(request, username: str):

    if not username:
        return UsernameCheckResponse(
            username="",
            available=False
        )

    username = username.strip()
    username_exists = User.objects.filter(username=username).exists()
    return UsernameCheckResponse(
        username=username,
        available=not username_exists
    )