# chat/serializers.py
from rest_framework import serializers
from .models import Client, ClientActivity, Notification
from django.utils import timezone
from datetime import timedelta

class ClientSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()
    display_name = serializers.CharField(required=False, allow_blank=True)
    system_info = serializers.JSONField(read_only=True)

    class Meta:
        model = Client
        fields = [
            'client_id',
            'display_name',
            'token',
            'last_seen',
            'last_command',
            'command_id',
            'last_output',
            'is_online',
            'system_info',
            'is_streaming',
            'stream_type',
            'created_at'
        ]

    def get_is_online(self, obj):
        return obj.last_seen >= timezone.now() - timedelta(seconds=30)

class ClientActivitySerializer(serializers.ModelSerializer):
    client_id = serializers.CharField(source='client.client_id', read_only=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = ClientActivity
        fields = [
            'id',
            'client_id',
            'activity_type',
            'description',
            'details',
            'created_at',
            'time_ago'
        ]

    def get_time_ago(self, obj):
        now = timezone.now()
        diff = now - obj.created_at

        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600} ساعت پیش"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60} دقیقه پیش"
        return "همین حالا"

class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    icon_class = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'message',
            'is_read',
            'created_at',
            'time_ago',
            'icon_class'
        ]

    def get_time_ago(self, obj):
        now = timezone.now()
        diff = now - obj.created_at

        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600} ساعت پیش"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60} دقیقه پیش"
        return "همین حالا"

    def get_icon_class(self, obj):
        icons = {
            'info': 'fas fa-info-circle',
            'success': 'fas fa-check-circle',
            'warning': 'fas fa-exclamation-triangle',
            'error': 'fas fa-times-circle'
        }
        return icons.get(obj.notification_type, 'fas fa-bell')