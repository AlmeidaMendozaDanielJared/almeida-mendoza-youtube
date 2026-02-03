from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # Panel de administración
    path('', include('videos.urls')),  # URLs de la app videos
]