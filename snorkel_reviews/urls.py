from django.urls import path

from . import views

# Its own prefix rather than a path under /location/, for the same
# reason saved_locations and locations_snorkelled have one: the listing
# patterns end in <slug:slug>, which matches anything, so anything
# hung underneath them is reached by the listing view instead. See
# url_check.py, which exists because that failure is invisible in the
# source and {% url %} keeps producing the right address either way.
urlpatterns = [
    path("review/<uuid:location_uuid>/", views.submit, name="submit_review"),
    path("review/<uuid:location_uuid>/delete/", views.delete,
         name="delete_review"),
]
