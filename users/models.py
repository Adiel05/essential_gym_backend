from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    ROLES = (
        ('superadmin', 'Superadmin'),
        ('admin', 'Admin'),
        ('recepcionista', 'Recepcionista'),
        ('entrenador', 'Entrenador'),
        ('socio', 'Socio'),
    )
    
    role = models.CharField(max_length=20, choices=ROLES, default='socio')
    telefono = models.CharField(max_length=15, blank=True, null=True)
    foto_perfil = models.ImageField(upload_to='perfiles/', null=True, blank=True)
    fecha_registro = models.DateTimeField(default=timezone.now)
    ultimo_acceso = models.DateTimeField(null=True, blank=True)
    intentos_fallidos = models.IntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    # Campos de perfilamiento para el entrenador virtual
    training_goal = models.CharField(
        max_length=20,
        choices=[
            ('hypertrophy', 'Hipertrofia'),
            ('fat_loss', 'Pérdida grasa'),
            ('endurance', 'Resistencia'),
            ('maintenance', 'Mantenimiento'),
        ],
        blank=True,
        null=True
    )
    days_per_week = models.PositiveSmallIntegerField(blank=True, null=True)
    injuries = models.TextField(blank=True, null=True)
    experience_level = models.CharField(
        max_length=15,
        choices=[
            ('beginner', 'Principiante'),
            ('intermediate', 'Intermedio'),
            ('advanced', 'Avanzado'),
        ],
        blank=True,
        null=True
    )
    session_duration = models.PositiveSmallIntegerField(blank=True, null=True)  # minutos

    def __str__(self):
        return f"{self.username} - {self.role}"
    
    def incrementar_intentos(self):
        self.intentos_fallidos += 1
        if self.intentos_fallidos >= 5:
            self.bloqueado_hasta = timezone.now() + timezone.timedelta(minutes=15)
        self.save()
    
    def resetear_intentos(self):
        self.intentos_fallidos = 0
        self.bloqueado_hasta = None
        self.save()