import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            host="localhost",
            database="polla_mundialista",
            user="tu_usuario",
            password="tu_contraseña"
        )
    
    def get_usuario_by_username(self, username):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
            return cur.fetchone()
    
    def get_usuario_by_id(self, user_id):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, username, email, nombre_completo, foto_perfil, area_trabajo, es_admin FROM usuarios WHERE id = %s", (user_id,))
            return cur.fetchone()
    
    def create_usuario(self, username, email, password_hash, nombre_completo, area_trabajo):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO usuarios (username, email, password_hash, nombre_completo, area_trabajo)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (username, email, password_hash, nombre_completo, area_trabajo))
            user_id = cur.fetchone()[0]
            self.conn.commit()
            return user_id
    
    def update_ultimo_acceso(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET ultimo_acceso = %s WHERE id = %s", (datetime.now(), user_id))
            self.conn.commit()
    
    def get_puntos_usuario(self, usuario_id):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM puntos_totales WHERE usuario_id = %s", (usuario_id,))
            return cur.fetchone()
    
    def get_estadisticas_usuario(self, usuario_id):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN puntos = 8 OR puntos = 5 THEN 1 END) as resultados_exactos,
                    COUNT(CASE WHEN puntos = 3 THEN 1 END) as ganadores_correctos,
                    AVG(puntos) as promedio_puntos
                FROM pronosticos_partidos 
                WHERE usuario_id = %s AND puntos > 0
            """, (usuario_id,))
            return cur.fetchone()
    
    def get_tabla_posiciones(self):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.username, u.nombre_completo, u.area_trabajo, 
                       pt.puntos_totales, pt.resultados_exactos,
                       RANK() OVER (ORDER BY pt.puntos_totales DESC) as ranking
                FROM puntos_totales pt
                JOIN usuarios u ON u.id = pt.usuario_id
                ORDER BY pt.puntos_totales DESC
            """)
            return cur.fetchall()
    
    def get_top_5(self):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.username, u.nombre_completo, u.foto_perfil, pt.puntos_totales
                FROM puntos_totales pt
                JOIN usuarios u ON u.id = pt.usuario_id
                ORDER BY pt.puntos_totales DESC
                LIMIT 5
            """)
            return cur.fetchall()
    
    def get_partidos(self, fase=None):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if fase:
                cur.execute("""
                    SELECT p.*, 
                           s1.nombre as local_nombre, s1.bandera_url as local_bandera,
                           s2.nombre as visitante_nombre, s2.bandera_url as visitante_bandera
                    FROM partidos p
                    JOIN selecciones s1 ON p.seleccion_local_id = s1.id
                    JOIN selecciones s2 ON p.seleccion_visitante_id = s2.id
                    WHERE p.fase = %s
                    ORDER BY p.fecha_hora
                """, (fase,))
            else:
                cur.execute("""
                    SELECT p.*, 
                           s1.nombre as local_nombre, s1.bandera_url as local_bandera,
                           s2.nombre as visitante_nombre, s2.bandera_url as visitante_bandera
                    FROM partidos p
                    JOIN selecciones s1 ON p.seleccion_local_id = s1.id
                    JOIN selecciones s2 ON p.seleccion_visitante_id = s2.id
                    ORDER BY p.fecha_hora
                """)
            return cur.fetchall()
    
    def get_partido_by_id(self, partido_id):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM partidos WHERE id = %s", (partido_id,))
            return cur.fetchone()
    
    def save_pronostico_partido(self, usuario_id, partido_id, goles_local, goles_visitante):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pronosticos_partidos (usuario_id, partido_id, goles_local, goles_visitante)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (usuario_id, partido_id) 
                DO UPDATE SET goles_local = %s, goles_visitante = %s, fecha_pronostico = %s
                RETURNING id
            """, (usuario_id, partido_id, goles_local, goles_visitante, 
                  goles_local, goles_visitante, datetime.now()))
            pronostico_id = cur.fetchone()[0]
            self.conn.commit()
            return pronostico_id
    
    def update_puntos_pronostico(self, pronostico_id, puntos):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE pronosticos_partidos SET puntos = %s WHERE id = %s", (puntos, pronostico_id))
            self.conn.commit()
    
    def save_pronostico_especial(self, usuario_id, data):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pronosticos_especiales 
                (usuario_id, campeon_id, subcampeon_id, tercer_lugar_id, maximo_goleador, 
                 seleccion_sorpresa_id, marcador_final_local, marcador_final_visitante)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (usuario_id) DO UPDATE SET
                campeon_id = %s, subcampeon_id = %s, tercer_lugar_id = %s, 
                maximo_goleador = %s, seleccion_sorpresa_id = %s, 
                marcador_final_local = %s, marcador_final_visitante = %s,
                fecha_actualizacion = %s
            """, (usuario_id, data.get('campeon_id'), data.get('subcampeon_id'), 
                  data.get('tercer_lugar_id'), data.get('maximo_goleador'),
                  data.get('seleccion_sorpresa_id'), data.get('marcador_final_local'),
                  data.get('marcador_final_visitante'),
                  data.get('campeon_id'), data.get('subcampeon_id'), 
                  data.get('tercer_lugar_id'), data.get('maximo_goleador'),
                  data.get('seleccion_sorpresa_id'), data.get('marcador_final_local'),
                  data.get('marcador_final_visitante'), datetime.now()))
            self.conn.commit()
    
    def update_resultado_partido(self, partido_id, goles_local, goles_visitante):
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE partidos 
                SET goles_local = %s, goles_visitante = %s, estado = 'finalizado'
                WHERE id = %s
            """, (goles_local, goles_visitante, partido_id))
            self.conn.commit()
    
    def get_pronosticos_by_partido(self, partido_id):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM pronosticos_partidos WHERE partido_id = %s", (partido_id,))
            return cur.fetchall()
    
    def get_puntos_by_fase(self, usuario_id, fase):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(pp.puntos), 0)
                FROM pronosticos_partidos pp
                JOIN partidos p ON pp.partido_id = p.id
                WHERE pp.usuario_id = %s AND p.fase = %s AND pp.puntos IS NOT NULL
            """, (usuario_id, fase))
            return cur.fetchone()[0]
    
    def get_puntos_especiales(self, usuario_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT COALESCE(puntos_especiales, 0) FROM puntos_totales WHERE usuario_id = %s", (usuario_id,))
            result = cur.fetchone()
            return result[0] if result else 0
    
    def update_puntos_totales(self, usuario_id, fase_grupos, eliminatorias, especiales, total):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO puntos_totales (usuario_id, puntos_fase_grupos, puntos_eliminatorias, 
                                           puntos_especiales, puntos_totales)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (usuario_id) DO UPDATE SET
                puntos_fase_grupos = %s, puntos_eliminatorias = %s,
                puntos_especiales = %s, puntos_totales = %s
            """, (usuario_id, fase_grupos, eliminatorias, especiales, total,
                  fase_grupos, eliminatorias, especiales, total))
            self.conn.commit()
    
    def get_historial_partidos(self):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, 
                       s1.nombre as local_nombre, s1.bandera_url as local_bandera,
                       s2.nombre as visitante_nombre, s2.bandera_url as visitante_bandera
                FROM partidos p
                JOIN selecciones s1 ON p.seleccion_local_id = s1.id
                JOIN selecciones s2 ON p.seleccion_visitante_id = s2.id
                WHERE p.estado = 'finalizado'
                ORDER BY p.fecha_hora DESC
            """)
            return cur.fetchall()