from django.shortcuts import render

# Create your views here.

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from .models import CustomUser
import logging
import re

logger = logging.getLogger(__name__)

class LoginThrottle(AnonRateThrottle):
    rate = '5/minute'

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    # Validar que llegaron los campos
    if not username or not password:
        return Response(
            {'error': 'Usuario y contraseña son requeridos'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Buscar usuario para verificar si está bloqueado
        try:
            user = CustomUser.objects.get(username=username)
            
            # Verificar si está bloqueado
            if user.bloqueado_hasta and user.bloqueado_hasta > timezone.now():
                tiempo_restante = (user.bloqueado_hasta - timezone.now()).seconds // 60
                return Response({
                    'error': f'Demasiados intentos. Intenta de nuevo en {tiempo_restante} minutos.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Verificar si la cuenta está activa
            if not user.is_active:
                return Response({
                    'error': 'Cuenta desactivada. Contacta al administrador.'
                }, status=status.HTTP_403_FORBIDDEN)
                
        except CustomUser.DoesNotExist:
            user = None
        
        # Autenticar
        user = authenticate(username=username, password=password)
        
        if user:
            # Login exitoso - resetear intentos y actualizar último acceso
            user.resetear_intentos()
            user.ultimo_acceso = timezone.now()
            user.save()
            
            # Generar tokens
            refresh = RefreshToken.for_user(user)
            
            # Logging
            logger.info(f"Login exitoso: {username}")
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'nombre': user.first_name,
                    'apellido': user.last_name,
                }
            })
        else:
            # Login fallido
            if user:
                user.incrementar_intentos()
                logger.warning(f"Login fallido para {username}")
            
            return Response({
                'error': 'Usuario o contraseña incorrectos'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
    except Exception as e:
        logger.error(f"Error en login: {str(e)}")
        return Response({
            'error': 'Error interno del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
        
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    try:
        # Obtener datos del request
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        password2 = request.data.get('password2')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        telefono = request.data.get('telefono', '')
        
        # Validaciones
        if not username or not email or not password or not password2:
            return Response(
                {'error': 'Todos los campos son obligatorios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que las contraseñas coincidan
        if password != password2:
            return Response(
                {'error': 'Las contraseñas no coinciden'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar longitud de contraseña
        if len(password) < 8:
            return Response(
                {'error': 'La contraseña debe tener al menos 8 caracteres'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar formato de email
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return Response(
                {'error': 'Email no válido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar si el usuario ya existe
        if CustomUser.objects.filter(username=username).exists():
            return Response(
                {'error': 'El nombre de usuario ya está en uso'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar si el email ya existe
        if CustomUser.objects.filter(email=email).exists():
            return Response(
                {'error': 'El email ya está registrado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear el usuario
        user = CustomUser.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            first_name=first_name,
            last_name=last_name,
            telefono=telefono,
            role='socio'  # Por defecto, todos los registros son socios
        )
        
        return Response({
            'message': 'Usuario creado exitosamente',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Error interno del servidor: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        

@api_view(['POST'])
def logout_view(request):
    try:
        # Blacklist el token si quieres (requiere configuración extra)
        return Response({'message': 'Sesión cerrada exitosamente'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)



@api_view(['GET'])
def dashboard_view(request):
    return Response({
        'message': f'Bienvenido {request.user.get_full_name() or request.user.username}',
        'role': request.user.role,
        'ultimo_acceso': request.user.ultimo_acceso,
        'fecha_registro': request.user.fecha_registro
    })