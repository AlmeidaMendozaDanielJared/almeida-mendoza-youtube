from google_auth_oauthlib.flow import Flow  # Flujo OAuth
from googleapiclient.discovery import build  # Constructor servicio
from googleapiclient.http import MediaFileUpload  # Para subir archivos
from django.conf import settings  # Settings

class YouTubeUploadService:
    """Servicio para subir videos a YouTube con OAuth"""
    
    def obtener_url_autorizacion(self):
        """Genera URL para que usuario autorice la app"""
        
        flow = Flow.from_client_config(  # Crea flujo OAuth
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=settings.YOUTUBE_SCOPES  # Permisos requeridos
        )
        
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI  # URL de callback
        
        authorization_url, state = flow.authorization_url(  # Genera URL
            access_type='offline',  # Obtener refresh_token
            include_granted_scopes='true'  # Incluir scopes ya autorizados
        )
        
        return authorization_url, state  # Retorna URL y state (para validación)
    
    def subir_video(self, credentials, archivo_path, titulo, descripcion, categoria='22', privacidad='private'):
        """
        Sube un video a YouTube
        
        Args:
            credentials: Credenciales OAuth del usuario
            archivo_path: Ruta al archivo de video
            titulo: Título del video
            descripcion: Descripción del video
            categoria: ID de categoría (22=People & Blogs, 27=Education)
            privacidad: public, private, unlisted
        
        Returns:
            dict: Información del video subido
        """
        
        # Crear servicio YouTube con credenciales del usuario
        youtube = build(  # Construye servicio autenticado
            'youtube', 
            'v3', 
            credentials=credentials  # Usa credentials del usuario
        )
        
        # Metadata del video
        body = {
            'snippet': {
                'title': titulo,  # Título
                'description': descripcion,  # Descripción
                'categoryId': categoria  # Categoría
            },
            'status': {
                'privacyStatus': privacidad  # Nivel de privacidad
            }
        }
        
        # Preparar archivo para upload
        media = MediaFileUpload(  # Crea objeto de media
            archivo_path,  # Ruta del archivo
            chunksize=-1,  # Subir todo de una vez
            resumable=True  # Permite reanudar si falla
        )
        
        # Ejecutar upload
        request = youtube.videos().insert(  # Crea request de insert
            part='snippet,status',  # Partes a enviar
            body=body,  # Metadata
            media_body=media  # Archivo de video
        )
        
        response = request.execute()  # Ejecuta upload (puede tomar tiempo)
        
        return response  # Retorna respuesta con ID del video subido