from rest_framework import serializers
from .models import CustomUser

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'telefono', 'foto_perfil', 'training_goal', 'days_per_week',
            'injuries', 'experience_level', 'session_duration'
        ]
        read_only_fields = ['id', 'username', 'email']  # estos no se pueden editar directamente