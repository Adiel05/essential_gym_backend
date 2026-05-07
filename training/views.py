from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime, date, timedelta
from .models import Routine, RoutineDetail, WorkoutLog, Exercise, ExerciseCompletion
from .serializers import RoutineDetailSerializer
from .utils import generar_rutina_inicial


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rutina_hoy(request):
    user = request.user
    rutina = Routine.objects.filter(user=user, is_template=False).first()
    if not rutina:
        return Response({'error': 'No hay rutina activa'}, status=404)

    today = date.today()
    day_of_week = today.isoweekday()  # 1=lunes, 7=domingo

    # Obtener los ejercicios programados para hoy (semana 1, por simplicidad)
    detalles = RoutineDetail.objects.filter(
        routine=rutina,
        week=1,
        day=day_of_week
    ).order_by('order')

    # Obtener los completados de hoy para este usuario
    completions = ExerciseCompletion.objects.filter(user=user, date=today)
    completion_dict = {c.exercise_id: c.completed for c in completions}

    # Construir respuesta manualmente (evitando el serializer que no incluye `completed`)
    data = []
    for detalle in detalles:
        data.append({
            'id': detalle.id,
            'exercise_id': detalle.exercise.id,
            'exercise_name': detalle.exercise.name,
            'muscle_group': detalle.exercise.muscle_group,
            'machine_required': detalle.exercise.machine_required,
            'sets': detalle.sets,
            'reps': detalle.reps,
            'order': detalle.order,
            'rest_seconds': detalle.rest_seconds,
            'completed': completion_dict.get(detalle.exercise.id, False),
            'gif_url': detalle.exercise.gif_file.url if detalle.exercise.gif_file else None
        })

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generar_rutina(request):
    user = request.user
    if not user.training_goal or not user.experience_level:
        return Response({'error': 'Perfil incompleto'}, status=400)
    rutina = generar_rutina_inicial(user)
    return Response({'message': 'Rutina generada', 'routine_id': rutina.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_entreno(request):
    user = request.user
    data = request.data
    log = WorkoutLog.objects.create(
        user=user,
        completed=True,
        difficulty=data.get('difficulty'),
        notes=data.get('notes', ''),
        actual_weights=data.get('actual_weights', {})
    )
    return Response({'message': 'Entreno registrado'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def completion_history(request):
    user = request.user
    start_date = request.query_params.get('start')
    end_date = request.query_params.get('end')

    if not start_date:
        start_date = (timezone.now() - timedelta(days=30)).date()
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    completions = ExerciseCompletion.objects.filter(
        user=user,
        date__range=[start_date, end_date]
    ).select_related('exercise').order_by('-date', 'exercise__name')

    data = []
    for c in completions:
        data.append({
            'date': c.date.isoformat(),
            'exercise_id': c.exercise.id,
            'exercise_name': c.exercise.name,
            'completed': c.completed
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_exercise_completion(request):
    user = request.user
    exercise_id = request.data.get('exercise_id')
    completed = request.data.get('completed', True)
    today = timezone.now().date()

    try:
        exercise = Exercise.objects.get(id=exercise_id)
    except Exercise.DoesNotExist:
        return Response({'error': 'Ejercicio no encontrado'}, status=404)

    completion, created = ExerciseCompletion.objects.get_or_create(
        user=user, date=today, exercise=exercise,
        defaults={'completed': completed}
    )
    if not created:
        completion.completed = completed
        completion.save()

    return Response({'message': 'Estado actualizado', 'completed': completion.completed})

