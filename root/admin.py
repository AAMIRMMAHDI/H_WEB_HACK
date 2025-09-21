from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('client_id', 'last_seen', 'last_command')
    readonly_fields = ('client_id', 'token', 'last_seen', 'last_command', 'command_id', 'last_output')