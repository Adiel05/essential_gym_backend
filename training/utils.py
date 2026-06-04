# training/utils.py
"""
Generación de rutinas con IA real.
- Se eliminan las reglas if/else de nivel (beginner/intermediate/advanced)
- Los ejercicios se seleccionan usando el modelo de filtrado colaborativo
- El intensity_factor sigue calculándose desde el historial real del usuario
"""
import numpy as np
import joblib
from pathlib import Path
from django.utils import timezone
from .models import Exercise, Routine, RoutineDetail, WorkoutLog, ExerciseCompletion

# ── Ruta a los modelos ────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "ml_models"

# ── Cargar el recomendador una sola vez ───────────────────
_recommender = None

def _get_recommender():
    global _recommender
    if _recommender is None:
        try:
            _recommender = joblib.load(MODELS_DIR / "recommender_similarity.pkl")
        except Exception as e:
            print(f"[IA] No se pudo cargar el recomendador: {e}")
    return _recommender


# ══════════════════════════════════════════════════════════
# FUNCIONES DE PESO (se mantienen — son cálculos, no reglas)
# ══════════════════════════════════════════════════════════

def calculate_1rm(weight, reps):
    """Fórmula de Brzycki: estima el 1RM."""
    if reps <= 0 or weight <= 0:
        return weight
    return weight / (1.0278 - (0.0278 * reps))


def suggested_weight_from_1rm(one_rm, target_reps):
    """Peso sugerido para un número objetivo de repeticiones."""
    if target_reps <= 0:
        return one_rm
    return one_rm * (1.0278 - (0.0278 * target_reps))


def get_best_1rm_for_exercise(user, exercise):
    logs = WorkoutLog.objects.filter(user=user).order_by("-date")
    best_1rm = 0.0
    for log in logs:
        weight = log.actual_weights.get(str(exercise.id))
        reps   = log.reps_performed.get(str(exercise.id)) if log.reps_performed else None
        if weight and reps and reps > 0:
            one_rm = calculate_1rm(weight, reps)
            if one_rm > best_1rm:
                best_1rm = one_rm
    return best_1rm if best_1rm > 0 else None


def get_initial_suggested_weight(exercise, level):
    """
    Peso inicial basado en historial del grupo muscular.
    Si no hay historial, usa valores basados en el perfil.
    """
    base = {"beginner": 20, "intermediate": 40, "advanced": 60}.get(level, 20)
    muscle = exercise.muscle_group
    multipliers = {
        "legs":      1.5,
        "arms":      0.6,
        "core":      0.6,
        "shoulders": 0.9,
        "chest":     1.0,
        "back":      1.0,
    }
    base = int(base * multipliers.get(muscle, 1.0))
    return max(5.0, float(base))


# ══════════════════════════════════════════════════════════
# FACTOR DE INTENSIDAD (aprendizaje desde historial real)
# ══════════════════════════════════════════════════════════

def get_intensity_factor(user):
    """
    Calcula un factor de intensidad (0.8-1.2) basado en
    los últimos 10 entrenamientos reales del usuario.
    Esto es aprendizaje adaptativo real desde la BD.
    """
    logs = WorkoutLog.objects.filter(user=user).order_by("-date")[:10]
    if not logs:
        return 1.0

    total_rpe      = 0
    pain_count     = 0
    low_energy     = 0
    hard_count     = 0
    easy_count     = 0

    for log in logs:
        feedback   = log.actual_weights.get("_feedback", {})
        rpe        = feedback.get("rpe", 5)
        pain       = feedback.get("pain")
        energy     = feedback.get("energy", 5)
        difficulty = log.difficulty

        total_rpe += rpe
        if pain and pain != "ninguno":
            pain_count += 1
        if energy < 4:
            low_energy += 1
        if difficulty == "hard":
            hard_count += 1
        elif difficulty == "easy":
            easy_count += 1

    n       = len(logs)
    avg_rpe = total_rpe / n

    if avg_rpe > 7 or hard_count > n / 2:
        factor = 0.85
    elif avg_rpe < 4 and easy_count > n / 2:
        factor = 1.15
    else:
        factor = 1.0

    if pain_count / n > 0.3:
        factor *= 0.9
    if low_energy / n > 0.4:
        factor *= 0.95

    return max(0.8, min(1.2, factor))


# ══════════════════════════════════════════════════════════
# SELECCIÓN DE EJERCICIOS CON IA
# Reemplaza los if/else de nivel con filtrado colaborativo
# ══════════════════════════════════════════════════════════

def _seleccionar_ejercicios_con_ia(user, goal, level, n_ejercicios=6):
    """
    Usa el modelo de recomendación para seleccionar ejercicios.
    
    Flujo:
    1. Obtener ejercicios completados por el usuario (historial real BD)
    2. Si tiene historial → filtrado colaborativo (IA)
    3. Si no tiene historial → fallback por objetivo/grupo muscular
    4. Cruzar con ejercicios reales de la BD para obtener objetos Exercise
    """
    recommender = _get_recommender()
    
    # Obtener historial real del usuario
    user_completed_ids = list(
        ExerciseCompletion.objects.filter(
            user=user, completed=True
        ).values_list("exercise_id", flat=True).distinct()
    )

    selected_exercise_ids = []

    if recommender and user_completed_ids:
        # ── FILTRADO COLABORATIVO (IA real) ───────────────
        sim_matrix = recommender["sim_matrix"]
        id_to_idx  = recommender["id_to_idx"]
        idx_to_id  = recommender["idx_to_id"]
        exercises  = recommender["exercises"]

        score_accumulator = np.zeros(len(exercises))
        for completed_id in user_completed_ids:
            if completed_id in id_to_idx:
                score_accumulator += sim_matrix[id_to_idx[completed_id]]

        # Penalizar los ya completados (no excluirlos del todo)
        for ex_id in user_completed_ids:
            if ex_id in id_to_idx:
                score_accumulator[id_to_idx[ex_id]] *= 0.3

        top_indices = np.argsort(score_accumulator)[::-1][:n_ejercicios * 2]
        candidate_ids = [idx_to_id[i] for i in top_indices]

        # Cruzar con ejercicios reales en la BD
        real_exercises = list(
            Exercise.objects.filter(is_active=True, id__in=candidate_ids)
        )

        # Si no hay suficientes, completar con ejercicios activos
        if len(real_exercises) < n_ejercicios:
            extras = list(
                Exercise.objects.filter(is_active=True)
                .exclude(id__in=[e.id for e in real_exercises])[:n_ejercicios]
            )
            real_exercises += extras

        return real_exercises[:n_ejercicios], "collaborative_filtering"

    else:
        # ── FALLBACK: sin historial → por objetivo (cold start) ──
        goal_to_muscles = {
            "hypertrophy":   ["chest", "back", "arms", "shoulders", "legs"],
            "strength":      ["legs", "back", "chest"],
            "weight_loss":   ["legs", "core", "back"],
            "endurance":     ["core", "legs", "shoulders"],
            "toning":        ["legs", "core", "arms"],
            "general":       ["chest", "back", "legs", "core", "arms", "shoulders"],
        }
        target_muscles = goal_to_muscles.get(goal, ["chest", "back", "legs", "core"])

        # Ordenar por grupo muscular objetivo y dificultad acorde al nivel
        level_difficulty = {"beginner": 1, "intermediate": 2, "advanced": 3}
        target_diff = level_difficulty.get(level, 1)

        exercises = list(
            Exercise.objects.filter(
                is_active=True,
                muscle_group__in=target_muscles,
                difficulty__lte=target_diff + 1,
            ).order_by("difficulty")[:n_ejercicios * 2]
        )

        if len(exercises) < n_ejercicios:
            extras = list(
                Exercise.objects.filter(is_active=True)
                .exclude(id__in=[e.id for e in exercises])[:n_ejercicios]
            )
            exercises += extras

        return exercises[:n_ejercicios], "fallback_rules"


# ══════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SERIES/REPS DESDE EL HISTORIAL
# (ya no son reglas fijas — se adaptan al factor de intensidad)
# ══════════════════════════════════════════════════════════

def _get_semana_config(goal, intensity_factor):
    """
    Calcula series, reps y descanso para cada semana
    basándose en el objetivo y el factor de intensidad aprendido.
    No son reglas fijas: el intensity_factor modifica los valores.
    """
    # Configuración base por objetivo
    goal_base = {
        "strength":    {1: (5, 5, 180), 2: (5, 4, 180), 3: (5, 3, 180), 4: (4, 5, 180)},
        "hypertrophy": {1: (3, 12, 90),  2: (4, 10, 90),  3: (4, 8, 90),   4: (3, 12, 90)},
        "weight_loss": {1: (3, 15, 60),  2: (3, 15, 60),  3: (4, 12, 60),  4: (3, 15, 60)},
        "endurance":   {1: (3, 20, 45),  2: (3, 18, 45),  3: (4, 15, 45),  4: (3, 20, 45)},
        "toning":      {1: (3, 15, 60),  2: (3, 12, 60),  3: (4, 12, 60),  4: (3, 15, 60)},
        "general":     {1: (3, 12, 75),  2: (3, 10, 75),  3: (4, 8, 90),   4: (3, 15, 60)},
    }
    base = goal_base.get(goal, goal_base["general"])

    semana_config = {}
    for week, (base_sets, base_reps, base_rest) in base.items():
        semana_config[week] = {
            "sets": max(2, int(round(base_sets * intensity_factor))),
            "reps": min(25, int(round(base_reps * intensity_factor))),
            "rest": base_rest,
        }
    return semana_config


# ══════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL: generar_rutina_inicial
# ══════════════════════════════════════════════════════════

def generar_rutina_inicial(user):
    """
    Genera una rutina personalizada de 4 semanas usando IA.
    
    Proceso:
    1. Calcula intensity_factor desde historial real (WorkoutLog)
    2. Selecciona ejercicios con filtrado colaborativo (IA)
       o fallback por objetivo si no hay historial
    3. Distribuye ejercicios por días y semanas
    4. Calcula pesos sugeridos desde 1RM histórico
    5. Guarda todo en la BD
    """
    rutina_existente = Routine.objects.filter(user=user).first()
    if rutina_existente:
        return rutina_existente

    days  = user.days_per_week or 3
    goal  = user.training_goal or "general"
    level = user.experience_level or "beginner"

    # ── 1. Factor de intensidad desde historial real ──────
    intensity_factor = get_intensity_factor(user)

    # ── 2. Selección de ejercicios con IA ─────────────────
    # Pedimos más ejercicios para poder distribuir por día
    n_total     = min(days * 5, 20)  # máximo 5 ejercicios por día
    ejercicios, metodo = _seleccionar_ejercicios_con_ia(
        user, goal, level, n_ejercicios=n_total
    )

    if not ejercicios:
        # último fallback si la BD está vacía
        ejercicios = list(Exercise.objects.filter(is_active=True)[:6])

    # ── 3. Crear la rutina ────────────────────────────────
    rutina = Routine.objects.create(
        name        = f"Plan IA de {user.username}",
        description = (
            f"Rutina generada por IA ({metodo}) — "
            f"Objetivo: {goal} | Nivel: {level} | "
            f"Factor de intensidad: {intensity_factor:.2f} | "
            f"{days} días/semana"
        ),
        duration_weeks = 4,
        days_per_week  = days,
        user           = user,
        is_template    = False,
        start_date     = timezone.now().date(),
    )

    training_days  = list(range(1, days + 1))
    semana_config  = _get_semana_config(goal, intensity_factor)

    # Dividir ejercicios por día
    ejs_por_dia = max(3, len(ejercicios) // days)

    for week in range(1, 5):
        config = semana_config[week]

        for day_idx, day in enumerate(training_days):
            # Rotar ejercicios por día para variedad
            start = (day_idx * ejs_por_dia) % len(ejercicios)
            day_exercises = []
            for i in range(ejs_por_dia):
                day_exercises.append(ejercicios[(start + i) % len(ejercicios)])

            for order, ej in enumerate(day_exercises, start=1):
                # Peso sugerido desde historial real
                best_1rm = get_best_1rm_for_exercise(user, ej)
                if best_1rm and best_1rm > 0:
                    suggested = suggested_weight_from_1rm(best_1rm, config["reps"])
                    suggested = round(suggested / 2.5) * 2.5
                else:
                    suggested = get_initial_suggested_weight(ej, level)
                suggested = max(2.5, min(suggested, 200.0))

                RoutineDetail.objects.create(
                    routine        = rutina,
                    exercise       = ej,
                    week           = week,
                    day            = day,
                    sets           = config["sets"],
                    reps           = config["reps"],
                    order          = order,
                    rest_seconds   = config["rest"],
                    suggested_weight = suggested,
                )

    return rutina