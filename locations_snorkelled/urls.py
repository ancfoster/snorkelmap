from django.urls import path

from . import views

# Its own prefix rather than a path under /location/, for the reason
# set out in saved_locations/urls.py.
urlpatterns = [
    path("snorkelled/<uuid:location_uuid>/", views.toggle,
         name="toggle_snorkelled"),
]
