from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions
from .models import Machine
from .serializers import MachineSerializer
from .models import Branch
from .serializers import BranchSerializer


class MachineViewSet(viewsets.ModelViewSet):
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer
    permission_classes = [permissions.IsAuthenticated]  
    
    
class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated]