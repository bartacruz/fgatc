from django.urls import path

from django.contrib import admin
from django.urls.conf import include
admin.autodiscover()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('map/', include('fgserver.map.urls')),
    path('tracker/', include('fgserver.tracker.urls')),
    ]

