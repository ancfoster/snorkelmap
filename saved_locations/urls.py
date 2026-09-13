from django.urls import path

from . import views

# Deliberately not under /location/. The listing addresses there are
# <country>/<slug> and a uuid is a perfectly good slug, so
# /location/<uuid>/save/ matched the detail pattern, looked for a
# listing called "save" and returned a 404. Its own prefix cannot
# collide with anything.
urlpatterns = [
    path("save/<uuid:location_uuid>/", views.toggle, name="toggle_saved"),
]
