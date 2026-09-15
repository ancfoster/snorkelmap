from django.contrib import admin
from django.urls import path, include
from allauth.account.views import LoginView, SignupView
from .views import home, privacy_policy, terms_conditions
from .api_v1 import api as api_v1

urlpatterns = [
    path('smadmin/', admin.site.urls),
    path('login/', LoginView.as_view(), name="sm_login"),
    path('create-snorkelmap-account/', SignupView.as_view(), name="custom_signup"),
    path('account/', include('allauth.urls')),
    path("", home, name="home"),
    path("privacy-policy/", privacy_policy, name="privacy_policy"),
    path("terms-and-conditions/", terms_conditions, name="terms_conditions"),
    path("", include('snorkelusers.urls')),
    path("", include('snorkel_locations.urls')),
    path("", include('saved_locations.urls')),
    path("", include('locations_snorkelled.urls')),
    path("", include('snorkel_reviews.urls')),
    path("", include('snorkel_visibility.urls')),
    path('api/v1/', api_v1.urls)
]
