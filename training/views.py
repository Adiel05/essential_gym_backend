from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .utils import generar_rutina_inicial
from .models import RoutineDetail, WorkoutLog
from .serializers import RoutineDetailSerializer, WorkoutLogSerializer
from django.utils import timezone
from datetime import datetime
from .models import Routine, RoutineDetail, WorkoutLog

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
    # data espera: {'difficulty': 'moderate', 'notes': '...', 'actual_weights': {'press_banca': 50}}
    log = WorkoutLog.objects.create(
        user=user,
        completed=True,
        difficulty=data.get('difficulty'),
        notes=data.get('notes', ''),
        actual_weights=data.get('actual_weights', {})
    )
    return Response({'message': 'Entreno registrado'})