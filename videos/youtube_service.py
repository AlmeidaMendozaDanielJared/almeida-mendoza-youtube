from googleapiclient.discovery import build  # Constructor de servicio Google
from django.conf import settings  # Configuración
from datetime import datetime  # Manejo de fechas
import isodate  # Para parsear duración ISO 8601

class YouTubeService:
    """Servicio para interactuar con YouTube Data API v3"""
    
    def __init__(self):
        # Crear cliente de YouTube API con API Key
        self.youtube = build(  # Construye servicio de YouTube
            settings.YOUTUBE_API_SERVICE_NAME,  # 'youtube'
            settings.YOUTUBE_API_VERSION,  # 'v3'
            developerKey=settings.YOUTUBE_API_KEY  # API Key
        )
    
    def buscar_videos(self, query, max_resultados=10, orden='relevance'):
        """
        Busca videos en YouTube
        
        Args:
            query: Texto a buscar
            max_resultados: Cantidad máxima de resultados (1-50)
            orden: relevance, date, rating, title, viewCount
        
        Returns:
            list: Lista de diccionarios con información de videos
        """
        
        # Llamar endpoint search.list
        search_response = self.youtube.search().list(  # Ejecuta búsqueda
            q=query,  # Término de búsqueda
            part='id,snippet',  # Partes a retornar
            type='video',  # Solo videos (no canales ni playlists)
            maxResults=max_resultados,  # Límite de resultados
            order=orden,  # Criterio de ordenamiento
            regionCode='HN'  # Región Honduras (opcional)
        ).execute()  # Ejecuta la petición
        
        # Extraer IDs de videos encontrados
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]  # Lista de IDs
        
        # Obtener detalles completos de los videos
        if video_ids:
            videos_detalle = self.obtener_detalles_videos(video_ids)  # Llama método interno
            return videos_detalle
        
        return []  # Sin resultados
    
    def obtener_detalles_videos(self, video_ids):
        """
        Obtiene información detallada de videos
        
        Args:
            video_ids: Lista de IDs de videos o string único
        
        Returns:
            list: Información completa de videos
        """
        
        # Convertir a lista si es string
        if isinstance(video_ids, str):
            video_ids = [video_ids]  # Convierte a lista
        
        # Llamar endpoint videos.list
        videos_response = self.youtube.videos().list(  # Obtiene detalles
            id=','.join(video_ids),  # IDs separados por coma
            part='snippet,contentDetails,statistics'  # Incluye snippet, duración y stats
        ).execute()
        
        videos = []  # Lista para almacenar resultados
        
        for item in videos_response.get('items', []):  # Itera resultados
            snippet = item['snippet']  # Información básica
            statistics = item.get('statistics', {})  # Estadísticas (puede no existir)
            content = item['contentDetails']  # Detalles de contenido
            
            # Parsear duración ISO 8601 (PT15M30S → 15:30)
            duracion_iso = content.get('duration', 'PT0S')  # Obtiene duración
            duracion_segundos = isodate.parse_duration(duracion_iso).total_seconds()  # Convierte a segundos
            
            video_data = {  # Construye diccionario con datos
                'youtube_id': item['id'],  # ID del video
                'titulo': snippet['title'],  # Título
                'descripcion': snippet['description'],  # Descripción
                'canal_id': snippet['channelId'],  # ID del canal
                'canal_nombre': snippet['channelTitle'],  # Nombre del canal
                'fecha_publicacion': datetime.fromisoformat(  # Convierte a datetime
                    snippet['publishedAt'].replace('Z', '+00:00')
                ),
                'url_thumbnail': snippet['thumbnails']['high']['url'],  # Miniatura alta resolución
                'url_video': f"https://www.youtube.com/watch?v={item['id']}",  # URL completa
                'duracion': duracion_iso,  # Duración en formato ISO
                'duracion_segundos': int(duracion_segundos),  # Duración en segundos
                'vistas': int(statistics.get('viewCount', 0)),  # Visualizaciones
                'likes': int(statistics.get('likeCount', 0)),  # Me gusta
                'comentarios': int(statistics.get('commentCount', 0)),  # Comentarios
                'etiquetas': ','.join(snippet.get('tags', [])),  # Tags separados por coma
            }
            
            videos.append(video_data)  # Agrega a la lista
        
        return videos  # Retorna lista de videos
    
    def obtener_videos_canal(self, canal_id, max_resultados=20):
        """Obtiene videos de un canal específico"""
        
        search_response = self.youtube.search().list(
            channelId=canal_id,  # Filtrar por canal
            part='id',
            type='video',
            order='date',  # Más recientes primero
            maxResults=max_resultados
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if video_ids:
            return self.obtener_detalles_videos(video_ids)
        
        return []