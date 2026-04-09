
from .models import Exercise, Routine, RoutineDetail

def generar_rutina_inicial(user):
    """
    Genera una rutina personalizada para el socio basada en su perfil.
    Si ya tiene una rutina activa, no la reemplaza.
    Retorna la rutina creada o la existente.
    """
    # Verificar si el usuario ya tiene una rutina asignada
    rutina_existente = Routine.objects.filter(user=user).first()
    if rutina_existente:
        return rutina_existente

    # Obtener datos del perfil
    days = user.days_per_week or 3
    goal = user.training_goal or 'hypertrophy'
    level = user.experience_level or 'beginner'

    # Intentar obtener una plantilla por nombre (según nivel y objetivo)
    # Si no existe, se creará directamente la rutina para el usuario sin plantilla.
    template_name = None
    if level == 'beginner':
        template_name = 'Full Body Principiante' + (' (3d)' if days <= 3 else ' (4d)')
    elif level == 'intermediate':
        if goal == 'hypertrophy':
            template_name = 'Push/Pull/Legs (4d)'
        elif goal == 'fat_loss':
            template_name = 'Upper/Lower + Cardio (4d)'
        else:
            template_name = 'Full Body Intermedio (3d)'
    else:  # advanced
        if goal == 'hypertrophy':
            template_name = 'División Especializada (5d)'
        else:
            template_name = 'Push/Pull/Legs Avanzado (5d)'

    # Buscar la plantilla (debe existir en la BD y tener un usuario asignado)
    plantilla = None
    if template_name:
        plantilla = Routine.objects.filter(name=template_name, is_template=True).first()

    if plantilla:
        # Duplicar la plantilla para el usuario
        rutina_usuario = Routine.objects.create(
            name=f"{plantilla.name} - {user.username}",
            description=plantilla.description,
            duration_weeks=plantilla.duration_weeks,
            days_per_week=plantilla.days_per_week,
            user=user,
            is_template=False
        )
        for detalle in plantilla.details.all():
            RoutineDetail.objects.create(
                routine=rutina_usuario,
                exercise=detalle.exercise,
                week=detalle.week,
                day=detalle.day,
                sets=detalle.sets,
                reps=detalle.reps,
                order=detalle.order,
                rest_seconds=detalle.rest_seconds
            )
        return rutina_usuario
    else:
        # No existe plantilla: creamos una rutina personalizada directamente
        return crear_rutina_personalizada(user, days, goal, level)


def crear_rutina_personalizada(user, days, goal, level):
    """Crea una rutina básica directamente para el usuario (sin usar plantillas)."""
    rutina = Routine.objects.create(
        name=f"Rutina de {user.username}",
        description=f"Rutina personalizada para {user.get_full_name() or user.username} basada en objetivo {goal} y nivel {level}",
        duration_weeks=4,
        days_per_week=days,
        user=user,
        is_template=False
    )

    # Obtener ejercicios (si no hay, crear unos de prueba)
    ejercicios = Exercise.objects.all()
    if not ejercicios.exists():
        ejercicios = crear_ejercicios_prueba()

    # Asignar ejercicios a la rutina (todos al día 1 de la semana 1 por simplicidad)
    for i, ejercicio in enumerate(ejercicios[:6], start=1):
        RoutineDetail.objects.create(
            routine=rutina,
            exercise=ejercicio,
            week=1,
            day=1,
            sets=3,
            reps=12,
            order=i,
            rest_seconds=60
        )
    return rutina


def crear_ejercicios_prueba():
    """Crea ejercicios básicos si la base de datos está vacía."""
    ejercicios_data = [
        {"name": "Press banca", "muscle_group": "chest", "difficulty": 2, "machine_required": "Rack de fuerza"},
        {"name": "Sentadilla", "muscle_group": "legs", "difficulty": 2, "machine_required": "Rack de sentadillas"},
        {"name": "Dominadas", "muscle_group": "back", "difficulty": 3, "machine_required": "Barra de dominadas"},
        {"name": "Press militar", "muscle_group": "shoulders", "difficulty": 2, "machine_required": "Barra o mancuernas"},
        {"name": "Curl de bíceps", "muscle_group": "arms", "difficulty": 1, "machine_required": "Mancuernas"},
        {"name": "Plancha", "muscle_group": "core", "difficulty": 1, "machine_required": ""},
    ]
    ejercicios = []
    for data in ejercicios_data:
        ej, _ = Exercise.objects.get_or_create(
            name=data["name"],
            defaults={
                "muscle_group": data["muscle_group"],
                "difficulty": data["difficulty"],
                "machine_required": data["machine_required"],
                "is_active": True
            }
        )
        ejercicios.append(ej)
    return ejercicios