from ninja import NinjaAPI

from snorkelusers.api_v1 import router as snorkelusers_router
from snorkel_locations.api_v1 import router as snorkel_locations_router
from snorkel_locations.media_webhook import router as media_webhook_router

# CSRF is not configured here. In django-ninja 1.x it belongs to the
# auth class: django_auth is a SessionAuth, which extends APIKeyCookie,
# which defaults to csrf=True and refuses a request with a bad token.
# So every endpoint using django_auth is already protected, and the
# webhook, which authenticates by signature and carries no cookie, is
# correctly outside that.
api = NinjaAPI(version='1.0.0')


@api.get('/hello')
def hello(request):
    return "Hello World!!!"


api.add_router("/users", snorkelusers_router)
api.add_router("/locations", snorkel_locations_router)
# Called by the Cloudflare Worker, not by a browser. It carries no
# session and is authenticated by a signature over its own body.
api.add_router("/media", media_webhook_router)
