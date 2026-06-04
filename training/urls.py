#essential_gym_backend\training\urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import views_ia

urlpatterns = [
    path("generar-rutina/", views.generar_rutina, name="generar_rutina"),
    path("rutina-hoy/", views.rutina_hoy, name="rutina_hoy"),
    path("registrar-entreno/", views.registrar_entreno, name="registrar_entreno"),
    path("completions/", views.completion_history, name="completion_history"),
    path(
        "toggle-completion/", views.toggle_exercise_completion, name="toggle_completion"
    ),
    path("exercises/", views.exercise_list, name="exercise_list"),
    path("alternatives/", views.exercise_alternatives, name="exercise_alternatives"),
    path("history/", views.training_history, name="training_history"),
    path("status/", views.training_status, name="training_status"),
    path("log-correction/", views.log_correction, name="log_correction"),
    
    path("analyze-pose/",      views_ia.analyze_pose,      name="analyze-pose"),
    path("recommend-routine/", views_ia.recommend_routine, name="recommend-routine"),
    path("retrain/",           views_ia.retrain_model,     name="retrain-model"),
    path("exercise-info/", views.exercise_instructions, name="exercise_instructions"),
]
