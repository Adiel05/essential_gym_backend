from django.db import models


class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Machine(models.Model):
    STATUS_CHOICES = [
        ("active", "Activa"),
        ("maintenance", "En mantenimiento"),
        ("retired", "Dada de baja"),
    ]

    branch = models.ForeignKey(
        "Branch", on_delete=models.CASCADE, related_name="gym_machines"
    )
    
    name = models.CharField(max_length=100)
    zone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Zona dentro del gimnasio (ej. Zona de pesas)",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    purchase_date = models.DateField(blank=True, null=True)
    last_maintenance = models.DateField(blank=True, null=True)
    image = models.ImageField(
        upload_to="machines/", blank=True, null=True
    )  # para interactividad
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.branch.name} ({self.get_status_display()})"
