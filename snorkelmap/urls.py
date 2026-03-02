from django.contrib import admin
from django.urls import path, include
from allauth.account.views import LoginView, SignupView

from .views import home

urlpatterns = [
    path("", home, name="home"),
    path('smadmin/', admin.site.urls)
    #path('account/', include('allauth.urls'))
]
