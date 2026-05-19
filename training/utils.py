# training/utils.py
from django.utils import timezone
from .models import Exercise, Routine, RoutineDetail, WorkoutLog


def get_intensity_factor(user):
    """Devuelve un factor de intensidad (0.8 a 1.2) basado en los últimos entrenamientos."""
    logs = WorkoutLog.objects.filter(user=user).order_by("-date")[:10]
    if not logs:
        return 1.0

    total_rpe = 0
    pain_count = 0
    low_energy_count = 0
    hard_count = 0
    easy_count = 0

    for log in logs:
        # Extraer feedback guardado en actual_weights['_feedback']
        feedback = log.actual_weights.get("_feedback", {})
        rpe = feedback.get("rpe", 5)
        pain = feedback.get("pain")
        energy = feedback.get("energy", 5)
        difficulty = log.difficulty

        total_rpe += rpe
        if pain and pain != "ninguno":
            pain_count += 1
        if energy < 4:
            low_energy_count += 1
        if difficulty == "hard":
            hard_count += 1
        elif difficulty == "easy":
            easy_count += 1

    n = len(logs)
    avg_rpe = total_rpe / n

    # Reglas de ajuste
    if avg_rpe > 7 or hard_count > n / 2:
        factor = 0.85  # demasiado difícil → bajar intensidad
    elif avg_rpe < 4 and easy_count > n / 2:
        factor = 1.15  # muy fácil → subir intensidad
    else:
        factor = 1.0

    # Si hay dolor frecuente (más de 30% de sesiones) bajar más
    if pain_count / n > 0.3:
        factor *= 0.9

    # Si energía baja frecuente, también reducir volumen (se puede reflejar en series)
    if low_energy_count / n > 0.4:
        factor *= 0.95

    return max(0.8, min(1.2, factor))  # acotar entre 0.8 y 1.2


def calculate_1rm(weight, reps):
    """Fórmula de Brzycki: estima el 1RM a partir de un peso y repeticiones"""
    if reps <= 0 or weight <= 0:
        return weight
    return weight / (1.0278 - (0.0278 * reps))


def suggested_weight_from_1rm(one_rm, target_reps):
    """Calcula el peso sugerido para un número objetivo de repeticiones"""
    if target_reps <= 0:
        return one_rm
    return one_rm * (1.0278 - (0.0278 * target_reps))


def get_best_1rm_for_exercise(user, exercise):
    logs = WorkoutLog.objects.filter(user=user).order_by("-date")
    best_1rm = 0.0
    for log in logs:
        weight = log.actual_weights.get(str(exercise.id))
        reps = log.reps_performed.get(str(exercise.id)) if log.reps_performed else None
        if weight and reps and reps > 0:
            one_rm = calculate_1rm(weight, reps)
            if one_rm > best_1rm:
                best_1rm = one_rm
    return best_1rm if best_1rm > 0 else None


def get_initial_suggested_weight(exercise, level):
    """
    Sugiere un peso inicial en kg basado en el nivel y el tipo de ejercicio.
    Usa reglas empíricas de entrenador:
    - Ejercicios de pierna tienen más peso.
    - Ejercicios de brazos o core menos.
    """
    # Peso base según nivel
    if level == "beginner":
        base = 20
    elif level == "intermediate":
        base = 40
    else:  # advanced
        base = 60

    # Ajuste por grupo muscular
    muscle = exercise.muscle_group
    if muscle == "legs":
        base = int(base * 1.5)  # +50%
    elif muscle in ["arms", "core"]:
        base = int(base * 0.6)  # -40%
    elif muscle in ["shoulders", "chest"]:
        base = int(base * 0.9)  # -10%
    # back se queda igual

    return max(5.0, float(base))  # nunca menos de 5 kg


def generar_rutina_inicial(user):
    """
    Genera una rutina personalizada completa de 4 semanas,
    distribuida en los días que el socio seleccionó.
    """
    rutina_existente = Routine.objects.filter(user=user).first()
    if rutina_existente:
        return rutina_existente

    days = user.days_per_week or 3
    goal = user.training_goal or "hypertrophy"
    level = user.experience_level or "beginner"

    # Crear la rutina base con fecha de inicio
    rutina = Routine.objects.create(
        name=f"Plan de {user.username}",
        description=f"Rutina personalizada - Objetivo: {goal} - Nivel: {level} - {days} días/semana",
        duration_weeks=4,
        days_per_week=days,
        user=user,
        is_template=False,
        start_date=timezone.now().date(),
    )

    ejercicios = list(Exercise.objects.all())
    if not ejercicios:
        ejercicios = crear_ejercicios_prueba()

    training_days = list(range(1, days + 1))

    # Aprendizaje por retroalimentación
    intensity_factor = get_intensity_factor(user)

    # Valores base de series, reps, descanso
    base_config = {
        1: (3, 12, 60),
        2: (3, 10, 75),
        3: (4, 8, 90),
        4: (3, 15, 60),
    }
    semana_config = {}
    for week, (base_sets, base_reps, base_rest) in base_config.items():
        sets = max(2, int(round(base_sets * intensity_factor)))
        reps = min(20, int(round(base_reps * intensity_factor)))
        semana_config[week] = {"sets": sets, "reps": reps, "rest": base_rest}

    for week in range(1, 5):
        config = semana_config[week]

        if level == "beginner":
            for day in training_days:
                for i, ej in enumerate(ejercicios[:6], start=1):
                    # Calcular peso sugerido
                    best_1rm = get_best_1rm_for_exercise(user, ej)
                    if best_1rm and best_1rm > 0:
                        suggested = suggested_weight_from_1rm(best_1rm, config["reps"])
                        suggested = round(suggested / 2.5) * 2.5
                    else:
                        suggested = get_initial_suggested_weight(ej, level)
                    # Asegurar límites
                    suggested = max(2.5, min(suggested, 150.0))

                    RoutineDetail.objects.create(
                        routine=rutina,
                        exercise=ej,
                        week=week,
                        day=day,
                        sets=config["sets"],
                        reps=config["reps"],
                        order=i,
                        rest_seconds=config["rest"],
                        suggested_weight=suggested,
                    )
        elif level == "intermediate":
            push = [
                ej for ej in ejercicios if ej.muscle_group in ["chest", "shoulders"]
            ]
            pull = [ej for ej in ejercicios if ej.muscle_group in ["back"]]
            legs = [ej for ej in ejercicios if ej.muscle_group == "legs"]
            if len(push) < 3:
                push = ejercicios[:3]
            if len(pull) < 3:
                pull = ejercicios[:3]
            if len(legs) < 3:
                legs = ejercicios[:3]
            day_pattern = {1: push, 2: pull, 3: legs}
            for day in training_days:
                exercises = day_pattern.get(day, push)
                for i, ej in enumerate(exercises[:4], start=1):
                    best_1rm = get_best_1rm_for_exercise(user, ej)
                    if best_1rm and best_1rm > 0:
                        suggested = suggested_weight_from_1rm(best_1rm, config["reps"])
                        suggested = round(suggested / 2.5) * 2.5
                    else:
                        suggested = get_initial_suggested_weight(ej, level)
                    suggested = max(2.5, min(suggested, 150.0))

                    RoutineDetail.objects.create(
                        routine=rutina,
                        exercise=ej,
                        week=week,
                        day=day,
                        sets=config["sets"],
                        reps=config["reps"],
                        order=i,
                        rest_seconds=config["rest"],
                        suggested_weight=suggested,
                    )
        else:  # advanced
            for day in training_days:
                for i, ej in enumerate(ejercicios[:8], start=1):
                    best_1rm = get_best_1rm_for_exercise(user, ej)
                    if best_1rm and best_1rm > 0:
                        suggested = suggested_weight_from_1rm(best_1rm, config["reps"])
                        suggested = round(suggested / 2.5) * 2.5
                    else:
                        suggested = get_initial_suggested_weight(ej, level)
                    suggested = max(2.5, min(suggested, 150.0))

                    RoutineDetail.objects.create(
                        routine=rutina,
                        exercise=ej,
                        week=week,
                        day=day,
                        sets=config["sets"],
                        reps=config["reps"],
                        order=i,
                        rest_seconds=config["rest"],
                        suggested_weight=suggested,
                    )

    return rutina


def crear_ejercicios_prueba():
    """Crea ejercicios básicos si la base de datos está vacía."""
    ejercicios_data = [
        {
            "name": "Press banca",
            "muscle_group": "chest",
            "difficulty": 2,
            "machine_required": "Rack de fuerza",
        },
        {
            "name": "Sentadilla",
            "muscle_group": "legs",
            "difficulty": 2,
            "machine_required": "Rack de sentadillas",
        },
        {
            "name": "Dominadas",
            "muscle_group": "back",
            "difficulty": 3,
            "machine_required": "Barra de dominadas",
        },
        {
            "name": "Press militar",
            "muscle_group": "shoulders",
            "difficulty": 2,
            "machine_required": "Barra o mancuernas",
        },
        {
            "name": "Curl de bíceps",
            "muscle_group": "arms",
            "difficulty": 1,
            "machine_required": "Mancuernas",
        },
        {
            "name": "Plancha",
            "muscle_group": "core",
            "difficulty": 1,
            "machine_required": "",
        },
        {
            "name": "Peso muerto",
            "muscle_group": "legs",
            "difficulty": 3,
            "machine_required": "Barra",
        },
        {
            "name": "Jalón al pecho",
            "muscle_group": "back",
            "difficulty": 2,
            "machine_required": "Polea alta",
        },
    ]
    ejercicios = []
    for data in ejercicios_data:
        ej, _ = Exercise.objects.get_or_create(
            name=data["name"],
            defaults={
                "muscle_group": data["muscle_group"],
                "difficulty": data["difficulty"],
                "machine_required": data["machine_required"],
                "is_active": True,
            },
        )
        ejercicios.append(ej)
    return ejercicios


def crear_ejercicios_prueba():
    """Crea ejercicios básicos si la base de datos está vacía."""
    ejercicios_data = [
        {
            "name": "Press banca",
            "muscle_group": "chest",
            "difficulty": 2,
            "machine_required": "Rack de fuerza",
        },
        {
            "name": "Sentadilla",
            "muscle_group": "legs",
            "difficulty": 2,
            "machine_required": "Rack de sentadillas",
        },
        {
            "name": "Dominadas",
            "muscle_group": "back",
            "difficulty": 3,
            "machine_required": "Barra de dominadas",
        },
        {
            "name": "Press militar",
            "muscle_group": "shoulders",
            "difficulty": 2,
            "machine_required": "Barra o mancuernas",
        },
        {
            "name": "Curl de bíceps",
            "muscle_group": "arms",
            "difficulty": 1,
            "machine_required": "Mancuernas",
        },
        {
            "name": "Plancha",
            "muscle_group": "core",
            "difficulty": 1,
            "machine_required": "",
        },
        {
            "name": "Peso muerto",
            "muscle_group": "legs",
            "difficulty": 3,
            "machine_required": "Barra",
        },
        {
            "name": "Jalón al pecho",
            "muscle_group": "back",
            "difficulty": 2,
            "machine_required": "Polea alta",
        },
    ]
    ejercicios = []
    for data in ejercicios_data:
        ej, _ = Exercise.objects.get_or_create(
            name=data["name"],
            defaults={
                "muscle_group": data["muscle_group"],
                "difficulty": data["difficulty"],
                "machine_required": data["machine_required"],
                "is_active": True,
            },
        )
        ejercicios.append(ej)
    return ejercicios
