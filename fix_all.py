from app import app, db, Partido, PronosticoPartido, Seleccion
from datetime import timedelta
from sqlalchemy.orm import aliased

with app.app_context():
    print("=" * 50)
    print("1. ELIMINANDO DUPLICADOS")
    print("=" * 50)
    
    partidos = Partido.query.order_by(Partido.fecha_hora).all()
    vistos = {}
    duplicados = []
    
    for p in partidos:
        clave = (p.seleccion_local_id, p.seleccion_visitante_id, p.fase, p.grupo)
        if clave in vistos:
            duplicados.append(p)
        else:
            vistos[clave] = p.id
    
    print(f"✅ Se encontraron {len(duplicados)} partidos duplicados")
    for dup in duplicados:
        PronosticoPartido.query.filter_by(partido_id=dup.id).delete()
        db.session.delete(dup)
    db.session.commit()
    print("✅ Duplicados eliminados")
    
    print("\n" + "=" * 50)
    print("2. CORRIGIENDO FASES DE GRUPOS")
    print("=" * 50)
    
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
    
    # Usar alias para evitar conflictos de join
    local_alias = aliased(Seleccion)
    visit_alias = aliased(Seleccion)
    
    partido_ref = Partido.query.join(local_alias, Partido.local).filter(
        local_alias.nombre == 'México'
    ).join(visit_alias, Partido.visitante).filter(
        visit_alias.nombre == 'Sudáfrica'
    ).first()
    
    if partido_ref:
        utc_actual = partido_ref.fecha_hora
        print(f"Referencia: México vs Sudáfrica -> {utc_actual}")
        # Hora real en Ecuador: 15:00 (UTC-5) => UTC 20:00
        if utc_actual.hour == 15:
            print("⚠️ Las fechas están en hora Ecuador. Sumando 5 horas a todos los partidos...")
            for p in Partido.query.all():
                p.fecha_hora = p.fecha_hora + timedelta(hours=5)
            db.session.commit()
            print("✅ Horas corregidas a UTC")
        elif utc_actual.hour == 20:
            print("✅ Las fechas ya están en UTC correctamente. No se requiere cambio.")
        else:
            print(f"⚠️ Hora inesperada: {utc_actual}. Se asume que ya está en UTC (no se modifica).")
    else:
        print("⚠️ No se encontró el partido de referencia (México vs Sudáfrica).")
        respuesta = input("¿Deseas sumar 5 horas a todos los partidos? (s/n): ")
        if respuesta.lower() == 's':
            for p in Partido.query.all():
                p.fecha_hora = p.fecha_hora + timedelta(hours=5)
            db.session.commit()
            print("✅ Horas sumadas.")
        else:
            print("No se modificaron las horas.")
    
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
