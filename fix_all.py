from app import app, db, Partido, PronosticoPartido
from datetime import timedelta

with app.app_context():
    print("=" * 50)
    print("1. ELIMINANDO DUPLICADOS")
    print("=" * 50)
    
    # Paso 1: Identificar y eliminar duplicados (mismos equipos, fase y grupo)
    partidos = Partido.query.order_by(Partido.fecha_hora).all()
    vistos = {}
    duplicados = []
    
    for p in partidos:
        # Clave única: local_id, visitante_id, fase, grupo
        clave = (p.seleccion_local_id, p.seleccion_visitante_id, p.fase, p.grupo)
        if clave in vistos:
            duplicados.append(p)
        else:
            vistos[clave] = p.id
    
    print(f"✅ Se encontraron {len(duplicados)} partidos duplicados")
    for dup in duplicados:
        # Eliminar pronósticos asociados
        PronosticoPartido.query.filter_by(partido_id=dup.id).delete()
        db.session.delete(dup)
    db.session.commit()
    print("✅ Duplicados eliminados")
    
    print("\n" + "=" * 50)
    print("2. CORRIGIENDO FASES DE GRUPOS")
    print("=" * 50)
    
    # Paso 2: Asegurar que todos los partidos con grupo (A-L) tengan fase = 'grupos'
    grupos = ['A','B','C','D','E','F','G','H','I','J','K','L']
    for g in grupos:
        Partido.query.filter(Partido.grupo == g, Partido.fase != 'grupos').update(
            {'fase': 'grupos'}, synchronize_session=False
        )
    db.session.commit()
    print("✅ Fases de grupos corregidas")
    
    print("\n" + "=" * 50)
    print("3. VERIFICANDO Y CORRIGIENDO HORAS UTC")
    print("=" * 50)
    
    # Paso 3: Obtener un partido de referencia (México vs Sudáfrica, primer partido)
    # La hora real en Ecuador es: 2026-06-11 15:00:00 (UTC-5) → UTC = 20:00:00
    partido_ref = Partido.query.join(Partido.local).filter(
        Seleccion.nombre == 'México'
    ).join(Partido.visitante).filter(Seleccion.nombre == 'Sudáfrica').first()
    
    if partido_ref:
        utc_actual = partido_ref.fecha_hora
        utc_esperada = partido_ref.fecha_hora.replace(hour=20, minute=0, second=0)
        
        # Si la hora actual es 15:00 (hora Ecuador almacenada como UTC), sumamos 5 horas
        if utc_actual.hour == 15 and utc_actual.minute == 0:
            print("⚠️ Las fechas están en hora Ecuador. Sumando 5 horas a todos los partidos...")
            for p in Partido.query.all():
                p.fecha_hora = p.fecha_hora + timedelta(hours=5)
            db.session.commit()
            print("✅ Horas corregidas a UTC")
        elif utc_actual.hour == 20:
            print("✅ Las fechas ya están en UTC correctamente. No se requiere cambio.")
        else:
            print(f"⚠️ Hora inesperada: {utc_actual}. Revisa manualmente.")
    else:
        print("⚠️ No se encontró el partido de referencia. Omite ajuste de horas.")
    
    print("\n" + "=" * 50)
    print("4. ESTADÍSTICAS FINALES")
    print("=" * 50)
    total_partidos = Partido.query.count()
    partidos_grupos = Partido.query.filter_by(fase='grupos').count()
    partidos_elim = Partido.query.filter(Partido.fase != 'grupos').count()
    print(f"Total partidos únicos: {total_partidos}")
    print(f"  - Fase de grupos: {partidos_grupos}")
    print(f"  - Eliminatorias:  {partidos_elim}")
    print("\n✅ Todo corregido. Reinicia la aplicación y prueba.")
