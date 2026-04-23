from django.contrib import admin
from django.utils.html import format_html
from .models import Exercise, Routine, RoutineDetail, WorkoutLog

class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'muscle_group', 'difficulty', 'preview_gif')
    readonly_fields = ('preview_gif',)
    fields = ('name', 'description', 'muscle_group', 'machine_required', 
              'gif_file', 'preview_gif', 'difficulty', 'is_active')
    
    def preview_gif(self, obj):
        if obj.gif_file:
            return format_html('<img src="{}" style="max-height: 100px;" />', obj.gif_file.url)
        return "Sin GIF"
    preview_gif.short_description = 'Vista previa'

admin.site.register(Exercise, ExerciseAdmin)
admin.site.register(Routine)
admin.site.register(RoutineDetail)
admin.site.register(WorkoutLog)