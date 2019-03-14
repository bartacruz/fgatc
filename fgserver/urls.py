from django.urls import path

from django.contrib import admin
from django.urls.conf import include
from . import views
admin.autodiscover()

urlpatterns = [
    path('',views.home, name='home' ),
    path('admin/', admin.site.urls),
    path('map/', include('fgserver.map.urls')),
    path('tracker/', include('fgserver.tracker.urls')),
    ]

