from rest_framework import serializers
from .models import RoutineDetail, WorkoutLog

class RoutineDetailSerializer(serializers.ModelSerializer):
    exercise_name = serializers.CharField(source='exercise.name')
    muscle_group = serializers.CharField(source='exercise.muscle_group')
    machine_required = serializers.CharField(source='exercise.machine_required')
    class Meta:
        model = RoutineDetail
        fields = ['id', 'exercise_name', 'muscle_group', 'machine_required', 'sets', 'reps', 'order', 'rest_seconds']

class WorkoutLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkoutLog
        fields = '__all__'