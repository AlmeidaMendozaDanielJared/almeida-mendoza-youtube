import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.files.storage import FileSystemStorage
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from django.db.models import Sum  # <--- IMPORTANTE: Agrega esto arriba
from django.core.paginator import Paginator

from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_oauth2_token

# Asumiendo que estos archivos existen en tu carpeta de app
from .models import Video
from .youtube_service import YouTubeService
from .upload_service import YouTubeUploadService

# Definimos las categorías aquí para pasarlas al Template HTML
YOUTUBE_CATEGORIES = [
    ('22', 'People & Blogs'),
    ('27', 'Education'),
    ('28', 'Programación'),
    ('10', 'Music'),
    ('17', 'Sports'),
    ('20', 'Gaming'),
]

def inicio(request):
    # 1. Obtenemos todos los videos
    videos = Video.objects.all().order_by('-fecha_publicacion')
    
    # 2. Hacemos los cálculos matemáticos
    total_videos = videos.count()
    
    # aggregate devuelve un diccionario, por eso usamos ['campo__sum']
    # El 'or 0' es un truco: si no hay videos, la suma da 'None', así que lo forzamos a ser 0
    total_views = videos.aggregate(Sum('vistas'))['vistas__sum'] or 0
    total_likes = videos.aggregate(Sum('likes'))['likes__sum'] or 0
    
    # 3. Empaquetamos todo en el contexto
    context = {
        'videos': videos,
        'total_videos': total_videos,
        'total_views': total_views,
        'total_likes': total_likes,
    }
    
    # 4. Enviamos el contexto al template
    return render(request, 'videos/inicio.html', context)

def mis_videos(request):
    # 1. Filtramos videos SOLO del usuario actual
    # Usamos 'all()' base para luego ir filtrando
    videos_list = Video.objects.filter(agregado_por=request.user).order_by('-fecha_publicacion')

    # 2. Lógica del Buscador (Si escribieron algo en el input "buscar")
    query = request.GET.get('buscar')
    if query:
        videos_list = videos_list.filter(titulo__icontains=query)

    # 3. Lógica del Filtro de Categoría (Si seleccionaron algo en el select)
    categoria_filtro = request.GET.get('categoria')
    if categoria_filtro:
        videos_list = videos_list.filter(categoria=categoria_filtro)

    # 4. CÁLCULOS MATEMÁTICOS (Lo que te faltaba)
    # Calculamos sobre 'videos_list' para que los números cambien si filtras
    total_views = videos_list.aggregate(Sum('vistas'))['vistas__sum'] or 0
    total_likes = videos_list.aggregate(Sum('likes'))['likes__sum'] or 0
    total_comments = videos_list.aggregate(Sum('comentarios'))['comentarios__sum'] or 0
    
    # Este es el total de videos encontrados
    cantidad_videos = videos_list.count()

    # 5. Paginación (Mostrar 10 videos por página)
    paginator = Paginator(videos_list, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'videos': page_obj,          # Los videos de la página actual
        'total_views': total_views,  # Suma de vistas
        'total_likes': total_likes,  # Suma de likes
        'total_comments': total_comments, # Suma de comentarios
        'total_videos_count': cantidad_videos # Cantidad total para mostrar en la tarjeta
    }
    
    return render(request, 'videos/mis_videos.html', context)

def detalle_video(request, video_id):
    """Muestra el reproductor y detalles de un video específico"""
    video = get_object_or_404(Video, pk=video_id)
    return render(request, 'videos/detalle_video.html', {'video': video})

def logout_view(request):
    """Cierra sesión"""
    logout(request)
    messages.info(request, "Sesión cerrada.")
    return redirect('videos:inicio')

# --- OAUTH & UPLOAD LOGIC ---
def autorizar_youtube(request):
    """Paso 1: Iniciar el flujo OAuth"""
    # Intenta instanciar el servicio
    try:
        upload_service = YouTubeUploadService()
    except Exception as e:
        messages.error(request, f"Error config: {e}")
        return redirect('videos:login')

    try:
        authorization_url, state = upload_service.obtener_url_autorizacion()
        
        request.session['oauth_state'] = state
        return redirect(authorization_url)
        
    except Exception as e:
        messages.error(request, f"Error al conectar con Google: {e}")
        return redirect('videos:login')

def oauth_callback(request):
    """
    Recibe el código de Google, obtiene el token,
    crea/recupera el usuario de Django y lo loguea.
    """
    state = request.session.get('oauth_state')
    
    if not state:
        messages.error(request, "Error de seguridad (State missing).")
        return redirect('videos:inicio')

    try:
        # 1. Configurar el flujo para intercambiar código por token
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=settings.YOUTUBE_SCOPES,
            state=state
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        
        # 2. Obtener Token
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        credentials = flow.credentials

        # 3. Obtener información del perfil del usuario (Email, Nombre)
        # Usamos el id_token que Google nos devuelve junto con el access_token
        # (Esto requiere que hayamos pedido el scope 'openid email')
        session = flow.authorized_session()
        profile_info = session.get('https://www.googleapis.com/oauth2/v2/userinfo').json()
        
        email = profile_info.get('email')
        nombre = profile_info.get('given_name', 'Usuario')
        
        # 4. Lógica de Login en Django
        if email:
            # Buscar si existe el usuario, si no, crearlo
            user, created = User.objects.get_or_create(username=email)
            if created:
                user.email = email
                user.first_name = nombre
                user.save()
            
            # Forzar el inicio de sesión (Backend manual)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # 5. Guardar las credenciales de YouTube en la sesión
            request.session['credentials'] = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }

            messages.success(request, f"¡Bienvenido, {nombre}!")
            return redirect('videos:mis_videos')
        else:
            messages.error(request, "No pudimos obtener tu email de Google.")
            return redirect('videos:inicio')

    except Exception as e:
        messages.error(request, f"Error en autenticación: {e}")
        return redirect('videos:inicio')

def login_view(request):
    """Muestra la página con el botón de Google"""
    if request.user.is_authenticated:
        return redirect('videos:mis_videos')
    return render(request, 'videos/login.html')

@login_required
def subir_video(request):
    """Paso 3: Formulario y proceso de subida"""
    
    # 1. Verificar si el usuario ya autorizó YouTube
    if 'credentials' not in request.session:
        messages.info(request, "Primero necesitamos permiso para subir videos a tu canal.")
        return redirect('videos:autorizar_youtube')

    # 2. Procesar Formulario (POST)
    # Nota: Tu HTML usa name="video", así que buscamos request.FILES.get('video')
    if request.method == 'POST':
        archivo = request.FILES.get('video')
        
        if archivo:
            try:
                # Obtener datos del HTML
                titulo = request.POST.get('titulo')
                descripcion = request.POST.get('descripcion')
                categoria_id = request.POST.get('categoria')
                privacidad = request.POST.get('privacidad') # public, unlisted, private

                # Guardar archivo temporalmente (Google API necesita un path físico)
                fs = FileSystemStorage()
                # Usamos un nombre seguro para evitar colisiones
                filename = fs.save(f"temp_{request.user.id}_{archivo.name}", archivo)
                uploaded_file_path = fs.path(filename)

                # Reconstruir credenciales
                creds_data = request.session['credentials']
                credentials = Credentials(**creds_data)

                # Subir a YouTube
                uploader = YouTubeUploadService()
                response = uploader.subir_video(
                    credentials=credentials,
                    archivo_path=uploaded_file_path,
                    titulo=titulo,
                    descripcion=descripcion,
                    categoria=categoria_id, # Pasamos la categoría seleccionada
                    privacidad=privacidad
                )

                # Guardar referencia en Base de Datos Local
                if 'id' in response:
                    # Parsear snippet
                    snippet = response.get('snippet', {})
                    thumbnails = snippet.get('thumbnails', {})
                    high_thumb = thumbnails.get('high', {}).get('url') or thumbnails.get('default', {}).get('url')

                    Video.objects.create(
                        youtube_id=response['id'],
                        titulo=snippet.get('title', titulo),
                        descripcion=snippet.get('description', descripcion),
                        url_video=f"https://www.youtube.com/watch?v={response['id']}",
                        url_thumbnail=high_thumb,
                        canal_nombre=snippet.get('channelTitle', ''),
                        fecha_publicacion=snippet.get('publishedAt'),
                        categoria=categoria_id,
                        agregado_por=request.user
                    )
                    
                    messages.success(request, f"¡Video '{titulo}' subido correctamente!")
                    
                    # Limpiar archivo temporal
                    if os.path.exists(uploaded_file_path):
                        os.remove(uploaded_file_path)
                        
                    return redirect('videos:mis_videos')
                else:
                    messages.error(request, "YouTube no devolvió un ID de video. Revisa tu cuenta.")
            
            except Exception as e:
                messages.error(request, f"Error al subir video: {e}")
                # Limpiar archivo temporal si falló
                if 'uploaded_file_path' in locals() and os.path.exists(uploaded_file_path):
                    os.remove(uploaded_file_path)
        else:
            messages.error(request, "Por favor selecciona un archivo de video.")

    # 3. Renderizar Formulario (GET)
    # Pasamos 'categorias' porque el template subir_video.html tiene un bucle for
    return render(request, 'videos/subir_video.html', {
        'categorias': YOUTUBE_CATEGORIES
    })