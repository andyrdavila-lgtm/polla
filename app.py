from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func, desc, or_, and_, text
import os
from werkzeug.utils import secure_filename
from functools import wraps
import json
import io
import zipfile
from collections import defaultdict

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'clave_secreta_polla_mundialista_2026'

# ==================================================
# CONFIGURACIÓN DE BASE DE DATOS POSTGRESQL
# ==================================================
DB_PASSWORD = '1111'

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://postgres:{DB_PASSWORD}@localhost:5432/polla_mundialista'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración para carga de archivos
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================================================
# MODELOS
# ==================================================

class Usuario(db.Model):
    __tablename__ = 'usuarios_polla'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre_completo = db.Column(db.String(100))
    foto_perfil = db.Column(db.String(255), default='/static/avatars/default_avatar.png')
    area_trabajo = db.Column(db.String(100))
    fecha_registro = db.Column(db.DateTime, default=datetime.now)
    ultimo_acceso = db.Column(db.DateTime)
    es_admin = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)

class Seleccion(db.Model):
    __tablename__ = 'selecciones'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    grupo = db.Column(db.String(1))
    bandera_url = db.Column(db.String(255))
    bandera_local = db.Column(db.String(255), default=None)
    color_primario = db.Column(db.String(7))
    color_secundario = db.Column(db.String(7))

class Partido(db.Model):
    __tablename__ = 'partidos'
    id = db.Column(db.Integer, primary_key=True)
    fase = db.Column(db.String(20), nullable=False)
    seleccion_local_id = db.Column(db.Integer, db.ForeignKey('selecciones.id'))
    seleccion_visitante_id = db.Column(db.Integer, db.ForeignKey('selecciones.id'))
    fecha_hora = db.Column(db.DateTime, nullable=False)
    goles_local = db.Column(db.Integer)
    goles_visitante = db.Column(db.Integer)
    penales_local = db.Column(db.Integer, default=None)
    penales_visitante = db.Column(db.Integer, default=None)
    estado = db.Column(db.String(20), default='pendiente')
    grupo = db.Column(db.String(1))
    bloqueado_manual = db.Column(db.Boolean, default=False)
    
    local = db.relationship('Seleccion', foreign_keys=[seleccion_local_id])
    visitante = db.relationship('Seleccion', foreign_keys=[seleccion_visitante_id])

    @property
    def ganador_real(self):
        if self.goles_local is None or self.goles_visitante is None:
            return None
        if self.goles_local > self.goles_visitante:
            return 'local'
        if self.goles_local < self.goles_visitante:
            return 'visitante'
        if self.penales_local is not None and self.penales_visitante is not None:
            if self.penales_local > self.penales_visitante:
                return 'local'
            if self.penales_local < self.penales_visitante:
                return 'visitante'
        return 'empate'

class PronosticoPartido(db.Model):
    __tablename__ = 'pronosticos_partidos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios_polla.id'))
    partido_id = db.Column(db.Integer, db.ForeignKey('partidos.id'))
    tipo_pronostico = db.Column(db.String(20), default='ganador')
    ganador = db.Column(db.String(20))
    goles_local = db.Column(db.Integer)
    goles_visitante = db.Column(db.Integer)
    penales_local = db.Column(db.Integer)
    penales_visitante = db.Column(db.Integer)
    puntos = db.Column(db.Integer, default=0)
    fecha_pronostico = db.Column(db.DateTime, default=datetime.now)
    ip_address = db.Column(db.String(45), default=None)
    intento_numero = db.Column(db.Integer, default=1)

class PronosticoEspecial(db.Model):
    __tablename__ = 'pronosticos_especiales'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios_polla.id'))
    campeon_id = db.Column(db.Integer, db.ForeignKey('selecciones.id'))
    subcampeon_id = db.Column(db.Integer, db.ForeignKey('selecciones.id'))
    tercer_lugar_id = db.Column(db.Integer, db.ForeignKey('selecciones.id'))
    maximo_goleador = db.Column(db.String(100))
    seleccion_sorpresa_id = db.Column(db.Integer, db.ForeignKey('selecciones.id'))
    marcador_final_local = db.Column(db.Integer)
    marcador_final_visitante = db.Column(db.Integer)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.now)
    ip_address = db.Column(db.String(45), default=None)

class PuntoTotal(db.Model):
    __tablename__ = 'puntos_totales'
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios_polla.id'), primary_key=True)
    puntos_fase_grupos = db.Column(db.Integer, default=0)
    puntos_eliminatorias = db.Column(db.Integer, default=0)
    puntos_especiales = db.Column(db.Integer, default=0)
    puntos_totales = db.Column(db.Integer, default=0)
    resultados_exactos = db.Column(db.Integer, default=0)

class LogAuditoria(db.Model):
    __tablename__ = 'log_auditoria'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios_polla.id'))
    accion = db.Column(db.String(50), nullable=False)
    entidad = db.Column(db.String(50), nullable=False)
    entidad_id = db.Column(db.Integer)
    detalles = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    fecha = db.Column(db.DateTime, default=datetime.now)
    
    usuario = db.relationship('Usuario')

class HistorialResultado(db.Model):
    __tablename__ = 'historial_resultados'
    id = db.Column(db.Integer, primary_key=True)
    partido_id = db.Column(db.Integer, db.ForeignKey('partidos.id'))
    goles_local_anterior = db.Column(db.Integer)
    goles_visitante_anterior = db.Column(db.Integer)
    goles_local_nuevo = db.Column(db.Integer)
    goles_visitante_nuevo = db.Column(db.Integer)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios_polla.id'))
    fecha_modificacion = db.Column(db.DateTime, default=datetime.now)
    
    partido = db.relationship('Partido')
    usuario = db.relationship('Usuario')

class ConfiguracionGlobal(db.Model):
    __tablename__ = 'configuracion_global'
    clave = db.Column(db.String(100), primary_key=True)
    valor = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.now)

# ==================================================
# FUNCIONES DE UTILIDAD
# ==================================================

def log_auditoria(accion, entidad, entidad_id=None, detalles=None):
    if 'user_id' not in session:
        return
    try:
        log = LogAuditoria(
            usuario_id=session['user_id'],
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalles=detalles,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error en auditoría: {e}")
        db.session.rollback()

def is_match_editable(match, usuario_id=None):
    if match.estado == 'finalizado':
        return False
    if match.bloqueado_manual:
        return False
    if not match.fecha_hora:
        return True
    
    if usuario_id:
        intentos = PronosticoPartido.query.filter_by(
            usuario_id=usuario_id, 
            partido_id=match.id
        ).count()
        if intentos >= 2:
            return False
    
    ahora = datetime.now()
    tiempo_inicio = match.fecha_hora
    diff_minutes = (tiempo_inicio - ahora).total_seconds() / 60
    return diff_minutes > 30

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('es_admin'):
            return jsonify({'error': 'Acceso no autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_bandera_default(nombre):
    if not nombre:
        return 'https://flagcdn.com/w80/default.png'
    paises = {
        'Argentina': 'ar', 'Brasil': 'br', 'Francia': 'fr', 'Alemania': 'de',
        'España': 'es', 'Inglaterra': 'gb', 'Países Bajos': 'nl', 'Portugal': 'pt',
        'México': 'mx', 'Uruguay': 'uy', 'Croacia': 'hr', 'Bélgica': 'be',
        'Ecuador': 'ec', 'Canadá': 'ca', 'EE.UU.': 'us', 'Colombia': 'co',
        'Paraguay': 'py', 'Japón': 'jp', 'Corea del Sur': 'kr', 'Australia': 'au',
        'Senegal': 'sn', 'Marruecos': 'ma', 'Túnez': 'tn', 'Egipto': 'eg',
        'Ghana': 'gh', 'Costa de Marfil': 'ci', 'Sudáfrica': 'za', 'Argelia': 'dz',
        'Suiza': 'ch', 'Catar': 'qa', 'Escocia': 'gb-sct', 'Haití': 'ht',
        'Turquía': 'tr', 'Curazao': 'cw', 'Suecia': 'se', 'Cabo Verde': 'cv',
        'Arabia Saudí': 'sa', 'Irán': 'ir', 'Nueva Zelanda': 'nz', 'Irak': 'iq',
        'Noruega': 'no', 'Austria': 'at', 'Jordania': 'jo', 'RD Congo': 'cd',
        'Uzbekistán': 'uz', 'Panamá': 'pa', 'Bosnia': 'ba', 'República Checa': 'cz'
    }
    codigo = paises.get(nombre, 'default')
    return f'https://flagcdn.com/w80/{codigo}.png'

# ==================================================
# CÁLCULO DE PUNTOS
# ==================================================

def _mismo_ganador(gl, gv, rl, rv):
    if gl > gv and rl > rv:
        return True
    if gl < gv and rl < rv:
        return True
    if gl == gv and rl == rv:
        return True
    return False

def calcular_puntos_pronostico(pronostico, partido):
    if partido.goles_local is None or partido.goles_visitante is None:
        return 0, False

    es_fase_grupos = (partido.fase == 'grupos')
    ganador_real = partido.ganador_real
    puntos = 0
    es_exacto = False

    if pronostico.tipo_pronostico == 'ganador':
        if pronostico.ganador == ganador_real:
            puntos = 3
        return puntos, False

    if pronostico.tipo_pronostico == 'marcador':
        gl = pronostico.goles_local
        gv = pronostico.goles_visitante
        rl = partido.goles_local
        rv = partido.goles_visitante

        if gl == rl and gv == rv:
            puntos = 5 if es_fase_grupos else 8
            es_exacto = True
        elif _mismo_ganador(gl, gv, rl, rv):
            puntos = 3
        elif abs(gl - gv) == abs(rl - rv):
            puntos = 1
        return puntos, es_exacto

    if pronostico.tipo_pronostico == 'penales':
        gl = pronostico.goles_local
        gv = pronostico.goles_visitante
        pl = pronostico.penales_local
        pv = pronostico.penales_visitante
        rl = partido.goles_local
        rv = partido.goles_visitante
        rpl = partido.penales_local
        rpv = partido.penales_visitante

        marcador_90_exacto = (gl == rl and gv == rv)
        penales_exactos = (rpl is not None and rpv is not None and
                           pl is not None and pv is not None and
                           pl == rpl and pv == rpv)

        if marcador_90_exacto and penales_exactos:
            puntos = 10
            es_exacto = True
        elif marcador_90_exacto:
            puntos = 5 if es_fase_grupos else 8
        elif _mismo_ganador(gl, gv, rl, rv) and pronostico.ganador == ganador_real:
            puntos = 3
        elif abs(gl - gv) == abs(rl - rv):
            puntos = 1
        return puntos, es_exacto

    return 0, False

def recalcular_puntos_partido(partido_id):
    partido = db.session.get(Partido, partido_id)
    if not partido or partido.estado != 'finalizado' or partido.goles_local is None:
        return

    subquery = db.session.query(
        PronosticoPartido.usuario_id,
        func.max(PronosticoPartido.fecha_pronostico).label('max_fecha')
    ).filter(
        PronosticoPartido.partido_id == partido_id
    ).group_by(PronosticoPartido.usuario_id).subquery()

    pronosticos = db.session.query(PronosticoPartido).join(
        subquery,
        (PronosticoPartido.usuario_id == subquery.c.usuario_id) &
        (PronosticoPartido.fecha_pronostico == subquery.c.max_fecha)
    ).filter(
        PronosticoPartido.partido_id == partido_id
    ).all()

    for pronostico in pronosticos:
        puntos, es_exacto = calcular_puntos_pronostico(pronostico, partido)
        pronostico.puntos = puntos
        db.session.commit()
        actualizar_puntos_totales_usuario(pronostico.usuario_id)

def actualizar_puntos_totales_usuario(usuario_id):
    subquery = db.session.query(
        PronosticoPartido.partido_id,
        func.max(PronosticoPartido.fecha_pronostico).label('max_fecha')
    ).filter(
        PronosticoPartido.usuario_id == usuario_id
    ).group_by(PronosticoPartido.partido_id).subquery()

    ultimos_pronosticos = db.session.query(PronosticoPartido).join(
        subquery,
        (PronosticoPartido.partido_id == subquery.c.partido_id) &
        (PronosticoPartido.fecha_pronostico == subquery.c.max_fecha)
    ).filter(
        PronosticoPartido.usuario_id == usuario_id
    ).all()

    puntos_grupos = 0
    puntos_eliminatorias = 0
    resultados_exactos = 0

    for p in ultimos_pronosticos:
        partido = db.session.get(Partido, p.partido_id)
        if partido and partido.estado == 'finalizado':
            if partido.fase == 'grupos':
                puntos_grupos += p.puntos
            else:
                puntos_eliminatorias += p.puntos

            if p.tipo_pronostico in ('marcador', 'penales'):
                _, es_exacto = calcular_puntos_pronostico(p, partido)
                if es_exacto:
                    resultados_exactos += 1

    puntos_total = db.session.get(PuntoTotal, usuario_id)
    if puntos_total:
        puntos_total.puntos_fase_grupos = puntos_grupos
        puntos_total.puntos_eliminatorias = puntos_eliminatorias
        puntos_total.resultados_exactos = resultados_exactos
        
        # Bonus por predicción de campeón (10 puntos si acertó)
        puntos_especiales = puntos_total.puntos_especiales or 0
        final_partido = Partido.query.filter_by(fase='FINAL').first()
        if final_partido and final_partido.estado == 'finalizado' and final_partido.goles_local is not None:
            ganador_final = final_partido.ganador_real
            ganador_id = None
            if ganador_final == 'local':
                ganador_id = final_partido.seleccion_local_id
            elif ganador_final == 'visitante':
                ganador_id = final_partido.seleccion_visitante_id
            if ganador_id:
                prono_especial = PronosticoEspecial.query.filter_by(usuario_id=usuario_id).first()
                if prono_especial and prono_especial.campeon_id == ganador_id:
                    puntos_especiales = 10
                else:
                    puntos_especiales = 0
            else:
                puntos_especiales = 0
        else:
            puntos_especiales = 0  # Aún no se decide
        
        puntos_total.puntos_especiales = puntos_especiales
        puntos_total.puntos_totales = (puntos_grupos + puntos_eliminatorias + puntos_especiales)
        db.session.commit()

# ==================================================
# ACTUALIZACIÓN COMPLETA DE LA LLAVE ELIMINATORIA
# ==================================================

def obtener_ganador(partido):
    """Devuelve el objeto Seleccion ganador del partido, o None si no está finalizado."""
    if partido.estado != 'finalizado' or partido.goles_local is None:
        return None
    ganador = partido.ganador_real
    if ganador == 'local':
        return partido.local
    elif ganador == 'visitante':
        return partido.visitante
    return None

def actualizar_ronda(origen_fase, destino_fase, num_partidos_destino):
    """
    Toma todos los partidos de origen_fase ordenados por fecha_hora,
    los agrupa en parejas secuenciales, y para cada partido de destino_fase
    (ordenados también por fecha_hora) asigna como local el ganador del
    primer partido de la pareja y como visitante el ganador del segundo.
    """
    partidos_origen = Partido.query.filter_by(fase=origen_fase).order_by(Partido.fecha_hora).all()
    partidos_destino = Partido.query.filter_by(fase=destino_fase).order_by(Partido.fecha_hora).all()

    if len(partidos_destino) != num_partidos_destino:
        print(f"⚠️ Advertencia: se esperaban {num_partidos_destino} partidos para {destino_fase}, pero hay {len(partidos_destino)}")
        return

    # Agrupar origen en parejas
    parejas = [(partidos_origen[i], partidos_origen[i+1]) for i in range(0, len(partidos_origen), 2)]
    if len(parejas) != num_partidos_destino:
        print(f"⚠️ No se pueden formar {num_partidos_destino} parejas con {len(partidos_origen)} partidos de origen")
        return

    for idx, (partido_dest, (p1, p2)) in enumerate(zip(partidos_destino, parejas)):
        ganador1 = obtener_ganador(p1)
        ganador2 = obtener_ganador(p2)
        if ganador1 and ganador2:
            if partido_dest.seleccion_local_id != ganador1.id:
                partido_dest.seleccion_local_id = ganador1.id
            if partido_dest.seleccion_visitante_id != ganador2.id:
                partido_dest.seleccion_visitante_id = ganador2.id
            db.session.commit()
            print(f"✅ {destino_fase} partido {partido_dest.id}: {ganador1.nombre} vs {ganador2.nombre}")
        else:
            # Si algún ganador falta, se deja como estaba (posiblemente None)
            pass

def generar_partidos_eliminatoria():
    """
    Actualiza los partidos de octavos (R32) de forma incremental, usando la información
    disponible de los grupos (aunque no estén todos finalizados).
    """
    partidos_grupos = Partido.query.filter(Partido.fase == 'grupos').all()
    if not partidos_grupos:
        return

    # Organizar datos por grupo
    grupos = 'ABCDEFGHIJKL'
    datos_grupos = {g: {} for g in grupos}

    for p in partidos_grupos:
        if not p.grupo or p.goles_local is None:
            continue
        g = p.grupo
        local = p.local
        visit = p.visitante
        if local:
            datos_grupos[g][local.nombre] = datos_grupos[g].get(local.nombre, {'nombre': local.nombre, 'id': local.id, 'puntos': 0, 'dg': 0, 'gf': 0})
        if visit:
            datos_grupos[g][visit.nombre] = datos_grupos[g].get(visit.nombre, {'nombre': visit.nombre, 'id': visit.id, 'puntos': 0, 'dg': 0, 'gf': 0})

        gl, gv = p.goles_local, p.goles_visitante
        if gl > gv:
            datos_grupos[g][local.nombre]['puntos'] += 3
        elif gl < gv:
            datos_grupos[g][visit.nombre]['puntos'] += 3
        else:
            datos_grupos[g][local.nombre]['puntos'] += 1
            datos_grupos[g][visit.nombre]['puntos'] += 1

        datos_grupos[g][local.nombre]['gf'] += gl
        datos_grupos[g][local.nombre]['dg'] += (gl - gv)
        datos_grupos[g][visit.nombre]['gf'] += gv
        datos_grupos[g][visit.nombre]['dg'] += (gv - gl)

    # Calcular posiciones
    primeros, segundos, terceros = {}, {}, {}
    for g in grupos:
        equipos = list(datos_grupos[g].values())
        equipos.sort(key=lambda x: (-x['puntos'], -x['dg'], -x['gf']))
        if len(equipos) >= 1 and equipos[0]['puntos'] > 0:
            primeros[g] = equipos[0]
        if len(equipos) >= 2 and equipos[1]['puntos'] > 0:
            segundos[g] = equipos[1]
        if len(equipos) >= 3 and equipos[2]['puntos'] > 0:
            terceros[g] = equipos[2]

    # Mejores 8 terceros
    terceros_con_datos = [(g, terceros[g]) for g in grupos if g in terceros]
    terceros_con_datos.sort(key=lambda x: (-x[1]['puntos'], -x[1]['dg'], -x[1]['gf']))
    mejores_terceros = {g: data for g, data in terceros_con_datos[:8]}

    def mejor_tercero(grupos_posibles):
        candidatos = []
        for g in grupos_posibles:
            if g in terceros and g in mejores_terceros:
                candidatos.append((g, terceros[g]))
        if not candidatos:
            return None
        candidatos.sort(key=lambda x: (-x[1]['puntos'], -x[1]['dg'], -x[1]['gf']))
        return candidatos[0][1]

    # Obtener los partidos R32 ordenados por fecha
    partidos_R32 = Partido.query.filter_by(fase='R32').order_by(Partido.fecha_hora).all()
    if len(partidos_R32) != 16:
        print(f"⚠️ Se esperaban 16 partidos R32, pero hay {len(partidos_R32)}. No se actualiza.")
        return

    # Orden de los cruces según el fixture oficial
    asignaciones_ordenadas = [
        (segundos.get('A'), segundos.get('B')),
        (primeros.get('E'), mejor_tercero(['A','B','C','D','F'])),
        (primeros.get('F'), segundos.get('C')),
        (primeros.get('C'), segundos.get('F')),
        (primeros.get('I'), mejor_tercero(['C','D','F','G','H'])),
        (segundos.get('E'), segundos.get('I')),
        (primeros.get('A'), mejor_tercero(['C','E','F','H','I'])),
        (primeros.get('L'), mejor_tercero(['E','H','I','J','K'])),
        (primeros.get('D'), mejor_tercero(['B','E','F','I','J'])),
        (primeros.get('G'), mejor_tercero(['A','E','H','I','J'])),
        (segundos.get('K'), segundos.get('L')),
        (primeros.get('H'), segundos.get('J')),
        (primeros.get('B'), mejor_tercero(['E','F','G','I','J'])),
        (primeros.get('J'), segundos.get('H')),
        (primeros.get('K'), mejor_tercero(['D','E','I','J','L'])),
        (segundos.get('D'), segundos.get('G')),
    ]

    for idx, (local_data, visit_data) in enumerate(asignaciones_ordenadas):
        partido = partidos_R32[idx]
        actualizado = False
        if local_data and partido.seleccion_local_id != local_data['id']:
            partido.seleccion_local_id = local_data['id']
            actualizado = True
        if visit_data and partido.seleccion_visitante_id != visit_data['id']:
            partido.seleccion_visitante_id = visit_data['id']
            actualizado = True
        if actualizado:
            db.session.commit()
            print(f"✅ Partido R32 {partido.id}: {local_data['nombre'] if local_data else '?'} vs {visit_data['nombre'] if visit_data else '?'}")

    print("🏆 Eliminatoria R32 actualizada de forma incremental.")

def actualizar_toda_eliminatoria():
    """Actualiza toda la llave eliminatoria desde grupos hasta final."""
    # 1. Actualizar R32 desde grupos
    generar_partidos_eliminatoria()
    
    # 2. R32 -> R16
    actualizar_ronda('R32', 'R16', 8)
    
    # 3. R16 -> QF
    actualizar_ronda('R16', 'QF', 4)
    
    # 4. QF -> SF
    actualizar_ronda('QF', 'SF', 2)
    
    # 5. SF -> Final y Tercer puesto
    sf_partidos = Partido.query.filter_by(fase='SF').order_by(Partido.fecha_hora).all()
    final = Partido.query.filter_by(fase='FINAL').first()
    tercero = Partido.query.filter_by(fase='3P').first()
    
    if len(sf_partidos) == 2 and final and tercero:
        ganador1 = obtener_ganador(sf_partidos[0])
        ganador2 = obtener_ganador(sf_partidos[1])
        perdedor1 = sf_partidos[0].visitante if sf_partidos[0].ganador_real == 'local' else sf_partidos[0].local
        perdedor2 = sf_partidos[1].visitante if sf_partidos[1].ganador_real == 'local' else sf_partidos[1].local
        
        if ganador1 and ganador2:
            if final.seleccion_local_id != ganador1.id:
                final.seleccion_local_id = ganador1.id
            if final.seleccion_visitante_id != ganador2.id:
                final.seleccion_visitante_id = ganador2.id
            db.session.commit()
            print(f"✅ FINAL: {ganador1.nombre} vs {ganador2.nombre}")
        
        if perdedor1 and perdedor2:
            if tercero.seleccion_local_id != perdedor1.id:
                tercero.seleccion_local_id = perdedor1.id
            if tercero.seleccion_visitante_id != perdedor2.id:
                tercero.seleccion_visitante_id = perdedor2.id
            db.session.commit()
            print(f"✅ TERCER PUESTO: {perdedor1.nombre} vs {perdedor2.nombre}")
    
    print("🏆 Eliminatoria completa actualizada.")

# ==================================================
# RUTAS PRINCIPALES
# ==================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/polla_mundialista_carrusel')
def polla_mundialista_carrusel():
    return render_template('polla_mundialista_carrusel.html')

@app.route('/manual')
def manual():
    return render_template('manual_usuario_polla_dga_2026.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        usuario = Usuario.query.filter_by(username=username, activo=True).first()
        if usuario and check_password_hash(usuario.password_hash, password):
            session['user_id'] = usuario.id
            session['username'] = usuario.username
            session['nombre'] = usuario.nombre_completo or usuario.username
            session['es_admin'] = usuario.es_admin
            usuario.ultimo_acceso = datetime.now()
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        nombre_completo = request.form.get('nombre_completo')
        area_trabajo = request.form.get('area_trabajo')
        if password != confirm_password:
            error = 'Las contraseñas no coinciden'
        elif Usuario.query.filter_by(username=username).first():
            error = 'El nombre de usuario ya existe'
        elif Usuario.query.filter_by(email=email).first():
            error = 'El email ya está registrado'
        else:
            hashed_password = generate_password_hash(password)
            nuevo_usuario = Usuario(
                username=username, email=email, password_hash=hashed_password,
                nombre_completo=nombre_completo, area_trabajo=area_trabajo
            )
            db.session.add(nuevo_usuario)
            db.session.commit()
            puntos = PuntoTotal(usuario_id=nuevo_usuario.id)
            db.session.add(puntos)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', nombre=session['nombre'])

@app.route('/pronosticos')
def pronosticos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('pronosticos.html', nombre=session['nombre'])

@app.route('/tabla_posiciones')
def tabla_posiciones():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('tabla.html', nombre=session['nombre'])

@app.route('/perfil')
def perfil():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('perfil.html', nombre=session['nombre'])

@app.route('/historial')
def historial():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('historial.html', nombre=session['nombre'])

@app.route('/horarios')
def horarios():
    return render_template('horarios.html')

@app.route('/api/premio')
def api_premio():
    # Excluir al usuario admin (es_admin = False)
    total_usuarios = Usuario.query.filter(Usuario.activo == True, Usuario.es_admin == False).count()
    premio_total = total_usuarios * 10
    primer_lugar = premio_total * 0.5
    segundo_lugar = premio_total * 0.3
    tercer_lugar = premio_total * 0.2
    return jsonify({
        'total_usuarios': total_usuarios,
        'premio_total': premio_total,
        'primer_lugar': primer_lugar,
        'segundo_lugar': segundo_lugar,
        'tercer_lugar': tercer_lugar
    })

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    return render_template('admin_panel.html', nombre=session['nombre'])

@app.route('/admin/partidos')
def admin_partidos():
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    partidos = Partido.query.order_by(Partido.fecha_hora).all()
    selecciones = Seleccion.query.all()
    return render_template('admin_partidos.html', nombre=session['nombre'],
                           partidos=partidos, selecciones=selecciones)

@app.route('/admin/usuarios')
def admin_usuarios():
    if 'user_id' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    usuarios = Usuario.query.all()
    return render_template('admin_usuarios.html', nombre=session['nombre'], usuarios=usuarios)

# ==================================================
# API ENDPOINTS
# ==================================================

@app.route('/api/verificar-sesion')
def api_verificar_sesion():
    if 'user_id' in session:
        usuario = db.session.get(Usuario, session['user_id'])
        if usuario:
            return jsonify({
                'autenticado': True,
                'usuario': {
                    'id': usuario.id,
                    'username': usuario.username,
                    'nombre_completo': usuario.nombre_completo,
                    'email': usuario.email,
                    'area_trabajo': usuario.area_trabajo,
                    'foto_perfil': usuario.foto_perfil,
                    'fecha_registro': usuario.fecha_registro.isoformat() if usuario.fecha_registro else None
                }
            })
    return jsonify({'autenticado': False})

@app.route('/api/partidos')
def api_partidos():
    fase = request.args.get('fase')
    grupo = request.args.get('grupo')
    query = Partido.query
    if fase:
        query = query.filter_by(fase=fase)
    if grupo:
        query = query.filter_by(grupo=grupo)
    partidos = query.order_by(Partido.fecha_hora).all()

    resultado = []
    for p in partidos:
        intentos = 0
        ultimo_pronostico = None
        if 'user_id' in session:
            intentos = PronosticoPartido.query.filter_by(
                usuario_id=session['user_id'], partido_id=p.id
            ).count()
            ultimo_pronostico = PronosticoPartido.query.filter_by(
                usuario_id=session['user_id'], partido_id=p.id
            ).order_by(PronosticoPartido.fecha_pronostico.desc()).first()

        # Manejo seguro de local/visitante None
        if p.local:
            local_nombre = p.local.nombre
            local_bandera = p.local.bandera_local or p.local.bandera_url or get_bandera_default(p.local.nombre)
        else:
            local_nombre = 'Por definir'
            local_bandera = '/static/default_flag.png'

        if p.visitante:
            visitante_nombre = p.visitante.nombre
            visitante_bandera = p.visitante.bandera_local or p.visitante.bandera_url or get_bandera_default(p.visitante.nombre)
        else:
            visitante_nombre = 'Por definir'
            visitante_bandera = '/static/default_flag.png'

        resultado.append({
            'id': p.id,
            'fase': p.fase,
            'local_nombre': local_nombre,
            'local_bandera': local_bandera,
            'visitante_nombre': visitante_nombre,
            'visitante_bandera': visitante_bandera,
            'fecha_hora': p.fecha_hora.strftime('%Y-%m-%d %H:%M:%S'),
            'goles_local': p.goles_local,
            'goles_visitante': p.goles_visitante,
            'penales_local': p.penales_local,
            'penales_visitante': p.penales_visitante,
            'estado': p.estado,
            'grupo': p.grupo,
            'bloqueado_manual': p.bloqueado_manual,
            'intentos': intentos,
            'ultimo_pronostico': {
                'tipo': ultimo_pronostico.tipo_pronostico,
                'ganador': ultimo_pronostico.ganador,
                'goles_local': ultimo_pronostico.goles_local,
                'goles_visitante': ultimo_pronostico.goles_visitante,
                'penales_local': ultimo_pronostico.penales_local,
                'penales_visitante': ultimo_pronostico.penales_visitante,
                'intento': ultimo_pronostico.intento_numero
            } if ultimo_pronostico else None,
            'editable': is_match_editable(p, session.get('user_id'))
        })
    return jsonify(resultado)

@app.route('/api/selecciones')
def api_selecciones():
    selecciones = Seleccion.query.order_by(Seleccion.nombre).all()
    return jsonify([{
        'id': s.id,
        'nombre': s.nombre,
        'grupo': s.grupo,
        'bandera_url': s.bandera_local or s.bandera_url or get_bandera_default(s.nombre)
    } for s in selecciones])

@app.route('/api/mis-pronosticos')
def api_mis_pronosticos():
    if 'user_id' not in session:
        return jsonify({})

    subquery = db.session.query(
        PronosticoPartido.partido_id,
        func.max(PronosticoPartido.fecha_pronostico).label('max_fecha')
    ).filter(
        PronosticoPartido.usuario_id == session['user_id']
    ).group_by(PronosticoPartido.partido_id).subquery()

    pronosticos = db.session.query(PronosticoPartido).join(
        subquery,
        (PronosticoPartido.partido_id == subquery.c.partido_id) &
        (PronosticoPartido.fecha_pronostico == subquery.c.max_fecha)
    ).filter(
        PronosticoPartido.usuario_id == session['user_id']
    ).all()

    resultado = {}
    for p in pronosticos:
        data = {
            'tipo': p.tipo_pronostico,
            'ganador': p.ganador,
            'goles_local': p.goles_local,
            'goles_visitante': p.goles_visitante,
            'penales_local': p.penales_local,
            'penales_visitante': p.penales_visitante,
            'intento': p.intento_numero
        }
        if p.tipo_pronostico == 'ganador':
            data['goles_local'] = None
            data['goles_visitante'] = None
            data['penales_local'] = None
            data['penales_visitante'] = None
        resultado[str(p.partido_id)] = data
    
    return jsonify(resultado)

@app.route('/api/mis-pronosticos-especiales')
def api_mis_pronosticos_especiales():
    if 'user_id' not in session:
        return jsonify({})
    pronostico = PronosticoEspecial.query.filter_by(usuario_id=session['user_id']).first()
    if pronostico:
        return jsonify({
            'campeon_id': pronostico.campeon_id,
            'subcampeon_id': pronostico.subcampeon_id,
            'tercer_lugar_id': pronostico.tercer_lugar_id,
            'maximo_goleador': pronostico.maximo_goleador,
            'seleccion_sorpresa_id': pronostico.seleccion_sorpresa_id,
            'marcador_final_local': pronostico.marcador_final_local,
            'marcador_final_visitante': pronostico.marcador_final_visitante
        })
    return jsonify({})

@app.route('/api/pronostico-partido', methods=['POST'])
def api_guardar_pronostico_partido():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    data = request.json
    partido_id = data.get('partido_id')
    tipo = data.get('tipo', 'ganador')

    partido = db.session.get(Partido, partido_id)
    if not partido:
        return jsonify({'error': 'Partido no encontrado'}), 404

    intentos_actuales = PronosticoPartido.query.filter_by(
        usuario_id=session['user_id'], partido_id=partido_id
    ).count()

    if intentos_actuales >= 2:
        return jsonify({'error': 'Has alcanzado el límite de 2 intentos para este partido'}), 400

    if not is_match_editable(partido, session['user_id']):
        return jsonify({'error': 'El partido ya no está disponible para pronosticar'}), 400

    nuevo_intento = intentos_actuales + 1

    if tipo == 'ganador':
        ganador = data.get('ganador')
        if ganador not in ('local', 'visitante', 'empate'):
            return jsonify({'error': 'Selecciona un ganador válido'}), 400
        pronostico = PronosticoPartido(
            usuario_id=session['user_id'],
            partido_id=partido_id,
            tipo_pronostico='ganador',
            ganador=ganador,
            goles_local=None,
            goles_visitante=None,
            penales_local=None,
            penales_visitante=None,
            ip_address=request.remote_addr,
            intento_numero=nuevo_intento
        )

    elif tipo == 'marcador':
        try:
            gl = int(data['goles_local'])
            gv = int(data['goles_visitante'])
        except (KeyError, ValueError):
            return jsonify({'error': 'Marcador inválido'}), 400
        if gl < 0 or gv < 0 or gl > 20 or gv > 20:
            return jsonify({'error': 'Goles fuera de rango (0-20)'}), 400

        if gl > gv:
            ganador_imp = 'local'
        elif gl < gv:
            ganador_imp = 'visitante'
        else:
            ganador_imp = 'empate'

        pronostico = PronosticoPartido(
            usuario_id=session['user_id'],
            partido_id=partido_id,
            tipo_pronostico='marcador',
            ganador=ganador_imp,
            goles_local=gl,
            goles_visitante=gv,
            penales_local=None,
            penales_visitante=None,
            ip_address=request.remote_addr,
            intento_numero=nuevo_intento
        )

    elif tipo == 'penales':
        try:
            gl = int(data['goles_local'])
            gv = int(data['goles_visitante'])
            pl = int(data['penales_local'])
            pv = int(data['penales_visitante'])
        except (KeyError, ValueError):
            return jsonify({'error': 'Datos de penales inválidos'}), 400
        if gl < 0 or gv < 0 or gl > 20 or gv > 20:
            return jsonify({'error': 'Goles fuera de rango (0-20)'}), 400
        if pl < 0 or pv < 0 or pl > 20 or pv > 20:
            return jsonify({'error': 'Penales fuera de rango (0-20)'}), 400
        if pl == pv:
            return jsonify({'error': 'En penales debe haber un ganador (no puede empatar)'}), 400
        if gl != gv:
            return jsonify({'error': 'Los penales sólo aplican si el marcador en 90\' está empatado'}), 400

        ganador_imp = 'local' if pl > pv else 'visitante'

        pronostico = PronosticoPartido(
            usuario_id=session['user_id'],
            partido_id=partido_id,
            tipo_pronostico='penales',
            ganador=ganador_imp,
            goles_local=gl,
            goles_visitante=gv,
            penales_local=pl,
            penales_visitante=pv,
            ip_address=request.remote_addr,
            intento_numero=nuevo_intento
        )
    else:
        return jsonify({'error': 'Tipo de pronóstico no válido'}), 400

    db.session.add(pronostico)
    db.session.commit()
    log_auditoria('CREATE', 'pronostico', pronostico.id,
                  f"Pronóstico tipo={tipo} creado (intento {nuevo_intento}/2)")

    return jsonify({'success': True, 'intento': nuevo_intento, 'max_intentos': 2})

@app.route('/api/pronostico-especial', methods=['POST'])
def api_guardar_pronostico_especial():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    data = request.json
    pronostico = PronosticoEspecial.query.filter_by(usuario_id=session['user_id']).first()
    if pronostico:
        pronostico.campeon_id = data.get('campeon_id')
        pronostico.subcampeon_id = data.get('subcampeon_id')
        pronostico.tercer_lugar_id = data.get('tercer_lugar_id')
        pronostico.maximo_goleador = data.get('maximo_goleador')
        pronostico.seleccion_sorpresa_id = data.get('seleccion_sorpresa_id')
        pronostico.marcador_final_local = data.get('marcador_final_local')
        pronostico.marcador_final_visitante = data.get('marcador_final_visitante')
        pronostico.fecha_actualizacion = datetime.now()
        pronostico.ip_address = request.remote_addr
        accion = 'UPDATE'
    else:
        pronostico = PronosticoEspecial(
            usuario_id=session['user_id'],
            campeon_id=data.get('campeon_id'),
            subcampeon_id=data.get('subcampeon_id'),
            tercer_lugar_id=data.get('tercer_lugar_id'),
            maximo_goleador=data.get('maximo_goleador'),
            seleccion_sorpresa_id=data.get('seleccion_sorpresa_id'),
            marcador_final_local=data.get('marcador_final_local'),
            marcador_final_visitante=data.get('marcador_final_visitante'),
            ip_address=request.remote_addr
        )
        db.session.add(pronostico)
        accion = 'CREATE'
    db.session.commit()
    log_auditoria(accion, 'pronostico_especial', pronostico.id, "Pronósticos especiales guardados")
    return jsonify({'success': True})

# ========== PREDICCIÓN DE CAMPEÓN (única) ==========
@app.route('/api/mi-prediccion-campeon')
def api_mi_prediccion_campeon():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    pronostico = PronosticoEspecial.query.filter_by(usuario_id=session['user_id']).first()
    if pronostico and pronostico.campeon_id:
        return jsonify({
            'campeon_id': pronostico.campeon_id,
            'fecha_actualizacion': pronostico.fecha_actualizacion.isoformat()
        })
    return jsonify({'campeon_id': None})

@app.route('/api/prediccion-campeon', methods=['POST'])
def api_guardar_prediccion_campeon():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.json
    campeon_id = data.get('campeon_id')
    if not campeon_id:
        return jsonify({'error': 'Debe seleccionar un equipo'}), 400
    
    # Verificar plazo: hasta 10 de junio de 2026, 23:30
    deadline = datetime(2026, 6, 10, 23, 30, 0)
    if datetime.now() > deadline:
        return jsonify({'error': 'El plazo para predecir al campeón ya expiró (10/06/2026 23:30)'}), 400
    
    # Verificar que la selección exista
    seleccion = db.session.get(Seleccion, campeon_id)
    if not seleccion:
        return jsonify({'error': 'Selección no válida'}), 400
    
    # Verificar si el usuario ya tiene una predicción de campeón (única e irreversible)
    pronostico_existente = PronosticoEspecial.query.filter_by(usuario_id=session['user_id']).first()
    if pronostico_existente and pronostico_existente.campeon_id is not None:
        return jsonify({'error': 'Ya realizaste tu predicción de campeón y no puedes cambiarla.'}), 400
    
    # Solo crear nuevo registro (nunca actualizar si ya tiene campeón)
    if pronostico_existente:
        # Caso borde: existe registro pero sin campeon_id (por ejemplo, si se creó vacío antes)
        pronostico_existente.campeon_id = campeon_id
        pronostico_existente.fecha_actualizacion = datetime.now()
        pronostico_existente.ip_address = request.remote_addr
        accion = 'UPDATE'
    else:
        pronostico = PronosticoEspecial(
            usuario_id=session['user_id'],
            campeon_id=campeon_id,
            ip_address=request.remote_addr
        )
        db.session.add(pronostico)
        accion = 'CREATE'
    
    db.session.commit()
    log_auditoria(accion, 'prediccion_campeon', 
                  pronostico_existente.id if pronostico_existente else pronostico.id, 
                  f"Campeón: {seleccion.nombre}")
    
    # Actualizar puntos especiales (si la final ya se jugó, se recalcula)
    actualizar_puntos_totales_usuario(session['user_id'])
    
    return jsonify({'success': True, 'message': 'Predicción guardada exitosamente (única e irreversible)'})

@app.route('/api/certificado-campeon')
def api_certificado_campeon():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    usuario = db.session.get(Usuario, session['user_id'])
    pronostico = PronosticoEspecial.query.filter_by(usuario_id=session['user_id']).first()
    if not pronostico or not pronostico.campeon_id:
        return jsonify({'error': 'No has realizado una predicción de campeón'}), 404
    
    seleccion = db.session.get(Seleccion, pronostico.campeon_id)
    if not seleccion:
        return jsonify({'error': 'Selección no encontrada'}), 404
    
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.lib.utils import ImageReader
        import io
        import os
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(letter))
        width, height = landscape(letter)
        
        # Fondo y bordes
        c.setStrokeColor(colors.HexColor('#FFD100'))
        c.setLineWidth(3)
        c.rect(30, 30, width-60, height-60)
        
        # Encabezado institucional
        c.setFillColor(colors.HexColor('#003580'))
        c.rect(0, height-70, width, 70, fill=True, stroke=False)
        c.setFillColor(colors.HexColor('#FFD100'))
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(width/2, height-40, "POLLA MUNDIALISTA DGA LEGAL 2026")
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 12)
        c.drawCentredString(width/2, height-58, "CERTIFICADO DE PREDICCIÓN")
        
        # Cuerpo
        y = height - 130
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, y, "Este certificado acredita que")
        y -= 30
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(colors.HexColor('#003580'))
        nombre_display = usuario.nombre_completo or usuario.username
        c.drawCentredString(width/2, y, nombre_display.upper())
        y -= 40
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 14)
        c.drawCentredString(width/2, y, "ha registrado su predicción oficial para el")
        y -= 25
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor('#CC0001'))
        c.drawCentredString(width/2, y, "CAMPEÓN DEL MUNDO 2026")
        y -= 35
        c.setFillColor(colors.HexColor('#FFD100'))
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(width/2, y, seleccion.nombre)
        y -= 50
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 12)
        fecha_pred = pronostico.fecha_actualizacion.strftime("%d de %B de %Y a las %H:%M")
        c.drawCentredString(width/2, y, f"Predicción realizada el: {fecha_pred}")
        
        # Pie
        c.setFillColor(colors.HexColor('#001a40'))
        c.rect(0, 0, width, 40, fill=True, stroke=False)
        c.setFillColor(colors.HexColor('#FFD100'))
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(width/2, 18, '"No solo litigamos resultados, también los pronosticamos." — DGA LEGAL 2026')
        
        c.save()
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"certificado_campeon_{usuario.username}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
    except ImportError:
        return jsonify({'error': 'ReportLab no está instalado'}), 500

@app.route('/api/areas-disponibles')
def api_areas_disponibles():
    areas = db.session.query(Usuario.area_trabajo).filter(Usuario.area_trabajo != None).distinct().all()
    # Limpieza básica desde el servidor también
    areas_clean = sorted(set([a[0].strip() for a in areas if a[0] and a[0].strip()]))
    return jsonify(areas_clean)

@app.route('/api/tabla-posiciones')
def api_tabla_posiciones():
    resultados = db.session.query(
        Usuario, PuntoTotal
    ).join(
        PuntoTotal, Usuario.id == PuntoTotal.usuario_id
    ).filter(
        Usuario.activo == True
    ).order_by(
        PuntoTotal.puntos_totales.desc()
    ).all()
    tabla = []
    for i, (usuario, puntos) in enumerate(resultados):
        tabla.append({
            'posicion': i + 1,
            'usuario_id': usuario.id,
            'username': usuario.username,
            'nombre_completo': usuario.nombre_completo,
            'area_trabajo': usuario.area_trabajo,
            'foto_perfil': usuario.foto_perfil,
            'puntos_totales': puntos.puntos_totales,
            'puntos_fase_grupos': puntos.puntos_fase_grupos,
            'puntos_eliminatorias': puntos.puntos_eliminatorias,
            'puntos_especiales': puntos.puntos_especiales,
            'resultados_exactos': puntos.resultados_exactos
        })
    return jsonify(tabla)

@app.route('/api/top-5')
def api_top_5():
    top = db.session.query(
        Usuario, PuntoTotal
    ).join(
        PuntoTotal, Usuario.id == PuntoTotal.usuario_id
    ).order_by(
        PuntoTotal.puntos_totales.desc()
    ).limit(5).all()
    return jsonify([{
        'username': u.username,
        'nombre_completo': u.nombre_completo,
        'puntos_totales': p.puntos_totales
    } for u, p in top])

@app.route('/api/historial-partidos')
def api_historial_partidos():
    limit = request.args.get('limit', type=int, default=50)
    offset = request.args.get('offset', type=int, default=0)
    query = Partido.query.filter(Partido.estado == 'finalizado')
    total = query.count()
    partidos = query.order_by(Partido.fecha_hora.desc()).limit(limit).offset(offset).all()
    return jsonify({
        'total': total, 'limit': limit, 'offset': offset,
        'data': [{
            'id': p.id,
            'local_nombre': p.local.nombre if p.local else '',
            'local_bandera': (p.local.bandera_local or p.local.bandera_url or
                              get_bandera_default(p.local.nombre if p.local else None)) if p.local else '/static/default_flag.png',
            'goles_local': p.goles_local,
            'visitante_nombre': p.visitante.nombre if p.visitante else '',
            'visitante_bandera': (p.visitante.bandera_local or p.visitante.bandera_url or
                                  get_bandera_default(p.visitante.nombre if p.visitante else None)) if p.visitante else '/static/default_flag.png',
            'goles_visitante': p.goles_visitante,
            'penales_local': p.penales_local,
            'penales_visitante': p.penales_visitante,
            'fecha_hora': p.fecha_hora.strftime('%d/%m/%Y %H:%M')
        } for p in partidos]
    })

@app.route('/api/perfil/actualizar', methods=['POST'])
def api_actualizar_perfil():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    usuario = db.session.get(Usuario, session['user_id'])
    data = request.json
    cambios = []
    if 'nombre_completo' in data and data['nombre_completo'] != usuario.nombre_completo:
        cambios.append(f"nombre: {usuario.nombre_completo} -> {data['nombre_completo']}")
        usuario.nombre_completo = data['nombre_completo']
    if 'area_trabajo' in data and data['area_trabajo'] != usuario.area_trabajo:
        cambios.append(f"área: {usuario.area_trabajo} -> {data['area_trabajo']}")
        usuario.area_trabajo = data['area_trabajo']
    if 'email' in data and data['email'] != usuario.email:
        cambios.append(f"email: {usuario.email} -> {data['email']}")
        usuario.email = data['email']
    if cambios:
        db.session.commit()
        session['nombre'] = usuario.nombre_completo or usuario.username
        log_auditoria('UPDATE', 'usuario', usuario.id, f"Perfil actualizado: {', '.join(cambios)}")
    return jsonify({'success': True})

# ========== NUEVO ENDPOINT: CAMBIAR CONTRASEÑA ==========
@app.route('/api/perfil/cambiar-password', methods=['POST'])
def api_cambiar_password():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Debe proporcionar contraseña actual y nueva'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'La nueva contraseña debe tener al menos 6 caracteres'}), 400
    
    usuario = db.session.get(Usuario, session['user_id'])
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    if not check_password_hash(usuario.password_hash, current_password):
        return jsonify({'error': 'Contraseña actual incorrecta'}), 401
    
    # Opcional: evitar usar la misma contraseña
    if check_password_hash(usuario.password_hash, new_password):
        return jsonify({'error': 'La nueva contraseña debe ser diferente a la actual'}), 400
    
    usuario.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    log_auditoria('UPDATE', 'password', usuario.id, 'Contraseña cambiada')
    
    return jsonify({'success': True, 'message': 'Contraseña actualizada correctamente'})

@app.route('/api/subir-avatar', methods=['POST'])
def api_subir_avatar():
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    if 'avatar' not in request.files:
        return jsonify({'error': 'No se envió archivo'}), 400
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó archivo'}), 400
    if file and allowed_file(file.filename):
        extension = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(
            f"user_{session['user_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
        )
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        avatar_url = f'/static/avatars/{filename}'
        usuario = db.session.get(Usuario, session['user_id'])
        if usuario:
            usuario.foto_perfil = avatar_url
            db.session.commit()
            log_auditoria('UPDATE', 'avatar', usuario.id, "Avatar actualizado")
            return jsonify({'success': True, 'avatar_url': avatar_url})
    return jsonify({'error': 'Formato no permitido. Use JPG, PNG, GIF'}), 400

# ==================================================
# PDF
# ==================================================

@app.route('/api/mis-pronosticos-pdf')
def api_mis_pronosticos_pdf():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    usuario = db.session.get(Usuario, session['user_id'])
    puntos_obj = db.session.get(PuntoTotal, session['user_id'])

    subquery = db.session.query(
        PronosticoPartido.partido_id,
        func.max(PronosticoPartido.fecha_pronostico).label('max_fecha')
    ).filter(
        PronosticoPartido.usuario_id == session['user_id']
    ).group_by(PronosticoPartido.partido_id).subquery()

    pronosticos = db.session.query(PronosticoPartido, Partido).join(
        subquery,
        (PronosticoPartido.partido_id == subquery.c.partido_id) &
        (PronosticoPartido.fecha_pronostico == subquery.c.max_fecha)
    ).join(
        Partido, PronosticoPartido.partido_id == Partido.id
    ).filter(
        PronosticoPartido.usuario_id == session['user_id']
    ).order_by(Partido.fecha_hora).all()

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib import colors

        buffer = io.BytesIO()
        c = rl_canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        def nueva_pagina():
            c.showPage()
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(colors.HexColor('#003580'))
            c.rect(0, height - 30, width, 30, fill=True, stroke=False)
            c.setFillColor(colors.white)
            c.drawCentredString(width / 2, height - 20,
                                "Polla Mundialista DGA LEGAL 2026 — continuación")
            c.setFillColor(colors.black)
            return height - 60

        c.setFillColor(colors.HexColor('#003580'))
        c.rect(0, height - 70, width, 70, fill=True, stroke=False)
        c.setFillColor(colors.HexColor('#FFD100'))
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width / 2, height - 35, "Polla Mundialista DGA LEGAL 2026")
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width / 2, height - 55, "RESUMEN DE PRONÓSTICOS")

        c.setFillColor(colors.black)
        y = height - 100
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"Usuario: {usuario.nombre_completo or usuario.username}")
        y -= 18
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Email: {usuario.email}  |  Área: {usuario.area_trabajo or '—'}")
        y -= 18
        c.drawString(50, y,
                     f"Puntos Totales: {puntos_obj.puntos_totales if puntos_obj else 0}  |  "
                     f"Exactos: {puntos_obj.resultados_exactos if puntos_obj else 0}  |  "
                     f"Emitido: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        y -= 25

        def dibujar_cabecera_tabla(yy):
            c.setFillColor(colors.HexColor('#001a40'))
            c.rect(40, yy - 5, width - 80, 18, fill=True, stroke=False)
            c.setFillColor(colors.HexColor('#FFD100'))
            c.setFont("Helvetica-Bold", 9)
            c.drawString(45, yy + 1, "PARTIDO")
            c.drawString(240, yy + 1, "PRONÓSTICO")
            c.drawString(390, yy + 1, "RESULTADO")
            c.drawString(480, yy + 1, "PTS")
            c.setFillColor(colors.black)
            return yy - 22

        y = dibujar_cabecera_tabla(y)

        for idx, (pron, partido) in enumerate(pronosticos):
            if y < 60:
                y = nueva_pagina()
                y = dibujar_cabecera_tabla(y)

            if idx % 2 == 0:
                c.setFillColor(colors.HexColor('#f4f1e8'))
                c.rect(40, y - 4, width - 80, 16, fill=True, stroke=False)
                c.setFillColor(colors.black)

            nombre_local = partido.local.nombre if partido.local else '?'
            nombre_visit = partido.visitante.nombre if partido.visitante else '?'
            partido_str = f"{nombre_local} vs {nombre_visit}"

            tipo = pron.tipo_pronostico or 'ganador'
            if tipo == 'ganador':
                if pron.ganador == 'local':
                    pron_str = f"Gana: {nombre_local}"
                elif pron.ganador == 'visitante':
                    pron_str = f"Gana: {nombre_visit}"
                else:
                    pron_str = "Empate"
            elif tipo == 'marcador':
                pron_str = f"{pron.goles_local}-{pron.goles_visitante}"
            elif tipo == 'penales':
                pron_str = (f"{pron.goles_local}-{pron.goles_visitante} "
                            f"(pen: {pron.penales_local}-{pron.penales_visitante})")
            else:
                pron_str = "—"

            if partido.goles_local is not None:
                if partido.penales_local is not None:
                    res_str = (f"{partido.goles_local}-{partido.goles_visitante} "
                               f"(pen: {partido.penales_local}-{partido.penales_visitante})")
                else:
                    res_str = f"{partido.goles_local}-{partido.goles_visitante}"
            else:
                res_str = "Pendiente"

            c.setFont("Helvetica", 8)
            c.drawString(45, y, partido_str[:38])
            c.drawString(240, y, pron_str[:28])
            c.drawString(390, y, res_str[:18])

            if pron.puntos and pron.puntos > 0:
                c.setFillColor(colors.HexColor('#1a6b1a'))
            c.setFont("Helvetica-Bold", 8)
            c.drawString(480, y, str(pron.puntos))
            c.setFillColor(colors.black)

            y -= 18

        c.setFillColor(colors.HexColor('#001a40'))
        c.rect(0, 0, width, 30, fill=True, stroke=False)
        c.setFillColor(colors.HexColor('#FFD100'))
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(width / 2, 11,
                            '"No solo litigamos resultados, también los pronosticamos." — DGA LEGAL 2026')

        c.save()
        buffer.seek(0)
        return send_file(
            buffer, as_attachment=True,
            download_name=f"pronosticos_{usuario.username}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
    except ImportError:
        return jsonify({'error': 'ReportLab no está instalado. Ejecuta: pip install reportlab'}), 500

# ==================================================
# ADMIN API ENDPOINTS
# ==================================================

@app.route('/api/admin/estadisticas')
@admin_required
def api_admin_estadisticas():
    total_usuarios = Usuario.query.count()
    total_partidos = Partido.query.count()
    partidos_finalizados = Partido.query.filter_by(estado='finalizado').count()
    total_pronosticos = PronosticoPartido.query.count()
    top_usuarios = db.session.query(
        Usuario, PuntoTotal
    ).join(
        PuntoTotal, Usuario.id == PuntoTotal.usuario_id
    ).order_by(
        PuntoTotal.puntos_totales.desc()
    ).limit(5).all()
    return jsonify({
        'total_usuarios': total_usuarios,
        'total_partidos': total_partidos,
        'partidos_finalizados': partidos_finalizados,
        'total_pronosticos': total_pronosticos,
        'top_usuarios': [{
            'username': u.username,
            'nombre_completo': u.nombre_completo,
            'puntos_totales': p.puntos_totales
        } for u, p in top_usuarios]
    })

@app.route('/api/admin/actualizar-resultado', methods=['POST'])
@admin_required
def api_admin_actualizar_resultado():
    data = request.json
    partido_id = data.get('partido_id')
    goles_local = data.get('goles_local')
    goles_visitante = data.get('goles_visitante')
    penales_local = data.get('penales_local')
    penales_visitante = data.get('penales_visitante')

    partido = db.session.get(Partido, partido_id)
    if not partido:
        return jsonify({'error': 'Partido no encontrado'}), 404

    historial = HistorialResultado(
        partido_id=partido_id,
        goles_local_anterior=partido.goles_local,
        goles_visitante_anterior=partido.goles_visitante,
        goles_local_nuevo=goles_local,
        goles_visitante_nuevo=goles_visitante,
        modificado_por=session['user_id']
    )
    db.session.add(historial)

    partido.goles_local = goles_local
    partido.goles_visitante = goles_visitante
    partido.penales_local = penales_local
    partido.penales_visitante = penales_visitante
    partido.estado = 'finalizado'
    db.session.commit()

    detalle = f"Resultado: {goles_local}-{goles_visitante}"
    if penales_local is not None:
        detalle += f" (pen: {penales_local}-{penales_visitante})"
    log_auditoria('UPDATE', 'resultado', partido_id, detalle)

    recalcular_puntos_partido(partido_id)
    
    # Regenerar toda la eliminatoria (R32, R16, QF, SF, FINAL, 3P)
    actualizar_toda_eliminatoria()
    
    return jsonify({'success': True})

@app.route('/api/admin/recalcular-puntos', methods=['POST'])
@admin_required
def api_admin_recalcular_puntos():
    db.session.query(PuntoTotal).update({
        PuntoTotal.puntos_fase_grupos: 0,
        PuntoTotal.puntos_eliminatorias: 0,
        PuntoTotal.puntos_totales: 0,
        PuntoTotal.resultados_exactos: 0
    })
    db.session.commit()
    partidos_finalizados = Partido.query.filter_by(estado='finalizado').all()
    for partido in partidos_finalizados:
        recalcular_puntos_partido(partido.id)
    log_auditoria('RECALCULAR', 'puntos', None, "Puntos recalculados completamente")
    return jsonify({'success': True})

@app.route('/api/admin/toggle-bloqueo-partido/<int:partido_id>', methods=['POST'])
@admin_required
def admin_toggle_bloqueo_partido(partido_id):
    partido = db.session.get(Partido, partido_id)
    if not partido:
        return jsonify({'error': 'Partido no encontrado'}), 404
    partido.bloqueado_manual = not partido.bloqueado_manual
    db.session.commit()
    estado = 'bloqueado' if partido.bloqueado_manual else 'desbloqueado'
    log_auditoria('UPDATE', 'partido', partido_id, f"Partido {estado} manualmente")
    return jsonify({'success': True, 'bloqueado_manual': partido.bloqueado_manual})

@app.route('/api/admin/crear-usuario', methods=['POST'])
@admin_required
def api_admin_crear_usuario():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    nombre_completo = request.form.get('nombre_completo')
    area_trabajo = request.form.get('area_trabajo')
    es_admin = request.form.get('es_admin') == 'true'
    if not username or not email or not password:
        return jsonify({'message': 'Campos requeridos incompletos'}), 400
    if Usuario.query.filter_by(username=username).first():
        return jsonify({'message': 'El nombre de usuario ya existe'}), 400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({'message': 'El email ya está registrado'}), 400
    if len(password) < 6:
        return jsonify({'message': 'La contraseña debe tener al menos 6 caracteres'}), 400
    hashed_password = generate_password_hash(password)
    nuevo_usuario = Usuario(
        username=username, email=email, password_hash=hashed_password,
        nombre_completo=nombre_completo, area_trabajo=area_trabajo,
        es_admin=es_admin, activo=True,
        foto_perfil='/static/avatars/default_avatar.png'
    )
    try:
        db.session.add(nuevo_usuario)
        db.session.commit()
        puntos = PuntoTotal(usuario_id=nuevo_usuario.id)
        db.session.add(puntos)
        db.session.commit()
        log_auditoria('CREATE', 'usuario', nuevo_usuario.id, f"Usuario creado: {username}")
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename and allowed_file(file.filename):
                extension = file.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(
                    f"user_{nuevo_usuario.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
                )
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                nuevo_usuario.foto_perfil = f'/static/avatars/{filename}'
                db.session.commit()
        return jsonify({'success': True, 'user_id': nuevo_usuario.id,
                        'message': 'Usuario creado exitosamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error al crear usuario: {str(e)}'}), 500

@app.route('/api/admin/eliminar-usuario/<int:usuario_id>', methods=['DELETE'])
@admin_required
def api_admin_eliminar_usuario(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    if usuario.username == 'ADMIN':
        return jsonify({'error': 'No se puede eliminar al administrador principal'}), 400
    PronosticoPartido.query.filter_by(usuario_id=usuario_id).delete()
    PronosticoEspecial.query.filter_by(usuario_id=usuario_id).delete()
    PuntoTotal.query.filter_by(usuario_id=usuario_id).delete()
    LogAuditoria.query.filter_by(usuario_id=usuario_id).delete()
    db.session.delete(usuario)
    db.session.commit()
    log_auditoria('DELETE', 'usuario', usuario_id, f"Usuario eliminado: {usuario.username}")
    return jsonify({'success': True})

@app.route('/api/admin/crear-partido', methods=['POST'])
@admin_required
def admin_crear_partido():
    data = request.json
    required = ['fase', 'seleccion_local_id', 'seleccion_visitante_id', 'fecha_hora']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Falta campo requerido: {field}'}), 400
    local = db.session.get(Seleccion, data['seleccion_local_id'])
    visitante = db.session.get(Seleccion, data['seleccion_visitante_id'])
    if not local or not visitante:
        return jsonify({'error': 'Equipo local o visitante no válido'}), 400
    nuevo_partido = Partido(
        fase=data['fase'],
        seleccion_local_id=data['seleccion_local_id'],
        seleccion_visitante_id=data['seleccion_visitante_id'],
        fecha_hora=datetime.strptime(data['fecha_hora'], '%Y-%m-%d %H:%M:%S'),
        grupo=data.get('grupo'),
        estado='pendiente',
        bloqueado_manual=False
    )
    db.session.add(nuevo_partido)
    db.session.commit()
    log_auditoria('CREATE', 'partido', nuevo_partido.id,
                  f'Partido creado: {local.nombre} vs {visitante.nombre}')
    return jsonify({'success': True, 'partido_id': nuevo_partido.id})

@app.route('/api/admin/backup', methods=['GET'])
@admin_required
def admin_backup():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        tablas = ['usuarios_polla', 'selecciones', 'partidos', 'pronosticos_partidos',
                  'pronosticos_especiales', 'puntos_totales']
        modelos = {
            'usuarios_polla': Usuario, 'selecciones': Seleccion, 'partidos': Partido,
            'pronosticos_partidos': PronosticoPartido,
            'pronosticos_especiales': PronosticoEspecial, 'puntos_totales': PuntoTotal
        }
        for tabla in tablas:
            datos = modelos[tabla].query.all()
            data_list = []
            for item in datos:
                item_dict = {c.name: getattr(item, c.name) for c in item.__table__.columns}
                for key, value in item_dict.items():
                    if isinstance(value, datetime):
                        item_dict[key] = value.isoformat()
                data_list.append(item_dict)
            zip_file.writestr(f'{tabla}.json', json.dumps(data_list, indent=2, default=str))
    zip_buffer.seek(0)
    log_auditoria('BACKUP', 'base_datos', None, 'Backup generado')
    return send_file(zip_buffer, as_attachment=True,
                     download_name=f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
                     mimetype='application/zip')

# ==================================================
# INICIALIZACIÓN
# ==================================================

def init_db():
    with app.app_context():
        db.create_all()

        # Migraciones con text()
        migraciones = [
            "ALTER TABLE pronosticos_partidos ADD COLUMN IF NOT EXISTS ganador VARCHAR(20)",
            "ALTER TABLE pronosticos_partidos ADD COLUMN IF NOT EXISTS tipo_pronostico VARCHAR(20) DEFAULT 'ganador'",
            "ALTER TABLE pronosticos_partidos ADD COLUMN IF NOT EXISTS penales_local INTEGER",
            "ALTER TABLE pronosticos_partidos ADD COLUMN IF NOT EXISTS penales_visitante INTEGER",
            "ALTER TABLE partidos ADD COLUMN IF NOT EXISTS bloqueado_manual BOOLEAN DEFAULT FALSE",
            "ALTER TABLE partidos ADD COLUMN IF NOT EXISTS penales_local INTEGER",
            "ALTER TABLE partidos ADD COLUMN IF NOT EXISTS penales_visitante INTEGER",
        ]
        for sql in migraciones:
            try:
                db.session.execute(text(sql))
                db.session.commit()
                print(f"✅ Migración ejecutada: {sql[:50]}...")
            except Exception as e:
                db.session.rollback()
                print(f"⚠️ Migración omitida: {e}")

        # Actualizar tipo_pronostico antiguos
        try:
            db.session.execute(text("""
                UPDATE pronosticos_partidos
                SET tipo_pronostico = CASE
                    WHEN goles_local IS NOT NULL AND goles_visitante IS NOT NULL THEN 'marcador'
                    ELSE 'ganador'
                END
                WHERE tipo_pronostico IS NULL OR tipo_pronostico = ''
            """))
            db.session.commit()
            print("✅ Migración tipo_pronostico completada")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Migración tipo_pronostico omitida: {e}")

        # Insertar selecciones si no existen
        if Seleccion.query.count() == 0:
            selecciones_data = [
                ("Argentina", "A"), ("Brasil", "B"), ("Francia", "C"), ("Alemania", "D"),
                ("España", "E"), ("Inglaterra", "F"), ("Países Bajos", "G"), ("Portugal", "H"),
                ("México", "A"), ("Uruguay", "B"), ("Croacia", "C"), ("Bélgica", "D"),
                ("Ecuador", "E"), ("Canadá", "B"), ("EE.UU.", "D"), ("Colombia", "K"),
                ("Paraguay", "D"), ("Japón", "F"), ("Corea del Sur", "A"), ("Australia", "D"),
                ("Senegal", "I"), ("Marruecos", "C"), ("Túnez", "F"), ("Egipto", "G"),
                ("Ghana", "L"), ("Costa de Marfil", "E"), ("Sudáfrica", "A"), ("Argelia", "J"),
                ("Suiza", "B"), ("Catar", "B"), ("Escocia", "C"), ("Haití", "C"),
                ("Turquía", "D"), ("Curazao", "E"), ("Suecia", "F"), ("Cabo Verde", "H"),
                ("Arabia Saudí", "H"), ("Irán", "G"), ("Nueva Zelanda", "G"), ("Irak", "I"),
                ("Noruega", "I"), ("Austria", "J"), ("Jordania", "J"), ("RD Congo", "K"),
                ("Uzbekistán", "K"), ("Panamá", "L"), ("Bosnia", "B"), ("República Checa", "A"),
            ]
            for nombre, grupo in selecciones_data:
                db.session.add(Seleccion(nombre=nombre, grupo=grupo))
            db.session.commit()
            print("✅ 48 selecciones insertadas")

        # ==================================================
        # INSERTAR / ACTUALIZAR LOS 104 PARTIDOS (siempre)
        # ==================================================
        from datetime import datetime

        # Lista completa de partidos de grupos (72) con nombres corregidos
        grupos_raw = [
            ("2026-06-11", "15:00", "México", "Sudáfrica", "A", "grupos"),
            ("2026-06-11", "22:00", "Corea del Sur", "República Checa", "A", "grupos"),
            ("2026-06-12", "15:00", "Canadá", "Bosnia", "B", "grupos"),
            ("2026-06-12", "21:00", "EE.UU.", "Paraguay", "D", "grupos"),
            ("2026-06-13", "15:00", "Catar", "Suiza", "B", "grupos"),
            ("2026-06-13", "18:00", "Brasil", "Marruecos", "C", "grupos"),
            ("2026-06-13", "21:00", "Haití", "Escocia", "C", "grupos"),
            ("2026-06-14", "00:00", "Australia", "Turquía", "D", "grupos"),
            ("2026-06-14", "13:00", "Alemania", "Curazao", "E", "grupos"),
            ("2026-06-14", "16:00", "Países Bajos", "Japón", "F", "grupos"),
            ("2026-06-14", "19:00", "Costa de Marfil", "Ecuador", "E", "grupos"),
            ("2026-06-14", "22:00", "Suecia", "Túnez", "F", "grupos"),
            ("2026-06-15", "12:00", "España", "Cabo Verde", "H", "grupos"),
            ("2026-06-15", "15:00", "Bélgica", "Egipto", "G", "grupos"),
            ("2026-06-15", "18:00", "Arabia Saudí", "Uruguay", "H", "grupos"),
            ("2026-06-15", "21:00", "Irán", "Nueva Zelanda", "G", "grupos"),
            ("2026-06-16", "15:00", "Francia", "Senegal", "I", "grupos"),
            ("2026-06-16", "18:00", "Irak", "Noruega", "I", "grupos"),
            ("2026-06-16", "21:00", "Argentina", "Argelia", "J", "grupos"),
            ("2026-06-17", "00:00", "Austria", "Jordania", "J", "grupos"),
            ("2026-06-17", "13:00", "Portugal", "RD Congo", "K", "grupos"),
            ("2026-06-17", "16:00", "Inglaterra", "Croacia", "L", "grupos"),
            ("2026-06-17", "19:00", "Ghana", "Panamá", "L", "grupos"),
            ("2026-06-17", "22:00", "Uzbekistán", "Colombia", "K", "grupos"),
            ("2026-06-18", "12:00", "República Checa", "Sudáfrica", "A", "grupos"),
            ("2026-06-18", "15:00", "Suiza", "Bosnia", "B", "grupos"),
            ("2026-06-18", "18:00", "Canadá", "Catar", "B", "grupos"),
            ("2026-06-18", "21:00", "México", "Corea del Sur", "A", "grupos"),
            ("2026-06-19", "15:00", "EE.UU.", "Australia", "D", "grupos"),
            ("2026-06-19", "18:00", "Escocia", "Marruecos", "C", "grupos"),
            ("2026-06-19", "21:00", "Brasil", "Haití", "C", "grupos"),
            ("2026-06-20", "00:00", "Turquía", "Paraguay", "D", "grupos"),
            ("2026-06-20", "13:00", "Países Bajos", "Suecia", "F", "grupos"),
            ("2026-06-20", "16:00", "Alemania", "Costa de Marfil", "E", "grupos"),
            ("2026-06-20", "22:00", "Ecuador", "Curazao", "E", "grupos"),
            ("2026-06-21", "00:00", "Túnez", "Japón", "F", "grupos"),
            ("2026-06-21", "12:00", "España", "Arabia Saudí", "H", "grupos"),
            ("2026-06-21", "15:00", "Bélgica", "Irán", "G", "grupos"),
            ("2026-06-21", "18:00", "Uruguay", "Cabo Verde", "H", "grupos"),
            ("2026-06-21", "21:00", "Nueva Zelanda", "Egipto", "G", "grupos"),
            ("2026-06-22", "13:00", "Argentina", "Austria", "J", "grupos"),
            ("2026-06-22", "17:00", "Francia", "Irak", "I", "grupos"),
            ("2026-06-22", "20:00", "Noruega", "Senegal", "I", "grupos"),
            ("2026-06-22", "23:00", "Jordania", "Argelia", "J", "grupos"),
            ("2026-06-23", "13:00", "Portugal", "Uzbekistán", "K", "grupos"),
            ("2026-06-23", "16:00", "Inglaterra", "Ghana", "L", "grupos"),
            ("2026-06-23", "19:00", "Panamá", "Croacia", "L", "grupos"),
            ("2026-06-23", "22:00", "Colombia", "RD Congo", "K", "grupos"),
            ("2026-06-24", "15:00", "Suiza", "Canadá", "B", "grupos"),
            ("2026-06-24", "15:00", "Bosnia", "Catar", "B", "grupos"),
            ("2026-06-24", "18:00", "Escocia", "Brasil", "C", "grupos"),
            ("2026-06-24", "18:00", "Marruecos", "Haití", "C", "grupos"),
            ("2026-06-24", "21:00", "República Checa", "México", "A", "grupos"),
            ("2026-06-24", "21:00", "Sudáfrica", "Corea del Sur", "A", "grupos"),
            ("2026-06-25", "16:00", "Curazao", "Costa de Marfil", "E", "grupos"),
            ("2026-06-25", "16:00", "Ecuador", "Alemania", "E", "grupos"),
            ("2026-06-25", "19:00", "Japón", "Suecia", "F", "grupos"),
            ("2026-06-25", "19:00", "Túnez", "Países Bajos", "F", "grupos"),
            ("2026-06-25", "22:00", "Turquía", "EE.UU.", "D", "grupos"),
            ("2026-06-25", "22:00", "Paraguay", "Australia", "D", "grupos"),
            ("2026-06-26", "15:00", "Noruega", "Francia", "I", "grupos"),
            ("2026-06-26", "15:00", "Senegal", "Irak", "I", "grupos"),
            ("2026-06-26", "20:00", "Cabo Verde", "Arabia Saudí", "H", "grupos"),
            ("2026-06-26", "20:00", "Uruguay", "España", "H", "grupos"),
            ("2026-06-26", "23:00", "Egipto", "Irán", "G", "grupos"),
            ("2026-06-26", "23:00", "Nueva Zelanda", "Bélgica", "G", "grupos"),
            ("2026-06-27", "17:00", "Panamá", "Inglaterra", "L", "grupos"),
            ("2026-06-27", "17:00", "Croacia", "Ghana", "L", "grupos"),
            ("2026-06-27", "19:30", "Colombia", "Portugal", "K", "grupos"),
            ("2026-06-27", "19:30", "RD Congo", "Uzbekistán", "K", "grupos"),
            ("2026-06-27", "22:00", "Argelia", "Austria", "J", "grupos"),
            ("2026-06-27", "22:00", "Jordania", "Argentina", "J", "grupos"),
        ]

        # Lista de partidos de eliminatoria (32)
        elim_raw = [
            ("2026-06-28", "14:00", "R32"),
            ("2026-06-29", "12:00", "R32"),
            ("2026-06-29", "15:30", "R32"),
            ("2026-06-29", "20:00", "R32"),
            ("2026-06-30", "12:00", "R32"),
            ("2026-06-30", "16:00", "R32"),
            ("2026-06-30", "20:00", "R32"),
            ("2026-07-01", "11:00", "R32"),
            ("2026-07-01", "15:00", "R32"),
            ("2026-07-01", "19:00", "R32"),
            ("2026-07-02", "14:00", "R32"),
            ("2026-07-02", "18:00", "R32"),
            ("2026-07-02", "22:00", "R32"),
            ("2026-07-03", "13:00", "R32"),
            ("2026-07-03", "17:00", "R32"),
            ("2026-07-03", "20:30", "R32"),
            ("2026-07-04", "12:00", "R16"),
            ("2026-07-04", "16:00", "R16"),
            ("2026-07-05", "15:00", "R16"),
            ("2026-07-05", "19:00", "R16"),
            ("2026-07-06", "14:00", "R16"),
            ("2026-07-06", "19:00", "R16"),
            ("2026-07-07", "11:00", "R16"),
            ("2026-07-07", "15:00", "R16"),
            ("2026-07-09", "15:00", "QF"),
            ("2026-07-10", "14:00", "QF"),
            ("2026-07-11", "16:00", "QF"),
            ("2026-07-11", "20:00", "QF"),
            ("2026-07-14", "14:00", "SF"),
            ("2026-07-15", "14:00", "SF"),
            ("2026-07-18", "16:00", "3P"),
            ("2026-07-19", "14:00", "FINAL"),
        ]

        def upsert_partido(fecha_str, hora_str, fase, grupo, local_nombre, visit_nombre):
            dt = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
            local = Seleccion.query.filter_by(nombre=local_nombre).first() if local_nombre else None
            visit = Seleccion.query.filter_by(nombre=visit_nombre).first() if visit_nombre else None
            
            partido = Partido.query.filter_by(fecha_hora=dt, fase=fase).first()
            if not partido:
                partido = Partido(
                    fase=fase,
                    grupo=grupo,
                    seleccion_local_id=local.id if local else None,
                    seleccion_visitante_id=visit.id if visit else None,
                    fecha_hora=dt,
                    estado='pendiente'
                )
                db.session.add(partido)
            else:
                if partido.seleccion_local_id != (local.id if local else None):
                    partido.seleccion_local_id = local.id if local else None
                if partido.seleccion_visitante_id != (visit.id if visit else None):
                    partido.seleccion_visitante_id = visit.id if visit else None
                if partido.grupo != grupo:
                    partido.grupo = grupo
            return partido

        # Insertar grupos
        for fecha_str, hora_str, local_n, visit_n, grupo, fase in grupos_raw:
            upsert_partido(fecha_str, hora_str, fase, grupo, local_n, visit_n)

        # Insertar eliminatoria
        for fecha_str, hora_str, fase in elim_raw:
            upsert_partido(fecha_str, hora_str, fase, None, None, None)

        db.session.commit()
        print(f"✅ Partidos verificados/actualizados: {Partido.query.count()} en total")

        # Actualizar eliminatoria completa después de cargar partidos
        print("🔄 Actualizando eliminatoria completa al iniciar...")
        actualizar_toda_eliminatoria()

        # Crear usuario ADMIN si no existe
        admin = Usuario.query.filter_by(username='ADMIN').first()
        if not admin:
            admin_user = Usuario(
                username='ADMIN', email='admin@polla.com',
                password_hash=generate_password_hash('admin123'),
                nombre_completo='Administrador', area_trabajo='Administración',
                es_admin=True, activo=True
            )
            db.session.add(admin_user)
            db.session.commit()
            puntos_admin = PuntoTotal(usuario_id=admin_user.id)
            db.session.add(puntos_admin)
            db.session.commit()
            print("\n" + "=" * 50)
            print("✅ USUARIO ADMIN CREADO")
            print("   Usuario: ADMIN  |  Contraseña: admin123")
            print("=" * 50 + "\n")
        else:
            print("✅ Usuario ADMIN ya existe")

        print("✅ Base de datos inicializada correctamente")

# ==================================================
# EJECUCIÓN
# ==================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🏆 POLLA MUNDIALISTA DGA LEGAL 2026")
    print("=" * 60)
    init_db()
    print("\n" + "=" * 60)
    print("📌 ACCESO AL SISTEMA")
    print("   URL: http://localhost:5001")
    print("   Usuario: ADMIN  |  Contraseña: admin123")
    print("=" * 60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)
