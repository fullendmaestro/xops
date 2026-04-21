#!/usr/bin/env python3
"""
Tashi Server Node - Gateway for web requests to the XOPS swarm

This controller runs in Webots and serves as the centralized relay point for:
1. Web client HTTP requests -> Tashi swarm broadcast
2. Tashi swarm messages -> tracking and coordination
3. Marketplace state management

Uses built-in Python HTTP server (no Flask dependency for Windows compatibility)
"""

import os
import sys
import json
import time
import threading
from typing import Dict, Any, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from queue import Queue

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Webots imports
from controller import Robot

# Tashi and XOPS imports
try:
    from tashi_drone.tashi_manager import TashiNode
    from tashi_drone import config
    from tashi_drone.xops.locations import list_location_options, resolve_location
except ImportError as e:
    print(f"[TashiServer] Import error: {e}")
    raise

# Persistence file for delivery history — survives Webots restarts.
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "delivery_history.json")


def _load_history() -> List[Dict[str, Any]]:
    """Load persisted delivery history from disk."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(history: List[Dict[str, Any]]):
    """Persist delivery history to disk."""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history[-500:], f)  # Keep last 500 entries
    except Exception as exc:
        print(f"[TashiServer] Failed to save history: {exc}")


class TashiServerNode:
    """
    Central server node that connects to Tashi and relays web requests to the swarm.
    This is a non-participating observer that facilitates marketplace coordination.
    """
    
    def __init__(self):
        self.robot = Robot()
        self.name = self.robot.getName()
        self.timestep = int(self.robot.getBasicTimeStep())
        
        print(f"[{self.name}] Initializing Tashi Server Node...")
        
        # Server state
        self.is_connected = False
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        self.delivery_history: List[Dict[str, Any]] = _load_history()
        self.reputation_scores: Dict[str, Dict[str, Any]] = {}

        # Initialize drone_states from config so fleet is visible even before any message.
        self.drone_states: Dict[str, Dict[str, Any]] = {}
        for node_name, node_cfg in config.DRONE_CONFIG.items():
            if node_cfg.get("role", "drone") == "drone":
                self.drone_states[node_name] = {
                    "id": node_name,
                    "status": "idle",
                    "current_request": None,
                    "capabilities": {
                        "max_payload": node_cfg.get("max_payload", 5.0),
                        "max_range": node_cfg.get("max_range", 10000),
                        "battery_capacity": node_cfg.get("battery_capacity", 5000),
                        "base_location": node_cfg.get("base_location", {"x": 0, "y": 0, "z": 0}),
                        "reputation": node_cfg.get("reputation", 100.0),
                    },
                    "reputation": node_cfg.get("reputation", 100.0),
                    "last_seen": time.time(),
                }

        # Broadcast queue for thread-safe message delivery from HTTP handler
        self.broadcast_queue: Queue = Queue()
        
        # Message locks for thread safety
        self._state_lock = threading.Lock()
        
        # Tashi node (initialized in run())
        self.tashi = None
        
    def _init_tashi_connection(self):
        """Initialize connection to Tashi P2P network as non-voting observer"""
        try:
            node_cfg = config.get_node_config(self.name)
            if not node_cfg:
                raise ValueError(
                    "Missing identity in swarm_config.json for TashiServer"
                )

            # Allow env override for deployments while defaulting to generated config.
            server_secret = os.getenv("TASHI_SERVER_SECRET", node_cfg["secret"])
            peers = config.get_peers(exclude_node=self.name)
            
            print(f"[{self.name}] Discovered peers: {peers}")
            
            # Initialize Tashi node — server is a non-voting observer.
            self.tashi = TashiNode(
                node_id=self.name,
                bind_addr=f"127.0.0.1:{node_cfg['port']}",
                secret_key=server_secret,
                peer_list=peers,
                tools_dir=config.TASHI_TOOLS_DIR,
            )
            
            self.tashi.on_message_callback = self._on_message_received
            self.tashi.on_ready_callback = self._on_node_ready
            self.tashi.start()
            
            print(f"[{self.name}] Tashi node started, waiting for swarm connection...")
            
        except Exception as e:
            print(f"[{self.name}] Failed to initialize Tashi: {e}")
    
    def _on_node_ready(self):
        """Called when Tashi node is ready"""
        self.is_connected = True
        print(f"[{self.name}] Connected to Tashi swarm")
    
    def _on_message_received(self, msg: str):
        """Handle messages from the Tashi swarm"""
        try:
            data = json.loads(msg)
            message_type = data.get("type")
            
            with self._state_lock:
                if message_type == "delivery_request":
                    self._handle_delivery_request(data)
                elif message_type == "delivery_bid":
                    self._handle_delivery_bid(data)
                elif message_type == "bid_awarded":
                    self._handle_bid_awarded(data)
                elif message_type == "delivery_confirmation":
                    self._handle_delivery_confirmation(data)
                elif message_type == "reputation_update":
                    self._handle_reputation_update(data)
                    
        except json.JSONDecodeError:
            if "Mission START" in msg:
                print(f"[{self.name}] Supervisor event: {msg}")
        except Exception as e:
            print(f"[{self.name}] Message processing error: {e}")
    
    def _handle_delivery_request(self, data: Dict[str, Any]):
        """Track delivery request from swarm"""
        request_id = data.get("request_id")
        if not request_id:
            return
            
        self.active_requests[request_id] = {
            **data,
            "status": "pending",
            "bids": [],
            "tracked_at": time.time()
        }
        print(f"[{self.name}] Tracking request: {request_id}")
    
    def _handle_delivery_bid(self, data: Dict[str, Any]):
        """Track bids from drones"""
        request_id = data.get("request_id")
        drone_id = data.get("drone_id")
        if request_id in self.active_requests:
            self.active_requests[request_id]["bids"].append(data)
            print(f"[{self.name}] Bid received for {request_id} from {drone_id}")
    
    def _handle_bid_awarded(self, data: Dict[str, Any]):
        """Track bid awards and update drone state"""
        request_id = data.get("request_id")
        awarded_drone = data.get("awarded_drone_id")
        if request_id in self.active_requests:
            self.active_requests[request_id]["status"] = "awarded"
            self.active_requests[request_id]["awarded_drone"] = awarded_drone
            self.active_requests[request_id]["final_price"] = data.get("final_price")
            print(f"[{self.name}] Bid awarded for {request_id} to {awarded_drone}")

        # Mark the winning drone as busy
        if awarded_drone and awarded_drone in self.drone_states:
            self.drone_states[awarded_drone]["status"] = "busy"
            self.drone_states[awarded_drone]["current_request"] = request_id
            self.drone_states[awarded_drone]["last_seen"] = time.time()
    
    def _handle_delivery_confirmation(self, data: Dict[str, Any]):
        """Track delivery completions and restore drone to idle"""
        request_id = data.get("request_id")
        drone_id = data.get("drone_id")
        if request_id in self.active_requests:
            request = self.active_requests.pop(request_id)
            request["status"] = "completed"
            request["completed_at"] = time.time()
            self.delivery_history.append(request)
            _save_history(self.delivery_history)
            print(f"[{self.name}] Delivery completed: {request_id}")

        # Restore drone to idle
        if drone_id and drone_id in self.drone_states:
            self.drone_states[drone_id]["status"] = "idle"
            self.drone_states[drone_id]["current_request"] = None
            self.drone_states[drone_id]["last_seen"] = time.time()
    
    def _handle_reputation_update(self, data: Dict[str, Any]):
        """Track reputation updates"""
        drone_id = data.get("drone_id")
        if drone_id:
            self.reputation_scores[drone_id] = {
                "last_update": time.time(),
                "event_type": data.get("event_type"),
                "impact": data.get("impact")
            }
            # Also reflect in drone_states
            if drone_id in self.drone_states:
                self.drone_states[drone_id]["reputation"] = data.get("new_score", self.drone_states[drone_id].get("reputation", 100.0))
    
    def broadcast_delivery_request(self, request_data: Dict[str, Any]) -> bool:
        """Queue a delivery request for broadcasting to the swarm"""
        if "request_id" not in request_data:
            request_data["request_id"] = f"req_{int(time.time() * 1000)}"
        
        if "bid_deadline" not in request_data:
            # 5 minutes — consistent with the HTTP handler deadline.
            request_data["bid_deadline"] = time.time() + 300
        
        if "pickup" not in request_data or "dropoff" not in request_data:
            print(f"[{self.name}] Missing pickup/dropoff locations")
            return False
        
        message = {
            "type": "delivery_request",
            **request_data
        }
        
        self.broadcast_queue.put(message)
        print(f"[{self.name}] Queued delivery request: {request_data.get('request_id')}")
        return True
    
    def get_marketplace_state(self) -> Dict[str, Any]:
        """Get current marketplace state"""
        with self._state_lock:
            return {
                "server_id": self.name,
                "connected": self.is_connected,
                "active_requests": self.active_requests,
                "delivery_history": self.delivery_history[-20:],
                "reputation_scores": self.reputation_scores,
                "drone_states": self.drone_states,
                "total_deliveries": len(self.delivery_history),
                "timestamp": time.time()
            }
    
    def run(self):
        """Main control loop — initialize Tashi and process broadcasts each timestep"""
        self._init_tashi_connection()
        
        # Wait for Tashi to be ready
        count = 0
        max_wait = 300  # ~3 seconds at 100 steps/sec
        while not self.is_connected and count < max_wait:
            self.robot.step(self.timestep)
            count += 1
            if count % 50 == 0:
                print(f"[{self.name}] Waiting for Tashi connection... ({count}/{max_wait})")
        
        if not self.is_connected:
            print(f"[{self.name}] WARNING: Tashi connection not established")
        
        print(f"[{self.name}] Server running...")
        
        # Main control loop
        while self.robot.step(self.timestep) != -1:
            if not self.broadcast_queue.empty():
                try:
                    message = self.broadcast_queue.get_nowait()
                    if self.tashi and self.is_connected:
                        self.tashi.broadcast(json.dumps(message))
                        print(f"[{self.name}] Broadcast delivery request: {message.get('request_id')}")
                    else:
                        print(f"[{self.name}] Not connected to swarm, dropped message")
                except Exception as e:
                    print(f"[{self.name}] Failed to process broadcast queue: {e}")


# Custom HTTP Request Handler
class TashiServerHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Tashi Server API"""
    
    server_instance: Optional['TashiServerNode'] = None
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
        try:
            if path == '/api/status':
                self._send_json(self.server_instance.get_marketplace_state())
            elif path == '/api/requests':
                with self.server_instance._state_lock:
                    response = {
                        "active_requests": self.server_instance.active_requests,
                        "total_active": len(self.server_instance.active_requests)
                    }
                self._send_json(response)
            elif path == '/api/drones':
                with self.server_instance._state_lock:
                    self._send_json(list(self.server_instance.drone_states.values()))
            elif path.startswith('/api/requests/'):
                request_id = path.split('/')[-1]
                with self.server_instance._state_lock:
                    request_obj = self.server_instance.active_requests.get(request_id)
                    if not request_obj:
                        self._send_json({"error": "Request not found"}, 404)
                    else:
                        self._send_json(request_obj)
            elif path == '/api/locations':
                self._send_json(list_location_options())
            elif path == '/api/history':
                with self.server_instance._state_lock:
                    # Support pagination via ?page=N&limit=M
                    limit = int(query.get("limit", ["20"])[0])
                    page = int(query.get("page", ["1"])[0])
                    history = self.server_instance.delivery_history
                    total = len(history)
                    start = (page - 1) * limit
                    end = start + limit
                    response = {
                        "history": list(reversed(history))[start:end],
                        "total_completed": total,
                        "page": page,
                        "limit": limit,
                        "total_pages": max(1, (total + limit - 1) // limit),
                    }
                self._send_json(response)
            elif path == '/api/reputation':
                with self.server_instance._state_lock:
                    self._send_json(self.server_instance.reputation_scores)
            elif path == '/health':
                status = self.server_instance.get_marketplace_state()
                if "error" in status:
                    self._send_json({"status": "unhealthy", "reason": "Server unavailable"}, 503)
                else:
                    self._send_json({"status": "healthy", "server": status.get("server_id")})
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            print(f"[TashiServer] GET error: {e}")
            self._send_json({"error": str(e)}, 500)
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[TashiServer] POST body parse error: {e}")
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        
        try:
            if path == '/api/requests':
                result = self._handle_create_request(data)
                status = 201 if result.get("success") else (400 if "Missing" in result.get("error", "") else 500)
                self._send_json(result, status)
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            print(f"[TashiServer] POST error: {e}")
            self._send_json({"error": str(e)}, 500)
    
    def _handle_create_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delivery request submission"""
        required_fields = ["customer_id", "package_weight"]
        missing = [field for field in required_fields if field not in data]
        if missing:
            return {"error": f"Missing fields: {missing}"}
        
        try:
            payload = dict(data)
            if "pickup" in payload and isinstance(payload["pickup"], str):
                payload["pickup"] = resolve_location(payload["pickup"], "pickup")
            if "dropoff" in payload and isinstance(payload["dropoff"], str):
                payload["dropoff"] = resolve_location(payload["dropoff"], "dropoff")
        except KeyError as exc:
            return {"error": f"Invalid location: {exc}"}
        
        if "pickup" not in payload or "dropoff" not in payload:
            return {"error": "Must specify pickup and dropoff locations"}
        
        if not isinstance(payload.get("package_weight"), (int, float)) or payload["package_weight"] <= 0:
            return {"error": "package_weight must be positive"}
        
        if "bid_deadline" not in payload:
            payload["bid_deadline"] = time.time() + 300

        success = self.server_instance.broadcast_delivery_request(payload)
        if success:
            return {
                "success": True,
                "request_id": payload.get("request_id"),
                "message": "Request broadcasted to swarm"
            }
        else:
            return {"error": "Failed to broadcast request"}
    
    def _send_json(self, data, status: int = 200):
        """Send JSON response"""
        response_body = json.dumps(data).encode('utf-8')
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', len(response_body))
        self.end_headers()
        
        self.wfile.write(response_body)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


if __name__ == "__main__":
    server = TashiServerNode()
    
    TashiServerHTTPHandler.server_instance = server
    
    http_server = HTTPServer(('0.0.0.0', 5000), TashiServerHTTPHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    
    print("[TashiServer] HTTP API started at http://0.0.0.0:5000")
    print("[TashiServer] Available endpoints:")
    print("  GET  /api/status     - Get marketplace status")
    print("  GET  /api/requests   - Get active requests")
    print("  GET  /api/drones     - Get tracked drone states (all 4 drones)")
    print("  GET  /api/locations  - Get predefined locations")
    print("  POST /api/requests   - Submit delivery request")
    print("  GET  /api/history    - Get delivery history (persisted)")
    print("  GET  /api/reputation - Get reputation scores")
    print("  GET  /health         - Health check")
    
    server.run()
