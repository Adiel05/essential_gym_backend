from rest_framework import serializers
from .models import Branch, Machine

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'

class MachineSerializer(serializers.ModelSerializer):
    branch_name = serializers.ReadOnlyField(source='branch.name')
    class Meta:
        model = Machine
        fields = '__all__'