# training/utils.py
from .models import Exercise, Routine, RoutineDetail

def generar_rutina_inicial(user):
    """
    Genera una rutina personalizada completa de 4 semanas,
    distribuida en los días que el socio seleccionó.
    """
    # Verificar si ya tiene rutina
    rutina_existente = Routine.objects.filter(user=user).first()
    if rutina_existente:
        return rutina_existente

    # Obtener datos del perfil
    days = user.days_per_week or 3
    goal = user.training_goal or 'hypertrophy'
    level = user.experience_level or 'beginner'

    # Crear la rutina base
    rutina = Routine.objects.create(
        name=f"Plan de {user.username}",
        description=f"Rutina personalizada - Objetivo: {goal} - Nivel: {level} - {days} días/semana",
        duration_weeks=4,
        days_per_week=days,
        user=user,
        is_template=False
    )

    # Obtener ejercicios (o crearlos si no existen)
    ejercicios = list(Exercise.objects.all())
    if not ejercicios:
        ejercicios = crear_ejercicios_prueba()

    # Determinar días de entrenamiento (1=lunes, 2=martes, ..., 7=domingo)
    # Usamos los primeros 'days' días de la semana
    training_days = list(range(1, days + 1))

    # Distribución profesional según nivel y objetivo
    if level == 'beginner':
        # Principiante: FULL BODY (mismos ejercicios todos los días)
        for day in training_days:
            for i, ej in enumerate(ejercicios[:6], start=1):
                RoutineDetail.objects.create(
                    routine=rutina,
                    exercise=ej,
                    week=1,
                    day=day,
                    sets=3,
                    reps=12,
                    order=i,
                    rest_seconds=60
                )

    elif level == 'intermediate':
        # Intermedio: Push/Pull/Legs (distribución por tipo de día)
        # Necesitamos clasificar los ejercicios por grupo muscular
        push = [ej for ej in ejercicios if ej.muscle_group in ['chest', 'shoulders']]
        pull = [ej for ej in ejercicios if ej.muscle_group in ['back']]
        legs = [ej for ej in ejercicios if ej.muscle_group == 'legs']
        
        # Si no hay suficientes, completamos con los primeros ejercicios
        if len(push) < 3: push = ejercicios[:3]
        if len(pull) < 3: pull = ejercicios[:3]
        if len(legs) < 3: legs = ejercicios[:3]
        
        # Asignar según el día (patrón Push/Pull/Legs)
        day_pattern = {1: push, 2: pull, 3: legs}
        for day in training_days:
            exercises = day_pattern.get(day, push)
            for i, ej in enumerate(exercises[:4], start=1):
                RoutineDetail.objects.create(
                    routine=rutina,
                    exercise=ej,
                    week=1,
                    day=day,
                    sets=4,
                    reps=10,
                    order=i,
                    rest_seconds=75
                )

    else:  # advanced
        # Avanzado: Mayor volumen y ejercicios más complejos
        # Usamos los primeros 6 ejercicios para todos los días
        for day in training_days:
            for i, ej in enumerate(ejercicios[:8], start=1):
                RoutineDetail.objects.create(
                    routine=rutina,
                    exercise=ej,
                    week=1,
                    day=day,
                    sets=4,
                    reps=8,
                    order=i,
                    rest_seconds=90
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
        {"name": "Peso muerto", "muscle_group": "legs", "difficulty": 3, "machine_required": "Barra"},
        {"name": "Jalón al pecho", "muscle_group": "back", "difficulty": 2, "machine_required": "Polea alta"},
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