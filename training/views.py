# training/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, date, timedelta
from .models import Routine, RoutineDetail, WorkoutLog, Exercise, ExerciseCompletion
from .serializers import RoutineDetailSerializer
from .utils import generar_rutina_inicial
from .models import CorrectionLog


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rutina_hoy(request):
    user = request.user
    rutina = Routine.objects.filter(user=user, is_template=False).first()
    if not rutina:
        return Response({"error": "No hay rutina activa"}, status=404)

    today = date.today()
    workout_completed = WorkoutLog.objects.filter(user=user, date=today).exists()
    day_of_week = today.isoweekday()

    # Calcular la semana actual (1 a 4) basada en start_date
    if rutina.start_date:
        days_since_start = (today - rutina.start_date).days
        week = (days_since_start // 7) + 1
        if week > 4:
            week = 4  # Si supera la semana 4, seguir mostrando semana 4
    else:
        week = 1  # compatibilidad con rutinas antiguas

    # Obtener los ejercicios de la semana correspondiente
    detalles = RoutineDetail.objects.filter(
        routine=rutina, week=week, day=day_of_week
    ).order_by("order")

    completions = ExerciseCompletion.objects.filter(user=user, date=today)
    completion_dict = {c.exercise_id: c.completed for c in completions}

    data = []
    for detalle in detalles:
        data.append(
            {
                "id": detalle.id,
                "exercise_id": detalle.exercise.id,
                "exercise_name": detalle.exercise.name,
                "description": detalle.exercise.description,
                "muscle_group": detalle.exercise.muscle_group,
                "machine_required": detalle.exercise.machine_required,
                "sets": detalle.sets,
                "reps": detalle.reps,
                "order": detalle.order,
                "rest_seconds": detalle.rest_seconds,
                "completed": completion_dict.get(detalle.exercise.id, False),
                "gif_url": (
                    detalle.exercise.gif_file.url if detalle.exercise.gif_file else None
                ),
                "suggested_weight": detalle.suggested_weight,
            }
        )

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def training_status(request):
    user = request.user
    today = date.today()
    completed = WorkoutLog.objects.filter(user=user, date=today).exists()
    return Response({"workout_completed": completed})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generar_rutina(request):
    user = request.user
    if not user.training_goal or not user.experience_level:
        return Response({"error": "Perfil incompleto"}, status=400)
    rutina = generar_rutina_inicial(user)
    return Response({"message": "Rutina generada", "routine_id": rutina.id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def registrar_entreno(request):
    user = request.user
    data = request.data
    log = WorkoutLog.objects.create(
        user=user,
        date=timezone.localtime().date(),
        completed=True,
        difficulty=data.get("difficulty"),
        notes=data.get("notes", ""),
        actual_weights=data.get("actual_weights", {}),
    )
    return Response({"message": "Entreno registrado"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def completion_history(request):
    user = request.user
    start_date = request.query_params.get("start")
    end_date = request.query_params.get("end")

    if not start_date:
        start_date = (timezone.now() - timedelta(days=30)).date()
    else:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    completions = (
        ExerciseCompletion.objects.filter(user=user, date__range=[start_date, end_date])
        .select_related("exercise")
        .order_by("-date", "exercise__name")
    )

    data = []
    for c in completions:
        data.append(
            {
                "date": c.date.isoformat(),
                "exercise_id": c.exercise.id,
                "exercise_name": c.exercise.name,
                "completed": c.completed,
            }
        )
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_exercise_completion(request):
    user = request.user
    exercise_id = request.data.get("exercise_id")
    completed = request.data.get("completed", True)
    today = timezone.now().date()

    try:
        exercise = Exercise.objects.get(id=exercise_id)
    except Exercise.DoesNotExist:
        return Response({"error": "Ejercicio no encontrado"}, status=404)

    completion, created = ExerciseCompletion.objects.get_or_create(
        user=user, date=today, exercise=exercise, defaults={"completed": completed}
    )
    if not created:
        completion.completed = completed
        completion.save()

    return Response(
        {"message": "Estado actualizado", "completed": completion.completed}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exercise_list(request):
    exercises = Exercise.objects.filter(is_active=True).order_by("name")
    data = []
    for ex in exercises:
        data.append(
            {
                "id": ex.id,
                "name": ex.name,
                "description": ex.description,
                "muscle_group": ex.muscle_group,
                "machine_required": ex.machine_required,
                "difficulty": ex.difficulty,
                "gif_url": ex.gif_file.url if ex.gif_file else None,
            }
        )
    return Response(data)


# training/views.py
from .models import Exercise


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exercise_alternatives(request):
    exercise_id = request.query_params.get("exercise_id")
    if not exercise_id:
        return Response({"error": "Se requiere exercise_id"}, status=400)

    try:
        target_exercise = Exercise.objects.get(id=exercise_id)
    except Exercise.DoesNotExist:
        return Response({"error": "Ejercicio no encontrado"}, status=404)

    # Busca alternativas por grupo muscular (excluyendo el propio)
    alternatives = Exercise.objects.filter(
        muscle_group=target_exercise.muscle_group, is_active=True
    ).exclude(id=exercise_id)[
        :5
    ]  # Limitamos a 5 sugerencias

    data = [
        {
            "id": alt.id,
            "name": alt.name,
            "description": alt.description,
            "muscle_group": alt.muscle_group,
            "machine_required": alt.machine_required,
            "difficulty": alt.difficulty,
            "gif_url": alt.gif_file.url if alt.gif_file else None,
        }
        for alt in alternatives
    ]

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def training_history(request):
    user = request.user
    logs = WorkoutLog.objects.filter(user=user).order_by("-date")
    data = []
    for log in logs:
        # Obtener los detalles de los ejercicios que el socio marcó como completados en esa fecha
        completions = ExerciseCompletion.objects.filter(
            user=user, date=log.date, completed=True
        )
        exercises = []
        for comp in completions:
            # Buscar el peso registrado en actual_weights (si existe)
            weight = log.actual_weights.get(str(comp.exercise.id))
            exercises.append(
                {
                    "exercise_name": comp.exercise.name,
                    "weight_used": weight if weight else None,
                }
            )
        data.append(
            {
                "date": log.date.isoformat(),
                "difficulty": log.difficulty,
                "notes": log.notes,
                "exercises": exercises,
            }
        )
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def log_correction(request):
    user = request.user
    data = request.data
    CorrectionLog.objects.create(
        user=user,
        exercise_name=data.get("exercise_name"),
        error_type=data.get("error_type"),
        severity=data.get("severity", "medium"),
        corrected=data.get("corrected", False),
    )
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def correction_stats(request):
    user = request.user
    from django.db.models import Count

    logs = (
        CorrectionLog.objects.filter(user=user)
        .values("date", "exercise_name")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    return Response(list(logs))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exercise_instructions(request):
    """Devuelve nombre, descripción e instrucciones de un ejercicio por nombre."""
    name = request.query_params.get("name", "").strip()
    if not name:
        return Response({"error": "Falta el parámetro name"}, status=400)

    try:
        exercise = Exercise.objects.get(name__iexact=name, is_active=True)
        return Response(
            {
                "id": exercise.id,
                "name": exercise.name,
                "description": exercise.description,
                "muscle_group": exercise.muscle_group,
                "difficulty": exercise.difficulty,
                "gif_url": (
                    request.build_absolute_uri(exercise.gif_file.url)
                    if exercise.gif_file
                    else None
                ),
            }
        )
    except Exercise.DoesNotExist:
        return Response({"error": f"Ejercicio '{name}' no encontrado"}, status=404)
