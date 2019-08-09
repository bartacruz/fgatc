from django.urls import path

from django.contrib import admin
from django.urls.conf import include
from django.contrib.auth import views as auth_views
from . import views
admin.autodiscover()

urlpatterns = [
    path('',views.home, name='home' ),
    path('login',auth_views.LoginView.as_view()),
    path('logout',auth_views.LogoutView.as_view()),
    path('admin/', admin.site.urls),
    path('map/', include('fgserver.map.urls')),
    path('tracker/', include('fgserver.tracker.urls')),
    path('admin_tools/', include('admin_tools.urls')),
    path('ajax_select/', include('ajax_select.urls')),
    ]

