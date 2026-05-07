from rest_framework import serializers
from .models import RoutineDetail, WorkoutLog

class RoutineDetailSerializer(serializers.ModelSerializer):
    exercise_name = serializers.CharField(source='exercise.name')
    exercise_id = serializers.IntegerField(source='exercise.id') 
    muscle_group = serializers.CharField(source='exercise.muscle_group')
    machine_required = serializers.CharField(source='exercise.machine_required')
    gif_url = serializers.SerializerMethodField() 
    completed = serializers.BooleanField(default=False)
    class Meta:
        model = RoutineDetail
        fields = ['id', 'exercise_id', 'exercise_name', 'muscle_group', 'machine_required', 'sets', 'reps', 'order', 'rest_seconds', 'gif_url', 'completed']
        
    def get_gif_url(self, obj):
        if obj.exercise.gif_file:
            return obj.exercise.gif_file.url
        return None

class WorkoutLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkoutLog
        fields = '__all__'