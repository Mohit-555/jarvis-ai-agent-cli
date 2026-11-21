"""
voice/wake_word.py  —  Continuous Background Wake Word Listener for Jarvis

Listens for "Hello Jarvis", "Hey Jarvis", or "Jarvis" using low-CPU energy VAD
and Whisper-tiny. Automatically opens or focuses the Jarvis terminal window
and greets the user.
"""

import os
import re
import sys
import time
import shutil
import tempfile
import threading
import subprocess
from typing import Optional, List, Callable

import numpy as np
try:
    import soundfile as sf
    _HAS_SOUNDFILE = True
except ImportError:
    _HAS_SOUNDFILE = False


class WakeWordListener:
    """Background listener for the 'Hello Jarvis' wake word."""

    def __init__(
        self,
        config: Optional[dict] = None,
        on_wake_callback: Optional[Callable[[], None]] = None,
        sample_rate: int = 16000,
        energy_threshold: float = 350.0,
        model_name: str = "tiny",
    ):
        self.config = config or {}
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.model_name = self.config.get("wake_word_model", model_name)
        self.on_wake_callback = on_wake_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._whisper_model = None
        self._lock = threading.Lock()

    def _get_desktop_env(self) -> dict:
        """Ensure session environment variables are set for Wayland/X11 and DBus."""
        env = dict(os.environ)
        uid = os.getuid()

        if not env.get("XDG_RUNTIME_DIR"):
            env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"

        if not env.get("DBUS_SESSION_BUS_ADDRESS"):
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"

        if not env.get("DISPLAY"):
            env["DISPLAY"] = ":0"

        if not env.get("WAYLAND_DISPLAY"):
            if os.path.exists(f"/run/user/{uid}/wayland-0"):
                env["WAYLAND_DISPLAY"] = "wayland-0"

        if not env.get("XDG_CURRENT_DESKTOP"):
            env["XDG_CURRENT_DESKTOP"] = "GNOME"

        return env

    def _find_audio_recorder(self) -> Optional[List[str]]:
        """Select best available audio streaming CLI."""
        if shutil.which("pw-record"):
            return ["pw-record", "--rate", str(self.sample_rate), "--channels", "1", "--format", "s16", "-"]
        if shutil.which("arecord"):
            return ["arecord", "-q", "-r", str(self.sample_rate), "-c", "1", "-f", "S16_LE", "-t", "raw"]
        if shutil.which("parec"):
            return ["parec", f"--rate={self.sample_rate}", "--channels=1", "--format=s16le"]
        return None

    def _load_whisper_model(self):
        """Lazily load the lightweight Whisper model."""
        if self._whisper_model is None:
            try:
                import whisper
                self._whisper_model = whisper.load_model(self.model_name)
            except Exception as e:
                pass
        return self._whisper_model

    def is_wake_phrase(self, text: str) -> bool:
        """Check if transcribed text contains the wake word."""
        if not text:
            return False
        clean = re.sub(r"[?!.,;:~_`'\"()]+", " ", text.lower()).strip()
        wake_patterns = [
            r"\bhello\s+jarvis\b",
            r"\bhey\s+jarvis\b",
            r"\bok\s+jarvis\b",
            r"\bhi\s+jarvis\b",
            r"\bsun\s+jarvis\b",
            r"\bjarvis\b",
        ]
        return any(re.search(pat, clean) for pat in wake_patterns)

    def trigger_wake(self):
        """Action when wake word is detected: focus or launch Jarvis terminal."""
        env = self._get_desktop_env()
        user_name = self.config.get("user_name", "Mohit")
        first_name = user_name.strip().split()[0] if user_name else "Mohit"

        # 1. Custom callback if provided
        if self.on_wake_callback:
            try:
                self.on_wake_callback()
            except Exception:
                pass

        # 2. Check if a Jarvis terminal window is already running
        focused = False
        if shutil.which("wmctrl"):
            try:
                res = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2, env=env)
                if res.returncode == 0:
                    for line in res.stdout.strip().split("\n"):
                        if "jarvis" in line.lower():
                            parts = line.split()
                            if parts:
                                win_id = parts[0]
                                subprocess.run(["wmctrl", "-ia", win_id], timeout=2, env=env)
                                focused = True
                                break
            except Exception:
                pass

        # 3. If no existing window was focused, launch a new terminal running Jarvis
        if not focused:
            pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            python_bin = os.path.join(pkg_root, "venv", "bin", "python")
            if not os.path.exists(python_bin):
                python_bin = sys.executable

            cli_script = os.path.join(pkg_root, "cli.py")
            cmd_str = f"cd '{pkg_root}' && '{python_bin}' '{cli_script}'; exec bash"

            if shutil.which("gnome-terminal"):
                subprocess.Popen(
                    ["gnome-terminal", "--title=jarvis", "--", "bash", "-c", cmd_str],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            elif shutil.which("kitty"):
                subprocess.Popen(
                    ["kitty", "--title", "jarvis", "bash", "-c", cmd_str],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            elif shutil.which("x-terminal-emulator"):
                subprocess.Popen(
                    ["x-terminal-emulator", "-title", "jarvis", "-e", f"bash -c \"{cmd_str}\""],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

        # 4. Spoken greeting
        self.speak_greeting(f"Hello {first_name}, I am listening")

    def speak_greeting(self, message: str):
        """Speak brief confirmation in background thread."""
        def _speak():
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(message)
                engine.runAndWait()
            except Exception:
                if shutil.which("espeak"):
                    try:
                        subprocess.run(["espeak", message], timeout=3)
                    except Exception:
                        pass
        t = threading.Thread(target=_speak, daemon=True)
        t.start()

    def _listen_loop(self):
        """Continuous background audio stream and keyword detector."""
        record_cmd = self._find_audio_recorder()
        if not record_cmd:
            return

        chunk_seconds = 0.5
        bytes_per_sample = 2  # S16_LE (16-bit)
        chunk_bytes = int(self.sample_rate * chunk_seconds * bytes_per_sample)

        try:
            self._proc = subprocess.Popen(
                record_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=chunk_bytes * 4
            )
        except Exception:
            return

        speech_buffer = []
        is_speech_active = False
        silent_count = 0
        max_chunks = int(3.0 / chunk_seconds)  # Max ~3 seconds buffer

        while self._running and self._proc and self._proc.poll() is None:
            raw = self._proc.stdout.read(chunk_bytes)
            if not raw or len(raw) < chunk_bytes:
                time.sleep(0.05)
                continue

            # Convert to numpy int16 array
            samples = np.frombuffer(raw, dtype=np.int16)
            rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

            if rms >= self.energy_threshold:
                is_speech_active = True
                silent_count = 0
                speech_buffer.append(samples)
            elif is_speech_active:
                speech_buffer.append(samples)
                silent_count += 1

                # If silence for 0.8s or buffer reaches max, process phrase
                if silent_count >= 2 or len(speech_buffer) >= max_chunks:
                    full_audio = np.concatenate(speech_buffer)
                    speech_buffer = []
                    is_speech_active = False
                    silent_count = 0

                    # Process buffer for wake word
                    self._process_audio_chunk(full_audio)

        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def _process_audio_chunk(self, audio_data: np.ndarray):
        """Transcribe speech buffer and trigger on wake word match."""
        model = self._load_whisper_model()
        if not model:
            return

        # Normalize int16 to float32 between -1.0 and 1.0
        float_audio = audio_data.astype(np.float32) / 32768.0

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        try:
            if _HAS_SOUNDFILE:
                sf.write(wav_path, float_audio, self.sample_rate)
            else:
                import wave
                with wave.open(wav_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(audio_data.tobytes())

            # Fast Whisper transcription
            result = model.transcribe(wav_path, fp16=False, language="en")
            text = result.get("text", "").strip()

            if self.is_wake_phrase(text):
                self.trigger_wake()
        except Exception:
            pass
        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    def start(self):
        """Start wake word listener in a background daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="JarvisWakeWordListener")
            self._thread.start()

    def stop(self):
        """Stop background listener."""
        with self._lock:
            self._running = False
            if self._proc:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                self._proc = None
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.5)
                self._thread = None

    def is_alive(self) -> bool:
        return self._running and bool(self._thread and self._thread.is_alive())


if __name__ == "__main__":
    print("Jarvis Wake Word Listener running. Say 'Hello Jarvis' to open terminal...")
    listener = WakeWordListener()
    listener.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping listener...")
        listener.stop()
