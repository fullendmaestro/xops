#!/usr/bin/env python3  
"""  
Tashi Web Client Node - HTTP API gateway for XOPS marketplace  
Serves consensus state to web clients and accepts delivery requests  
"""  
  
import json  
import time  
import threading  
from typing import Dict, Any, List, Optional  
from datetime import datetime  
  
from flask import Flask, jsonify, request  
from flask_cors import CORS  
  
import config  
from tashi_manager import TashiNode  
from xops.locations import list_location_options, resolve_location
  
app = Flask(__name__)  
CORS(app)  # Enable CORS for web clients  
  
class TashiWebClient:  
    """  
    Web client node that connects to Tashi consensus network  
    and provides HTTP API for marketplace operations  
    """  
      
    def __init__(self, client_id: str = "WebClient"):  
        self.client_id = client_id  
        self.tashi = None  
        self.is_connected = False  
          
        # Marketplace state tracking  
        self.active_requests = {}  
        self.drone_states = {}  
        self.delivery_history = []  
        self.reputation_scores = {}  

        # Delivery award engine
        self._award_lock = threading.Lock()
        self._awarder_running = True
          
        # Initialize Tashi connection  
        self._init_tashi_connection()  
        threading.Thread(target=self._award_loop, daemon=True).start()
          
    def _init_tashi_connection(self):  
        """Initialize connection to Tashi P2P network"""  
        try:  
            # Use a unique port for the web client  
            web_client_port = 9700  
              
            # Get drone configuration to connect to the swarm  
            drone_config = config.DRONE_CONFIG  
            if not drone_config:  
                print("ERROR: No drone configuration found. Run generate_config.py first")  
                return  
                  
            # Use first drone's peer list to connect  
            first_drone = list(drone_config.values())[0]  
            peers = config.get_peers()  
              
            # Generate temporary keys for web client  
            import subprocess  
            import re  
              
            # Find key-generate binary  
            key_gen_path = self._find_key_generate()  
            if not key_gen_path:  
                print("ERROR: key-generate binary not found")  
                return  
                  
            # Generate keys for web client  
            result = subprocess.check_output([key_gen_path], text=True)  
            secret = re.search(r"Secret:\s+(\S+)", result).group(1)  
            public = re.search(r"Public:\s+(\S+)", result).group(1)  
              
            # Initialize Tashi node  
            self.tashi = TashiNode(  
                node_id=self.client_id,  
                bind_addr=f"127.0.0.1:{web_client_port}",  
                secret_key=secret,  
                peer_list=peers,  
                tools_dir=config.TASHI_TOOLS_DIR  
            )  
              
            self.tashi.on_message_callback = self._on_message_received  
            self.tashi.on_ready_callback = self._on_node_ready  
            self.tashi.start()  
              
            print(f"[{self.client_id}] Web client connecting to swarm...")  
              
        except Exception as e:  
            print(f"[{self.client_id}] Failed to initialize Tashi connection: {e}")  
              
    def _find_key_generate(self):  
        """Find the key-generate binary"""  
        import os  
        import platform  
          
        tools_dir = config.TASHI_TOOLS_DIR  
        is_windows = platform.system() == "Windows"  
        ext = ".exe" if is_windows else ""  
          
        # Try release first  
        release = os.path.join(tools_dir, "target", "release", f"key-generate{ext}")  
        if os.path.exists(release):  
            return release  
              
        # Try debug  
        debug = os.path.join(tools_dir, "target", "debug", f"key-generate{ext}")  
        if os.path.exists(debug):  
            return debug  
              
        return None  
          
    def _on_node_ready(self):  
        """Called when Tashi node is ready"""  
        self.is_connected = True  
        print(f"[{self.client_id}] Connected to Tashi swarm")  
          
    def _on_message_received(self, msg: str):  
        """Handle messages from Tashi consensus"""  
        try:  
            data = json.loads(msg)  
            message_type = data.get("type")  
              
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
            # Handle legacy non-JSON messages  
            if "Mission START" in msg:
                print(f"[{self.client_id}] Legacy message: {msg}")
        except Exception as e:  
            print(f"[{self.client_id}] Message processing error: {e}")  
              
    def _handle_delivery_request(self, data: Dict[str, Any]):  
        """Track new delivery requests"""  
        request_id = data["request_id"]  
        self.active_requests[request_id] = {  
            **data,  
            "status": "pending",  
            "bids": [],  
            "created_at": time.time()  
        }  
        print(f"[{self.client_id}] Tracking delivery request: {request_id}")  
          
    def _handle_delivery_bid(self, data: Dict[str, Any]):  
        """Track bids for delivery requests"""  
        request_id = data["request_id"]  
        if request_id in self.active_requests:  
            self.active_requests[request_id]["bids"].append(data)  
              
    def _handle_bid_awarded(self, data: Dict[str, Any]):  
        """Track bid awards"""  
        request_id = data["request_id"]  
        if request_id in self.active_requests:  
            self.active_requests[request_id]["status"] = "awarded"  
            self.active_requests[request_id]["awarded_drone"] = data["awarded_drone_id"]  
            self.active_requests[request_id]["final_price"] = data["final_price"]  

    def _award_loop(self):
        """Pick winning bids once each request reaches its bid deadline."""
        while self._awarder_running:
            time.sleep(0.5)
            now = time.time()

            with self._award_lock:
                for request_id, req in list(self.active_requests.items()):
                    if req.get("status") != "pending":
                        continue

                    deadline = req.get("bid_deadline", 0)
                    if now < deadline:
                        continue

                    bids = req.get("bids", [])
                    if not bids:
                        req["status"] = "no_bids"
                        continue

                    winning_bid = min(
                        bids,
                        key=lambda bid: (
                            bid.get("bid_price", float("inf")),
                            bid.get("eta_minutes", float("inf")),
                        ),
                    )

                    award_message = {
                        "type": "bid_awarded",
                        "request_id": request_id,
                        "awarded_drone_id": winning_bid["drone_id"],
                        "final_price": winning_bid["bid_price"],
                        "awarded_at": now,
                    }

                    if self.tashi and self.tashi.broadcast(json.dumps(award_message)):
                        req["status"] = "awarded"
                        req["awarded_drone"] = winning_bid["drone_id"]
                        req["final_price"] = winning_bid["bid_price"]
                        print(
                            f"[{self.client_id}] Awarded {request_id} to {winning_bid['drone_id']} "
                            f"for ${winning_bid['bid_price']}"
                        )
              
    def _handle_delivery_confirmation(self, data: Dict[str, Any]):  
        """Track delivery completions"""  
        request_id = data["request_id"]  
        if request_id in self.active_requests:  
            request = self.active_requests.pop(request_id)  
            request["status"] = data["status"]  
            request["completed_at"] = time.time()  
            self.delivery_history.append(request)  
              
    def _handle_reputation_update(self, data: Dict[str, Any]):  
        """Track reputation updates"""  
        drone_id = data["drone_id"]  
        self.reputation_scores[drone_id] = {  
            "last_update": time.time(),  
            "event_type": data["event_type"],  
            "impact": data["impact"]  
        }  
          
    def submit_delivery_request(self, request_data: Dict[str, Any]) -> bool:  
        """Submit a new delivery request to the swarm"""  
        if not self.is_connected or not self.tashi:  
            return False  
              
        # Add required fields if missing  
        if "request_id" not in request_data:  
            request_data["request_id"] = f"web_{int(time.time())}"  
              
        if "bid_deadline" not in request_data:  
            request_data["bid_deadline"] = time.time() + 300  # 5 minutes default  
              
        # Broadcast to swarm  
        message = json.dumps({  
            "type": "delivery_request",  
            **request_data  
        })  
          
        return self.tashi.broadcast(message)  
          
    def get_marketplace_state(self) -> Dict[str, Any]:  
        """Get current marketplace state"""  
        return {  
            "client_id": self.client_id,  
            "connected": self.is_connected,  
            "active_requests": self.active_requests,  
            "delivery_history": self.delivery_history[-10:],  # Last 10 deliveries  
            "reputation_scores": self.reputation_scores,  
            "drone_count": len(config.DRONE_CONFIG),  
            "timestamp": time.time()  
        }  
  
# Global web client instance  
web_client = TashiWebClient()  
  
# API Routes  
@app.route('/api/status', methods=['GET'])  
def get_status():  
    """Get web client and marketplace status"""  
    return jsonify(web_client.get_marketplace_state())  
  
@app.route('/api/requests', methods=['GET'])  
def get_requests():  
    """Get all active delivery requests"""  
    return jsonify({  
        "active_requests": web_client.active_requests,  
        "total_active": len(web_client.active_requests)  
    })  
  
@app.route('/api/requests/<request_id>', methods=['GET'])  
def get_request(request_id):  
    """Get specific delivery request"""  
    request = web_client.active_requests.get(request_id)  
    if not request:  
        return jsonify({"error": "Request not found"}), 404  
    return jsonify(request)  
  
@app.route('/api/requests', methods=['POST'])  
def create_request():  
    """Submit a new delivery request"""  
    data = request.get_json() or {}
      
    # Validate required fields  
    required_fields = ["customer_id", "package_weight"]
    missing = [field for field in required_fields if field not in data]
    if missing:  
        return jsonify({"error": f"Missing fields: {missing}"}), 400  

    payload = dict(data)
    try:
        if payload.get("pickup_id"):
            payload["pickup"] = resolve_location(payload["pickup_id"], "pickup")
        if payload.get("dropoff_id"):
            payload["dropoff"] = resolve_location(payload["dropoff_id"], "dropoff")
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 400

    if "pickup" not in payload or "dropoff" not in payload:
        return jsonify({"error": "Provide pickup/dropoff coordinates or pickup_id/dropoff_id"}), 400

    if not isinstance(payload.get("package_weight"), (int, float)) or payload["package_weight"] <= 0:
        return jsonify({"error": "package_weight must be a positive number"}), 400

    if "bid_deadline" not in payload:
        payload["bid_deadline"] = time.time() + 12
          
    # Submit to swarm  
    success = web_client.submit_delivery_request(payload)  
    if success:  
        return jsonify({  
            "message": "Delivery request submitted",  
            "request_id": payload.get("request_id")  
        }), 201  
    else:  
        return jsonify({"error": "Failed to submit request"}), 500  


@app.route('/api/locations', methods=['GET'])
def get_locations():
    """Get predefined pickup and dropoff options for the frontend."""
    return jsonify(list_location_options())
  
@app.route('/api/history', methods=['GET'])  
def get_history():  
    """Get delivery history"""  
    return jsonify({  
        "history": web_client.delivery_history,  
        "total_completed": len(web_client.delivery_history)  
    })  
  
@app.route('/api/drones', methods=['GET'])  
def get_drones():  
    """Get drone information"""  
    drone_info = {}  
    for name, cfg in config.DRONE_CONFIG.items():  
        drone_info[name] = {  
            "id": name,  
            "port": cfg["port"],  
            "capabilities": {  
                "max_payload": cfg.get("max_payload", 5.0),  
                "max_range": cfg.get("max_range", 10000),  
                "battery_capacity": cfg.get("battery_capacity", 5000),  
                "base_location": cfg.get("base_location", {"x": 0, "y": 0, "z": 0}),  
                "reputation": cfg.get("reputation", 100.0)  
            }  
        }  
    return jsonify(drone_info)  
  
@app.route('/api/reputation', methods=['GET'])  
def get_reputation():  
    """Get reputation scores"""  
    return jsonify(web_client.reputation_scores)  
  
if __name__ == "__main__":  
    print("Starting Tashi Web Client Node...")  
    print("API will be available at http://localhost:5000")  
    print("Endpoints:")  
    print("  GET  /api/status - Get marketplace status")  
    print("  GET  /api/requests - Get active requests")  
    print("  GET  /api/locations - Get predefined pickup/dropoff points")
    print("  POST /api/requests - Submit delivery request")  
    print("  GET  /api/history - Get delivery history")  
    print("  GET  /api/drones - Get drone information")  
    print("  GET  /api/reputation - Get reputation scores")  
      
    # Start Flask app  
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)