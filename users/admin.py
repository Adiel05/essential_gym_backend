from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # Campos que se muestran en la lista de usuarios
    list_display = ('username', 'email', 'role', 'training_goal', 'days_per_week', 'is_staff')
    # Campos que se pueden usar para buscar
    search_fields = ('username', 'email')
    # Filtros laterales
    list_filter = ('role', 'is_staff', 'is_active')
    
    # Organización del formulario de edición
    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {'fields': ('telefono', 'foto_perfil', 'role')}),
        ('Perfil de entrenamiento', {'fields': ('training_goal', 'days_per_week', 'experience_level', 'session_duration', 'injuries')}),
        ('Seguridad', {'fields': ('intentos_fallidos', 'bloqueado_hasta', 'ultimo_acceso', 'fecha_registro')}),
    )
    
    # Campos que se muestran al crear un nuevo usuario
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {'fields': ('telefono', 'role')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)