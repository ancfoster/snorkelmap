from ninja import NinjaAPI
from snorkelusers.api_v1 import router as snorkelusers_router

api = NinjaAPI(version='1.0.0')

@api.get('/hello')
def hello(request):
    return "Hello World!!!"

api.add_router("/users", snorkelusers_router)