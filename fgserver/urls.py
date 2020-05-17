from django.urls import path

from django.contrib import admin
from django.urls.conf import include
from django.contrib.auth import views as auth_views
from . import views
admin.autodiscover()

urlpatterns = [
    path('',views.home, name='home' ),
    path('login/',views.fgatc_login),
    path('logout/',views.fgatc_logout),
    path('admin/', admin.site.urls),
    path('map/', include('fgserver.map.urls')),
    path('tracker/', include('fgserver.tracker.urls')),
    path('admin_tools/', include('admin_tools.urls')),
    path('ajax_select/', include('ajax_select.urls')),
    path("activate_airport/<str:icao>",views.activate_airport,{'active':True}),
    path("deactivate_airport/<str:icao>",views.activate_airport,{'active':False}),
    path("single/<str:icao>",views.activate_airport,{'active':True,'single':True}),
    path("clear",views.clear)
    ]

