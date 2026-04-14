import json  
import os  
  
# CONFIGURATION LOADER for Tashi Swarm with XOPS capabilities  
# This file loads the P2P keys, networking profile, and drone capabilities  
  
# Resolve paths relative to this script's directory  
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  
CONFIG_FILE = os.path.join(SCRIPT_DIR, "swarm_config.json")  
  
# --- CONFIGURATION ---  
# Path to tashi-tools (inside this repo)  
TASHI_TOOLS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "tashi-tools"))  
# ---------------------  
  
def load_config():  
    """Load configuration with backward compatibility for legacy configs"""  
    if not os.path.exists(CONFIG_FILE):  
        print(f"ERROR: {CONFIG_FILE} not found. Run 'utils/generate_config.py' first!")  
        return {}  
      
    with open(CONFIG_FILE, "r") as f:  
        config = json.load(f)  
      
    # Ensure backward compatibility by adding default capabilities if missing  
    for drone_name, drone_config in config.items():  
        if "max_payload" not in drone_config:  
            print(f"[{drone_name}] Adding default capabilities (legacy config detected)")  
            drone_config.update({  
                "max_payload": 5.0,  
                "max_range": 10000,  
                "battery_capacity": 5000,  
                "base_location": {"x": 0, "y": 0, "z": 0},  
                "reputation": 100.0  
            })  
      
    return config  
  
DRONE_CONFIG = load_config()  
  
def get_peers():  
    """Returns a list of public_key@ip:port for all peers in the swarm"""  
    return [f"{cfg['public']}@127.0.0.1:{cfg['port']}" for cfg in DRONE_CONFIG.values()]  
  
def get_drone_capabilities(drone_name: str) -> dict:  
    """Get XOPS capabilities for a specific drone"""  
    if drone_name not in DRONE_CONFIG:  
        return {}  
      
    return {  
        "max_payload": DRONE_CONFIG[drone_name].get("max_payload", 5.0),  
        "max_range": DRONE_CONFIG[drone_name].get("max_range", 10000),  
        "battery_capacity": DRONE_CONFIG[drone_name].get("battery_capacity", 5000),  
        "base_location": DRONE_CONFIG[drone_name].get("base_location", {"x": 0, "y": 0, "z": 0}),  
        "reputation": DRONE_CONFIG[drone_name].get("reputation", 100.0)  
    }  
  
def validate_config():  
    """Validate that all required fields are present"""  
    required_fields = ["port", "secret", "public", "max_payload", "max_range", "battery_capacity"]  
      
    for drone_name, config in DRONE_CONFIG.items():  
        missing_fields = [field for field in required_fields if field not in config]  
        if missing_fields:  
            print(f"WARNING: {drone_name} missing fields: {missing_fields}")  
            return False  
      
    print("✅ Configuration validation passed")  
    return True  
  
# Validate configuration on load  
validate_config()