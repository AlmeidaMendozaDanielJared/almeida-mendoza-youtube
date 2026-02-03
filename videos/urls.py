from django.urls import path
from django.contrib.auth import views as auth_views # <--- Importante
from . import views

# ¡Esto es crucial para que funcionen tus namespaces en los templates!
app_name = 'videos'

urlpatterns = [
    # Ruta: / (Inicio)
    path('', views.inicio, name='inicio'),
    
    # Ruta: /mis-videos/ (Listado)
    path('mis-videos/', views.mis_videos, name='mis_videos'),
    
    # Ruta: /subir/ (Formulario de carga)
    path('subir/', views.subir_video, name='subir_video'),
    
    # Ruta: /logout/ (Cerrar sesión)
    path('logout/', views.logout_view, name='logout'),    

    path('login/', views.login_view, name='login'),

    path('oauth/authorize/', views.autorizar_youtube, name='autorizar_youtube'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'), # Asegúrate que coincida con Google Console
    # (Opcional) Ruta para el callback de OAuth si usas autenticación de Google
    # path('oauth2callback/', views.oauth2callback, name='oauth2callback'),

    path('youtube/callback/', views.oauth_callback, name='oauth_callback'),

    path('video/<int:video_id>/', views.detalle_video, name='detalle_video'),
]