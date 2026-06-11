from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from .models import User
from inventory.models import StockTransaction
from clinics.models import Clinic
import uuid

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    clinic_name = serializers.CharField(write_only=True, required=True, max_length=255)
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password', 'clinic_name')

    def create(self, validated_data):
        clinic_name = validated_data.pop('clinic_name')
        
        # Auto-generate a unique code for the clinic
        clinic_code = str(uuid.uuid4())[:8].upper()
        
        # Create the new Clinic
        clinic = Clinic.objects.create(
            name=clinic_name,
            code=clinic_code,
            contact_email=validated_data['email'],
            contact_person=f"{validated_data['first_name']} {validated_data['last_name']}"
        )
        
        user = User.objects.create(
            username=validated_data['email'],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            clinic=clinic,
            role='clinic_administrator'
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class JoinClinicSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    clinic_code = serializers.CharField(write_only=True, required=True, max_length=50)
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password', 'clinic_code')

    def create(self, validated_data):
        clinic_code = validated_data.pop('clinic_code')
        
        try:
            clinic = Clinic.objects.get(code=clinic_code)
        except Clinic.DoesNotExist:
            raise serializers.ValidationError({"clinic_code": "Invalid Clinic Code."})
            
        user = User.objects.create(
            username=validated_data['email'],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            clinic=clinic,
            role='nurse'
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    total_issued = serializers.SerializerMethodField()
    total_received = serializers.SerializerMethodField()
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    clinic_code = serializers.CharField(source='clinic.code', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'first_name', 'last_name', 'email', 'phone_number', 
            'staff_number', 'role', 'clinic', 'clinic_name', 'clinic_code',
            'email_notifications', 'low_stock_alerts', 'expiry_alerts', 
            'table_view', 'last_login', 'total_issued', 'total_received'
        )
        read_only_fields = ('id', 'email', 'role', 'clinic', 'staff_number', 'last_login')

    def get_total_issued(self, obj):
        return StockTransaction.objects.filter(user=obj, transaction_type='issue').count()

    def get_total_received(self, obj):
        return StockTransaction.objects.filter(user=obj, transaction_type='receive').count()

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not check_password(value, user.password):
            raise serializers.ValidationError("Incorrect old password.")
        return value

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate(self, attrs):
        try:
            uid = urlsafe_base64_decode(attrs['uidb64']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uidb64": "Invalid user ID"})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "Invalid or expired token"})

        attrs['user'] = user
        return attrs
