from django.contrib import admin
from django.urls import path, include
from allauth.account.views import LoginView, SignupView

from .views import home

urlpatterns = [
    path('smadmin/', admin.site.urls),
    path('login/', LoginView.as_view(), name="sm_login"),
    path('create-snorkelmap-account/', SignupView.as_view(), name="custom_signup"),
    path('account/', include('allauth.urls')),
    path("", home, name="home"),
    path("", include('snorkelusers.urls'))
]
