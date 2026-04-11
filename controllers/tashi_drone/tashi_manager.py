import subprocess
import threading
import json
import time
import os
import re
import platform
import glob as globmod

class TashiNode:
    """Manages a single Tashi Vertex Node for a Webots Drone"""
    def __init__(self, node_id, bind_addr, secret_key, peer_list, tools_dir):
        self.node_id = node_id
        self.bind_addr = bind_addr
        self.secret_key = secret_key
        self.peer_list = peer_list
        self.is_running = False
        self.is_windows = platform.system() == "Windows"

        # Resolve paths from tashi-tools directory
        abs_tools = os.path.abspath(tools_dir)
        self.use_wsl = False

        # Try release build first, then debug
        if self.is_windows:
            release_bin = os.path.join(abs_tools, "target", "release", "drone-comm.exe")
            debug_bin = os.path.join(abs_tools, "target", "debug", "drone-comm.exe")
        else:
            release_bin = os.path.join(abs_tools, "target", "release", "drone-comm")
            debug_bin = os.path.join(abs_tools, "target", "debug", "drone-comm")

        if os.path.exists(release_bin):
            self.bin_path = release_bin
            target_dir = os.path.join(abs_tools, "target", "release")
        elif os.path.exists(debug_bin):
            self.bin_path = debug_bin
            target_dir = os.path.join(abs_tools, "target", "debug")
        else:
            raise FileNotFoundError(f"drone-comm binary not found. Run ./setup.sh first.")

        # Find the library directory - prefer target/<profile>/lib, fallback to build output
        preferred_lib = os.path.join(target_dir, "lib")
        if os.path.isdir(preferred_lib):
            self.lib_path = preferred_lib
        else:
            lib_candidates = globmod.glob(os.path.join(target_dir, "build", "**/lib"), recursive=True)
            self.lib_path = lib_candidates[0] if lib_candidates else target_dir

        self.process = None
        self.on_message_callback = None
        self.on_ready_callback = None

    def start(self):
        peer_args = " ".join([f"-P {p}" for p in self.peer_list])

        # Set library path for dynamic linking
        env = os.environ.copy()
        if self.is_windows:
            env["PATH"] = f"{self.lib_path};{env.get('PATH', '')}"
        else:
            env["LD_LIBRARY_PATH"] = f"{self.lib_path}:{env.get('LD_LIBRARY_PATH', '')}"

        cmd = [self.bin_path, "-B", self.bind_addr, "-K", self.secret_key]
        for p in self.peer_list:
            cmd.extend(["-P", p])

        self.process = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.is_running = True
        threading.Thread(target=self._read_stdout, daemon=True).start()

    def _read_stdout(self):
        while self.is_running and self.process:
            line = self.process.stdout.readline()
            if not line: break
            line = line.strip()
            if not line: continue
            
            # Watch for Tashi Protocol messages or verified consensus
            if line.startswith("RX_TX:"):
                msg = line.replace("RX_TX:", "").strip().strip('\x00')
                if self.on_message_callback:
                    self.on_message_callback(msg)
            elif "DRONE_COMM_NODE_READY" in line:
                print(f"[{self.node_id}] Consensus Layer: READY")
                if self.on_ready_callback:
                    self.on_ready_callback()
            elif any(err in line for err in ["Error", "Panic", "failed", "socket"]):
                print(f"[{self.node_id}] NODE ERROR: {line}")

    def broadcast(self, message):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(message + "\n")
                self.process.stdin.flush()
                return True
            except Exception as e:
                print(f"[{self.node_id}] Failed to broadcast: {e}")
        return False

    def stop(self):
        self.is_running = False
        if self.process:
            try: 
                if self.is_windows:
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.process.pid)])
                else:
                    self.process.terminate()
            except: pass
            self.process = None
