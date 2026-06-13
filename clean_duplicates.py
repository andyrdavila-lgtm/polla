from app import app, db, Partido, PronosticoPartido

with app.app_context():
    # Obtener todos los partidos ordenados por fecha
    partidos = Partido.query.order_by(Partido.fecha_hora).all()
    vistos = {}
    duplicados = []

    for p in partidos:
        # Clave única: combinación de equipos, fase y grupo
        clave = (p.seleccion_local_id, p.seleccion_visitante_id, p.fase, p.grupo)
        if clave in vistos:
            duplicados.append(p)
        else:
            vistos[clave] = p.id

    print(f"Se encontraron {len(duplicados)} partidos duplicados")

    for dup in duplicados:
        # Eliminar primero los pronósticos asociados
        PronosticoPartido.query.filter_by(partido_id=dup.id).delete()
        db.session.delete(dup)

    db.session.commit()
    print("✅ Duplicados eliminados correctamente")
