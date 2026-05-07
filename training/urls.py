from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

urlpatterns = [
    path('generar-rutina/', views.generar_rutina, name='generar_rutina'),
    path('rutina-hoy/', views.rutina_hoy, name='rutina_hoy'),
    path('registrar-entreno/', views.registrar_entreno, name='registrar_entreno'),
    path('completions/', views.completion_history, name='completion_history'),
    path('toggle-completion/', views.toggle_exercise_completion, name='toggle_completion'),
]