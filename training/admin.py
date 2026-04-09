from django.contrib import admin
from .models import Exercise, Routine, RoutineDetail, WorkoutLog

admin.site.register(Exercise)
admin.site.register(Routine)
admin.site.register(RoutineDetail)
admin.site.register(WorkoutLog)