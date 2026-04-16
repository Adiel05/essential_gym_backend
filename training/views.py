from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .utils import generar_rutina_inicial
from .models import RoutineDetail, WorkoutLog
from .serializers import RoutineDetailSerializer, WorkoutLogSerializer
from django.utils import timezone
from datetime import datetime
from .models import Routine, RoutineDetail, WorkoutLog
from django.utils import timezone
from datetime import datetime, timedelta
from .models import ExerciseCompletion

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generar_rutina(request):
    user = request.user
    if not user.training_goal or not user.experience_level:
        return Response({'error': 'Perfil incompleto'}, status=400)
    rutina = generar_rutina_inicial(user)
    return Response({'message': 'Rutina generada', 'routine_id': rutina.id})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rutina_hoy(request):
    user = request.user
    rutina = Routine.objects.filter(user=user, is_template=False).first()
    if not rutina:
        return Response({'error': 'No hay rutina activa'}, status=404)
    # Determinar día de la semana (1=lunes, 7=domingo)
    today = datetime.now().isoweekday()
    detalles = RoutineDetail.objects.filter(routine=rutina, week=1, day=today).order_by('order')
    serializer = RoutineDetailSerializer(detalles, many=True)
    return Response(serializer.data)

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
def reset_completion(request):
    user = request.user
    exercise_id = request.data.get('exercise_id')
    date_str = request.data.get('date')
    
    if not date_str:
        date = timezone.now().date()
    else:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    if exercise_id:
        
        try:
            exercise = Exercise.objects.get(id=exercise_id)
        except Exercise.DoesNotExist:
            return Response({'error': 'Ejercicio no encontrado'}, status=404)
        
        completion, _ = ExerciseCompletion.objects.get_or_create(
            user=user, date=date, exercise=exercise,
            defaults={'completed': False}
        )
        completion.completed = False
        completion.save()
        return Response({'message': f'Ejercicio {exercise.name} reiniciado'})
    else:
        
        completions = ExerciseCompletion.objects.filter(user=user, date=date)
        count = completions.update(completed=False)
        return Response({'message': f'Se reiniciaron {count} ejercicios del día {date}'})

