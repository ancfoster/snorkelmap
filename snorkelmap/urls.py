from django.contrib import admin
from django.urls import path, include
from allauth.account.views import LoginView, SignupView
from .views import home
from .api_v1 import api as api_v1

urlpatterns = [
    path('smadmin/', admin.site.urls),
    path('login/', LoginView.as_view(), name="sm_login"),
    path('create-snorkelmap-account/', SignupView.as_view(), name="custom_signup"),
    path('account/', include('allauth.urls')),
    path("", home, name="home"),
    path("", include('snorkelusers.urls')),
    path('api/v1/', api_v1.urls)
]
