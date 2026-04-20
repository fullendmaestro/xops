import subprocess  
import re  
import json  
import os  
import platform  
import glob  
  
# --- CONFIGURATION ---
NODE_SPECS = [
    {"name": "Drone1", "port": 9600, "role": "drone"},
    {"name": "Drone2", "port": 9601, "role": "drone"},
    {"name": "XopsSupervisor", "port": 9602, "role": "service"},
    {"name": "TashiServer", "port": 9605, "role": "service"},
]
  
# XOPS Drone Capabilities Configuration  
DRONE_CAPABILITIES = {
    "Drone1": {
        "max_payload": 5.0,        # kg
        "max_range": 10000,        # meters
        "battery_capacity": 5000,  # mAh
        "base_location": {"x": 0.0, "y": 0.0, "z": 0.15},
        "reputation": 100.0,
    },
    "Drone2": {
        "max_payload": 3.0,        # kg (smaller drone)
        "max_range": 8000,         # meters
        "battery_capacity": 4000,  # mAh
        "base_location": {"x": 2.6, "y": -1.7, "z": 0.15},
        "reputation": 95.0,
    },
}
  
# Resolve paths relative to this script  
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  
TOOLS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "tashi-tools"))  
  
# Target output (inside the controller folder)  
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "..", "controllers", "tashi_drone", "swarm_config.json")  
  
def find_binary(name):
    """Find binary in release or debug build"""
    is_windows = platform.system() == "Windows"
    ext = ".exe" if is_windows else ""

    release = os.path.join(TOOLS_DIR, "target", "release", f"{name}{ext}")
    debug = os.path.join(TOOLS_DIR, "target", "debug", f"{name}{ext}")

    if os.path.exists(release):
        return release, os.path.dirname(release)
    elif os.path.exists(debug):
        return debug, os.path.dirname(debug)
    return None, None

def find_lib_path(target_dir):
    """Find library directory - prefer target/<profile>/lib"""
    preferred = os.path.join(target_dir, "lib")
    if os.path.isdir(preferred):
        return preferred
    lib_dirs = glob.glob(os.path.join(target_dir, "build", "**/lib"), recursive=True)
    return lib_dirs[0] if lib_dirs else target_dir

def generate_swarm_config():  
    print("--- TASHI SWARM CONFIG GENERATOR (XOPS Enhanced) ---")  
  
    key_gen_path, target_dir = find_binary("key-generate")  
    if not key_gen_path:  
        print("ERROR: key-generate not found. Run ./setup.sh first!")  
        return  
  
    lib_path = find_lib_path(target_dir)  
    is_windows = platform.system() == "Windows"  
  
    # Set up environment  
    env = os.environ.copy()  
    if is_windows:  
        env["PATH"] = f"{lib_path};{env.get('PATH', '')}"  
    else:  
        env["LD_LIBRARY_PATH"] = f"{lib_path}:{env.get('LD_LIBRARY_PATH', '')}"  
  
    swarm_data = {}  
  
    for node in NODE_SPECS:
        name = node["name"]
        role = node["role"]
        port = node["port"]
        print(f"Generating keys for {name} ({role})...")
        try:  
            res = subprocess.check_output([key_gen_path], env=env, text=True)  
            sec = re.search(r"Secret:\s+(\S+)", res).group(1)  
            pub = re.search(r"Public:\s+(\S+)", res).group(1)  

            node_entry = {
                "role": role,
                "port": port,
                "secret": sec,
                "public": pub,
            }
            if role == "drone":
                capabilities = DRONE_CAPABILITIES.get(
                    name,
                    {
                        "max_payload": 5.0,
                        "max_range": 10000,
                        "battery_capacity": 5000,
                        "base_location": {"x": 0, "y": 0, "z": 0},
                        "reputation": 100.0,
                    },
                )
                node_entry.update(capabilities)

            swarm_data[name] = node_entry
        except Exception as e:  
            print(f"FAILED to generate keys for {name}: {e}")  
            return  
  
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)  
    with open(OUTPUT_FILE, "w") as f:  
        json.dump(swarm_data, f, indent=4)  
  
    print(f"\nSUCCESS: XOPS Config written to {OUTPUT_FILE}")  
    print("Included drone capabilities plus service node identities")
  
if __name__ == "__main__":  
    generate_swarm_config()