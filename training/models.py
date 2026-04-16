from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


class Exercise(models.Model):
    MUSCLE_GROUPS = [
        ("chest", "Pecho"),
        ("back", "Espalda"),
        ("legs", "Pierna"),
        ("shoulders", "Hombros"),
        ("arms", "Brazos"),
        ("core", "Core"),
    ]
    DIFFICULTY_CHOICES = [(1, "Principiante"), (2, "Intermedio"), (3, "Avanzado")]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    muscle_group = models.CharField(max_length=20, choices=MUSCLE_GROUPS)
    machine_required = models.CharField(
        max_length=100, blank=True, null=True
    )  # máquina o "peso libre"
    video_url = models.URLField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)  # imagen de referencia
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES, default=1)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Routine(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="routines")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    duration_weeks = models.IntegerField(default=4)
    days_per_week = models.IntegerField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_routines",
    )
    is_template = models.BooleanField(
        default=False, help_text="Si es plantilla para usar con múltiples usuarios"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.user.username}"


class RoutineDetail(models.Model):
    routine = models.ForeignKey(
        Routine, on_delete=models.CASCADE, related_name="details"
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    week = models.IntegerField()  # 1..duration_weeks
    day = models.IntegerField()  # 1..7
    sets = models.IntegerField()
    reps = models.IntegerField()
    order = models.IntegerField()
    rest_seconds = models.IntegerField(default=60)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week", "day", "order"]


class WorkoutLog(models.Model):
    DIFFICULTY_CHOICES = [
        ("easy", "Fácil"),
        ("moderate", "Moderado"),
        ("hard", "Difícil"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="workout_logs"
    )
    date = models.DateField(auto_now_add=True)
    completed = models.BooleanField(default=True)
    difficulty = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, blank=True, null=True
    )
    actual_weights = models.JSONField(
        default=dict, blank=True
    )  # ej: {exercise_id: weight}
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.date}"



class ExerciseCompletion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "date", "exercise")  

    def __str__(self):
        return f"{self.user.username} - {self.exercise.name} - {self.date} - {'✅' if self.completed else '❌'}"
