from controller import Robot  
import json  
import time  
import os  
import sys  
from enum import Enum  
from typing import Dict, Any, Optional  
  
# Ensure local modules can be found  
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  
  
try:  
    from tashi_manager import TashiNode  
    import config  
    from xops.delivery_state import DeliveryStateMachine, DeliveryRequest, DeliveryState  
    from xops.marketplace_manager import MarketplaceManager  
    from xops.reputation_system import ReputationEventType
except ImportError as e:  
    print(f"IMPORT ERROR: {e}. Check if required modules are in this folder.")  
    raise
  
# XOPS Message Types  
class MessageType(Enum):  
    DELIVERY_REQUEST = "delivery_request"  
    DELIVERY_BID = "delivery_bid"  
    BID_AWARDED = "bid_awarded"  
    DELIVERY_CONFIRMATION = "delivery_confirmation"  
    MISSION_START = "mission_start"  
  
class TashiDroneController:  
    """  
    Main Webots Controller for Decentralized Tashi Swarm with XOPS Marketplace.  
    Each instance of this script manages its own Tashi Node for peer-to-peer consensus.  
    """  
    def __init__(self):  
        self.robot = Robot()  
        self.name = self.robot.getName()  
        self.timestep = int(self.robot.getBasicTimeStep())  
          
        print(f"[{self.name}] Initializing Distributed Consensus Brain...")  
          
        # Load configuration  
        if self.name not in config.DRONE_CONFIG:  
            print(f"[{self.name}] CRITICAL: Identity mismatch. Check 'name' field in Webots and 'swarm_config.json'.")  
            return  
  
        cfg = config.DRONE_CONFIG[self.name]  
        peers = config.get_peers()  
          
        # Initialize Tashi P2P node  
        self.tashi = TashiNode(  
            node_id=self.name,  
            bind_addr=f"127.0.0.1:{cfg['port']}",  
            secret_key=cfg['secret'],  
            peer_list=peers,  
            tools_dir=config.TASHI_TOOLS_DIR  
        )  
        self.tashi.on_message_callback = self.on_message_received  
        self.tashi.start()  
          
        self.handshake_verified = False  
          
        # XOPS Components Integration  
        self.state_machine = DeliveryStateMachine(self.name)  
        self.marketplace = MarketplaceManager(  
            self.name,   
            self.tashi,   
            config.get_drone_capabilities(self.name)  
        )  
          
        # Navigation and delivery state  
        self.target_location = None  
        self.delivery_package = None  
  
    def validate_message_schema(self, data: Dict[str, Any], message_type: str) -> bool:  
        """Validate incoming message schema"""  
        try:  
            if message_type == MessageType.DELIVERY_REQUEST.value:  
                required_fields = ["request_id", "customer_id", "pickup", "dropoff", "package_weight", "bid_deadline"]  
                return all(field in data for field in required_fields)  
            elif message_type == MessageType.DELIVERY_BID.value:  
                required_fields = ["drone_id", "request_id", "bid_price", "eta_minutes"]  
                return all(field in data for field in required_fields)  
            elif message_type == MessageType.BID_AWARDED.value:  
                required_fields = ["request_id", "awarded_drone_id", "final_price"]  
                return all(field in data for field in required_fields)  
            elif message_type == MessageType.DELIVERY_CONFIRMATION.value:  
                required_fields = ["request_id", "drone_id", "status", "timestamp"]  
                return all(field in data for field in required_fields)  
            return False  
        except Exception:  
            return False  
  
    def handle_delivery_request(self, data: Dict[str, Any]):  
        """Handle incoming delivery request from customer"""  
        request_id = data["request_id"]  
        print(f"[{self.name}] 📦 Received delivery request: {request_id}")  
          
        # Use marketplace manager to handle the request  
        if self.marketplace.handle_delivery_request(data):  
            # Successfully submitted bid, transition to BIDDING state  
            if request_id in self.marketplace.active_requests:  
                delivery_request = self.marketplace.active_requests[request_id]  
                self.state_machine.transition_to(DeliveryState.BIDDING, {"delivery": delivery_request})  
  
    def handle_delivery_bid(self, data: Dict[str, Any]):  
        """Handle delivery bid from another drone"""  
        drone_id = data["drone_id"]  
        request_id = data["request_id"]  
        bid_price = data["bid_price"]  
          
        print(f"[{self.name}] 💰 Received bid from {drone_id} for {request_id}: ${bid_price}")  
          
        # Store bid for potential awarding logic  
        if request_id in self.marketplace.active_requests:  
            self.marketplace.active_requests[request_id].bids.append(data)  
  
    def handle_bid_awarded(self, data: Dict[str, Any]):  
        """Handle bid award notification"""  
        request_id = data["request_id"]  
        awarded_drone_id = data["awarded_drone_id"]  
          
        if awarded_drone_id == self.name:  
            print(f"[{self.name}] 🎉 WON BID for {request_id}! Price: ${data['final_price']}")  
            # Transition to ASSIGNED state  
            if request_id in self.marketplace.active_requests:  
                delivery_request = self.marketplace.active_requests[request_id]  
                self.state_machine.transition_to(DeliveryState.ASSIGNED, {"delivery": delivery_request})  
                self.target_location = delivery_request.pickup  
        else:  
            print(f"[{self.name}] ❌ Lost bid for {request_id} to {awarded_drone_id}")  
            # Return to IDLE state  
            self.state_machine.transition_to(DeliveryState.IDLE)  
  
    def handle_delivery_confirmation(self, data: Dict[str, Any]):  
        """Handle delivery completion confirmation"""  
        request_id = data["request_id"]  
        drone_id = data["drone_id"]  
        status = data["status"]  
          
        print(f"[{self.name}] ✅ Delivery {request_id} by {drone_id}: {status}")  
          
        # Update marketplace and reputation  
        self.marketplace.handle_delivery_confirmation(data)  
          
        # If this was our delivery, transition to RETURNING  
        if drone_id == self.name and status == "completed":  
            self.state_machine.transition_to(DeliveryState.RETURNING)  
            self.target_location = config.get_drone_capabilities(self.name)["base_location"]  
  
    def on_message_received(self, msg):  
        """Extended callback for XOPS marketplace messages"""  
        try:  
            data = json.loads(msg)  
            message_type = data.get("type")  
              
            if not message_type:  
                # Handle legacy mission messages  
                if "text" in data and "Mission START" in data['text']:  
                    print(f"[{self.name}] ✅ VERIFIED CONSENSUS: {data['text']}")  
                    self.handshake_verified = True  
                return  
              
            # Validate message schema  
            if not self.validate_message_schema(data, message_type):  
                print(f"[{self.name}] ❌ Invalid message schema for type: {message_type}")  
                return  
              
            print(f"[{self.name}] ✅ VERIFIED CONSENSUS: {message_type}")  
              
            # Route to appropriate handler  
            if message_type == MessageType.DELIVERY_REQUEST.value:  
                self.handle_delivery_request(data)  
            elif message_type == MessageType.DELIVERY_BID.value:  
                self.handle_delivery_bid(data)  
            elif message_type == MessageType.BID_AWARDED.value:  
                self.handle_bid_awarded(data)  
            elif message_type == MessageType.DELIVERY_CONFIRMATION.value:  
                self.handle_delivery_confirmation(data)  
            elif message_type == "reputation_update":  
                self.marketplace.reputation_system.handle_reputation_update(data)             
            else:  
                print(f"[{self.name}] ⚠️ Unknown message type: {message_type}")  
                  
        except json.JSONDecodeError as e:  
            print(f"[{self.name}] ❌ JSON decode error: {e}")  
        except Exception as e:  
            print(f"[{self.name}] ❌ Message processing error: {e}")  
  
    def get_current_position(self):  
        """Get current drone position from Webots"""  
        gps = self.robot.getDevice("gps")  
        if gps:  
            gps.enable(self.timestep)  
            return {  
                "x": gps.getValues()[0],  
                "y": gps.getValues()[1],   
                "z": gps.getValues()[2]  
            }  
        return {"x": 0, "y": 0, "z": 0}  
  
    def calculate_distance_to_target(self):  
        """Calculate distance to current target location"""  
        if not self.target_location:  
            return float('inf')  
              
        current_pos = self.get_current_position()  
        dx = self.target_location["x"] - current_pos["x"]  
        dy = self.target_location["y"] - current_pos["y"]  
        dz = self.target_location["z"] - current_pos["z"]  
        return (dx*dx + dy*dy + dz*dz) ** 0.5  
  
    def navigate_to_target(self):  
        """Simple navigation logic - move towards target location"""  
        if not self.target_location:  
            return False  
              
        current_pos = self.get_current_position()  
        distance = self.calculate_distance_to_target()  
          
        if distance < 0.5:  # Within 0.5 meters of target  
            return True  
              
        # Simple proportional navigation  
        motors = []  
        for i in range(4):  
            motor = self.robot.getDevice(f"motor{i+1}")  
            if motor:  
                motors.append(motor)  
                  
        if len(motors) >= 4:  
            # Calculate direction vector  
            dx = self.target_location["x"] - current_pos["x"]  
            dy = self.target_location["y"] - current_pos["y"]  
              
            # Simple forward movement (in real implementation, would use proper drone control)  
            base_speed = 2.0  
            for motor in motors:  
                motor.setPosition(float('inf'))  
                motor.setVelocity(base_speed)  
                  
        return False  
  
    def execute_pickup(self):  
        """Execute package pickup at current location"""  
        print(f"[{self.name}] 📤 Executing package pickup...")  
        # Simulate pickup time  
        time.sleep(2)  
        self.delivery_package = {"picked_up_at": time.time()}  
        print(f"[{self.name}] ✅ Package picked up successfully")  
  

    def execute_dropoff(self):  
        """Execute package dropoff at current location"""  
        print(f"[{self.name}] 📥 Executing package dropoff...")  
        
        # Calculate delivery performance  
        if self.state_machine.current_delivery:  
            delivery = self.state_machine.current_delivery  
            delivered_early = time.time() < delivery.bid_deadline  
            
            # Add reputation event  
            self.marketplace.reputation_system.add_reputation_event(  
                ReputationEventType.DELIVERY_COMPLETED,  
                delivery.request_id,  
                {"delivered_early": delivered_early}  
            )  
        
        # Simulate dropoff time  
        time.sleep(2)  
        
        # Send delivery confirmation  
        if self.state_machine.current_delivery:  
            confirmation = {  
                "type": "delivery_confirmation",  
                "request_id": self.state_machine.current_delivery.request_id,  
                "drone_id": self.name,  
                "status": "completed",  
                "timestamp": time.time()  
            }  
            self.tashi.broadcast(json.dumps(confirmation))  
            
        self.delivery_package = None  
        print(f"[{self.name}] ✅ Package delivered successfully")

  
    def run(self):  
        """Main control loop with XOPS delivery state machine"""  
        count = 0  
        while self.robot.step(self.timestep) != -1:  
            count += 1  
              
            # Legacy handshake logic for compatibility  
            if self.name == "Drone1" and count == 150:  
                print(f"[{self.name}] ISSUING SWARM-WIDE HANDSHAKE...")  
                self.tashi.broadcast(json.dumps({  
                    "text": "Mission START: Verified by Tashi Consensus",  
                    "timestamp": time.time()  
                }))  
  
            # XOPS: Simulate a delivery request for testing (remove in production)  
            if self.name == "Drone1" and count == 300:  
                print(f"[{self.name}] 📤 Submitting test delivery request...")  
                test_request = {  
                    "type": "delivery_request",  
                    "request_id": f"req_{int(time.time())}",  
                    "customer_id": "test_customer_001",  
                    "pickup": {"x": 5.0, "y": 0.0, "z": 1.0},  
                    "dropoff": {"x": -5.0, "y": 0.0, "z": 1.0},  
                    "package_weight": 2.5,  
                    "bid_deadline": time.time() + 300  # 5 minutes  
                }  
                self.tashi.broadcast(json.dumps(test_request))  
  
            # XOPS Delivery State Machine Logic  
            current_state = self.state_machine.current_state  
              
            if current_state == DeliveryState.NAVIGATING_PICKUP:  
                if self.navigate_to_target():  
                    print(f"[{self.name}] 📍 Arrived at pickup location")  
                    self.state_machine.transition_to(DeliveryState.AT_PICKUP)  
                      
            elif current_state == DeliveryState.AT_PICKUP:  
                self.execute_pickup()  
                self.state_machine.transition_to(DeliveryState.CARRYING)  
                self.target_location = self.state_machine.current_delivery.dropoff  
                  
            elif current_state == DeliveryState.CARRYING:  
                self.state_machine.transition_to(DeliveryState.NAVIGATING_DROPOFF)  
                  
            elif current_state == DeliveryState.NAVIGATING_DROPOFF:  
                if self.navigate_to_target():  
                    print(f"[{self.name}] 📍 Arrived at dropoff location")  
                    self.execute_dropoff()  
                      
            elif current_state == DeliveryState.RETURNING:  
                if self.navigate_to_target():  
                    print(f"[{self.name}] 🏠 Returned to base")  
                    self.state_machine.transition_to(DeliveryState.IDLE)  
                    self.target_location = None  
  
            # Continue normal operation - don't break for XOPS  
            if self.handshake_verified and count == 151:  
                print(f"[{self.name}] Handshake confirmed. XOPS Marketplace ready.")  
  
if __name__ == "__main__":  
    controller = TashiDroneController()  
    controller.run()