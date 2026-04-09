from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MachineViewSet
from .views import BranchViewSet

router = DefaultRouter()
router.register(r'machines', MachineViewSet, basename='machine')
router.register(r'branches', BranchViewSet, basename='branch')

urlpatterns = [
    path('', include(router.urls)),
]