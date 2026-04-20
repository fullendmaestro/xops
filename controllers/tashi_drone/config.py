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

DEFAULT_DRONE_CAPABILITIES = {
    "max_payload": 5.0,
    "max_range": 10000,
    "battery_capacity": 5000,
    "base_location": {"x": 0, "y": 0, "z": 0},
    "reputation": 100.0,
}
  
def load_config():  
    """Load configuration with backward compatibility for legacy configs"""  
    if not os.path.exists(CONFIG_FILE):  
        print(f"ERROR: {CONFIG_FILE} not found. Run 'utils/generate_config.py' first!")  
        return {}  
      
    with open(CONFIG_FILE, "r") as f:  
        config = json.load(f)  
      
    # Ensure backward compatibility by adding role/capabilities to drone entries.
    for node_name, node_config in config.items():
        node_role = node_config.get("role")
        if not node_role:
            node_role = "drone" if node_name.lower().startswith("drone") else "service"
            node_config["role"] = node_role

        if node_role == "drone" and "max_payload" not in node_config:
            print(f"[{node_name}] Adding default capabilities (legacy config detected)")
            node_config.update(DEFAULT_DRONE_CAPABILITIES)
      
    return config  
  
DRONE_CONFIG = load_config()  
  
def get_node_config(node_name: str) -> dict:
    """Return node identity config by exact node name."""
    return DRONE_CONFIG.get(node_name, {})


def get_peers(exclude_node: str = ""):
    """Return public_key@ip:port list for all nodes, optionally excluding one."""
    peers = []
    for node_name, cfg in DRONE_CONFIG.items():
        if exclude_node and node_name == exclude_node:
            continue
        peers.append(f"{cfg['public']}@127.0.0.1:{cfg['port']}")
    return peers
  
def get_drone_capabilities(drone_name: str) -> dict:  
    """Get XOPS capabilities for a specific drone"""  
    if drone_name not in DRONE_CONFIG:  
        return {}  
      
    return {  
        "max_payload": DRONE_CONFIG[drone_name].get("max_payload", DEFAULT_DRONE_CAPABILITIES["max_payload"]),  
        "max_range": DRONE_CONFIG[drone_name].get("max_range", DEFAULT_DRONE_CAPABILITIES["max_range"]),  
        "battery_capacity": DRONE_CONFIG[drone_name].get("battery_capacity", DEFAULT_DRONE_CAPABILITIES["battery_capacity"]),  
        "base_location": DRONE_CONFIG[drone_name].get("base_location", DEFAULT_DRONE_CAPABILITIES["base_location"]),  
        "reputation": DRONE_CONFIG[drone_name].get("reputation", DEFAULT_DRONE_CAPABILITIES["reputation"]),  
    }  
  
def validate_config():  
    """Validate that all required fields are present"""  
    required_fields = ["port", "secret", "public"]
    drone_required_fields = ["max_payload", "max_range", "battery_capacity"]
      
    for node_name, node_cfg in DRONE_CONFIG.items():
        missing_fields = [field for field in required_fields if field not in node_cfg]
        node_role = node_cfg.get("role", "drone" if node_name.lower().startswith("drone") else "service")
        if node_role == "drone":
            missing_fields.extend([field for field in drone_required_fields if field not in node_cfg])
        if missing_fields:  
            print(f"WARNING: {node_name} missing fields: {missing_fields}")
            return False  
      
    print("✅ Configuration validation passed")  
    return True  
  
# Validate configuration on load  
validate_config()