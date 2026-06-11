import psycopg2
from werkzeug.security import generate_password_hash

conn = psycopg2.connect(
    host="localhost",
    database="polla_mundialista",
    user="postgres",
    password="1111"
)
cur = conn.cursor()

# Actualizar la contraseña del ADMIN usando el método correcto
admin_password_hash = generate_password_hash('admin123')
cur.execute("""
    UPDATE usuarios_polla 
    SET password_hash = %s 
    WHERE username = 'ADMIN'
""", (admin_password_hash,))

# Resetear todos los puntos
cur.execute("""
    UPDATE puntos_totales 
    SET puntos_fase_grupos = 0, 
        puntos_eliminatorias = 0, 
        puntos_totales = 0, 
        resultados_exactos = 0
""")

# Recalcular puntos para partidos finalizados
cur.execute("""
    UPDATE pronosticos_partidos pp
    SET puntos = 
        CASE 
            WHEN p.goles_local = pp.goles_local AND p.goles_visitante = pp.goles_visitante THEN 
                CASE WHEN p.fase = 'grupos' THEN 5 ELSE 8 END
            WHEN (pp.goles_local > pp.goles_visitante AND p.goles_local > p.goles_visitante) OR
                 (pp.goles_local < pp.goles_visitante AND p.goles_local < p.goles_visitante) OR
                 (pp.goles_local = pp.goles_visitante AND p.goles_local = p.goles_visitante) THEN 3
            WHEN ABS(pp.goles_local - pp.goles_visitante) = ABS(p.goles_local - p.goles_visitante) THEN 1
            ELSE 0
        END
    FROM partidos p
    WHERE pp.partido_id = p.id AND p.estado = 'finalizado'
""")

# Actualizar puntos totales
cur.execute("""
    UPDATE puntos_totales pt
    SET 
        puntos_fase_grupos = COALESCE((
            SELECT SUM(pp.puntos) 
            FROM pronosticos_partidos pp 
            JOIN partidos p ON pp.partido_id = p.id 
            WHERE pp.usuario_id = pt.usuario_id AND p.fase = 'grupos'
        ), 0),
        puntos_eliminatorias = COALESCE((
            SELECT SUM(pp.puntos) 
            FROM pronosticos_partidos pp 
            JOIN partidos p ON pp.partido_id = p.id 
            WHERE pp.usuario_id = pt.usuario_id AND p.fase != 'grupos'
        ), 0),
        resultados_exactos = COALESCE((
            SELECT COUNT(*) 
            FROM pronosticos_partidos pp 
            JOIN partidos p ON pp.partido_id = p.id 
            WHERE pp.usuario_id = pt.usuario_id 
            AND p.estado = 'finalizado'
            AND pp.goles_local = p.goles_local 
            AND pp.goles_visitante = p.goles_visitante
        ), 0)
""")

cur.execute("""
    UPDATE puntos_totales 
    SET puntos_totales = puntos_fase_grupos + puntos_eliminatorias + puntos_especiales
""")

conn.commit()
cur.close()
conn.close()
print("✅ Puntos recalculados correctamente")