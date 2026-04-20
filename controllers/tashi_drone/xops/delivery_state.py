from enum import Enum  
from typing import Dict, Any, Optional, List  
import time  
import math  
  
class DeliveryState(Enum):  
    """States for drone delivery lifecycle"""  
    IDLE = "idle"  
    BIDDING = "bidding"  
    ASSIGNED = "assigned"  
    NAVIGATING_PICKUP = "navigating_pickup"  
    AT_PICKUP = "at_pickup"  
    CARRYING = "carrying"  
    NAVIGATING_DROPOFF = "navigating_dropoff"  
    DELIVERED = "delivered"  
    RETURNING = "returning"  
    ERROR = "error"  
  
class DeliveryRequest:  
    """Data structure for delivery requests"""  
    def __init__(self, request_id: str, customer_id: str, pickup: Dict[str, float],   
                 dropoff: Dict[str, float], package_weight: float, bid_deadline: float):  
        self.request_id = request_id  
        self.customer_id = customer_id  
        self.pickup = pickup  # {"x": 0, "y": 0, "z": 0}  
        self.dropoff = dropoff  
        self.package_weight = package_weight  
        self.bid_deadline = bid_deadline  
        self.assigned_drone = None  
        self.status = "pending"  
        self.created_at = time.time()  
        self.bids = []  
          
    def to_dict(self) -> Dict[str, Any]:  
        """Convert to dictionary for JSON serialization"""  
        return {  
            "request_id": self.request_id,  
            "customer_id": self.customer_id,  
            "pickup": self.pickup,  
            "dropoff": self.dropoff,  
            "package_weight": self.package_weight,  
            "bid_deadline": self.bid_deadline,  
            "assigned_drone": self.assigned_drone,  
            "status": self.status,  
            "created_at": self.created_at,  
            "bids": self.bids  
        }  
  
class DeliveryStateMachine:  
    """Manages state transitions for drone delivery operations"""  
      
    # Valid state transitions  
    VALID_TRANSITIONS = {  
        DeliveryState.IDLE: [DeliveryState.BIDDING],  
        DeliveryState.BIDDING: [DeliveryState.ASSIGNED, DeliveryState.IDLE],  
        DeliveryState.ASSIGNED: [DeliveryState.NAVIGATING_PICKUP, DeliveryState.ERROR],  
        DeliveryState.NAVIGATING_PICKUP: [DeliveryState.AT_PICKUP, DeliveryState.ERROR],  
        DeliveryState.AT_PICKUP: [DeliveryState.CARRYING, DeliveryState.ERROR],  
        DeliveryState.CARRYING: [DeliveryState.NAVIGATING_DROPOFF, DeliveryState.ERROR],  
        DeliveryState.NAVIGATING_DROPOFF: [DeliveryState.DELIVERED, DeliveryState.ERROR],  
        DeliveryState.DELIVERED: [DeliveryState.RETURNING],  
        DeliveryState.RETURNING: [DeliveryState.IDLE],  
        DeliveryState.ERROR: [DeliveryState.IDLE]  # Recovery path  
    }  
      
    def __init__(self, drone_id: str):  
        self.drone_id = drone_id  
        self.current_state = DeliveryState.IDLE  
        self.current_delivery = None  
        self.state_history = []  
        self.error_message = None  
          
    def can_transition_to(self, new_state: DeliveryState) -> bool:  
        """Check if transition to new state is valid"""  
        # Allow staying in the same state  
        if new_state == self.current_state:  
            return True  
        return new_state in self.VALID_TRANSITIONS.get(self.current_state, [])
      
    def transition_to(self, new_state: DeliveryState, context: Optional[Dict[str, Any]] = None) -> bool:  
        """Transition to new state if valid"""  
        if not self.can_transition_to(new_state):  
            print(f"[{self.drone_id}] ❌ Invalid state transition: {self.current_state.value} → {new_state.value}")  
            return False  
              
        old_state = self.current_state  
        self.current_state = new_state  
          
        # Record state transition  
        self.state_history.append({  
            "from": old_state.value,  
            "to": new_state.value,  
            "timestamp": time.time(),  
            "context": context  
        })  
          
        print(f"[{self.drone_id}] 🔄 State transition: {old_state.value} → {new_state.value}")  
          
        # Handle state entry logic  
        self._on_state_entry(new_state, context)  
          
        return True  
      
    def _on_state_entry(self, state: DeliveryState, context: Optional[Dict[str, Any]]):  
        """Handle logic when entering a new state"""  
        if state == DeliveryState.BIDDING:  
            print(f"[{self.drone_id}] 📊 Entering bidding phase")  
        elif state == DeliveryState.ASSIGNED:  
            if context and "delivery" in context:  
                self.current_delivery = context["delivery"]  
                print(f"[{self.drone_id}] ✅ Assigned to delivery: {self.current_delivery.request_id}")  
        elif state == DeliveryState.ERROR:  
            if context and "error" in context:  
                self.error_message = context["error"]  
                print(f"[{self.drone_id}] ❌ Error state: {self.error_message}")  
        elif state == DeliveryState.DELIVERED:  
            print(f"[{self.drone_id}] 🎉 Delivery completed successfully!")  
        elif state == DeliveryState.IDLE:  
            self.current_delivery = None  
            self.error_message = None  
            print(f"[{self.drone_id}] 🏠 Returned to idle state")  
      
    def get_status_summary(self) -> Dict[str, Any]:  
        """Get current status summary"""  
        return {  
            "drone_id": self.drone_id,  
            "current_state": self.current_state.value,  
            "current_delivery": self.current_delivery.to_dict() if self.current_delivery else None,  
            "error_message": self.error_message,  
            "state_history_count": len(self.state_history)  
        }  
      
    def is_available_for_bid(self) -> bool:  
        """Check if drone is available to bid on new deliveries"""  
        return self.current_state == DeliveryState.IDLE  
      
    def is_carrying_package(self) -> bool:  
        """Check if drone is currently carrying a package"""  
        return self.current_state == DeliveryState.CARRYING  
      
    def get_delivery_progress(self) -> Optional[Dict[str, Any]]:  
        """Get progress information for current delivery"""  
        if not self.current_delivery:  
            return None  
              
        return {  
            "request_id": self.current_delivery.request_id,  
            "state": self.current_state.value,  
            "pickup": self.current_delivery.pickup,  
            "dropoff": self.current_delivery.dropoff,  
            "status": self.current_delivery.status  
        }  
  
class BidManager:  
    """Manages bid calculation and submission logic"""  
      
    def __init__(self, drone_id: str, capabilities: Dict[str, float]):  
        self.drone_id = drone_id  
        self.capabilities = capabilities  # max_payload, max_range, battery_capacity  
        self.base_rate_per_meter = 0.01  # $0.01 per meter  
        self.weight_rate_per_kg = 0.5    # $0.50 per kg  
        self.urgency_multiplier = 0.1    # Additional cost for urgency  
      
    def calculate_distance(self, pickup: Dict[str, float], dropoff: Dict[str, float]) -> float:  
        """Calculate Euclidean distance between two points"""  
        dx = dropoff["x"] - pickup["x"]  
        dy = dropoff["y"] - pickup["y"]  
        dz = dropoff["z"] - pickup["z"]  
        return math.sqrt(dx*dx + dy*dy + dz*dz)  
      
    def can_handle_delivery(self, request: DeliveryRequest) -> bool:  
        """Check if drone can handle the delivery request"""  
        # Check payload capacity  
        if request.package_weight > self.capabilities.get("max_payload", 5.0):  
            return False  
              
        # Check range capability  
        distance = self.calculate_distance(request.pickup, request.dropoff)  
        if distance > self.capabilities.get("max_range", 10000):  
            return False  
              
        # Check if deadline is reasonable  
        time_to_deadline = request.bid_deadline - time.time()  
        if time_to_deadline < 60:  # Less than 1 minute  
            return False  
              
        return True  
      
    def calculate_bid(self, request: DeliveryRequest) -> Optional[Dict[str, Any]]:  
        """Calculate bid price and ETA for delivery request"""  
        if not self.can_handle_delivery(request):  
            return None  
              
        distance = self.calculate_distance(request.pickup, request.dropoff)  
          
        # Base price calculation  
        base_price = distance * self.base_rate_per_meter  
        weight_cost = request.package_weight * self.weight_rate_per_kg  
          
        # Urgency factor (higher cost for tighter deadlines)  
        time_to_deadline = request.bid_deadline - time.time()  
        urgency_factor = max(0, (1800 - time_to_deadline) / 1800) * self.urgency_multiplier  # 30 min threshold  
          
        total_price = round(base_price + weight_cost + urgency_factor, 2)  
          
        # ETA calculation (assuming 10 m/s average speed)  
        eta_minutes = int(distance / 10 / 60)  # Convert to minutes  
          
        return {  
            "drone_id": self.drone_id,  
            "request_id": request.request_id,  
            "bid_price": total_price,  
            "eta_minutes": eta_minutes,  
            "distance_meters": round(distance, 2),  
            "timestamp": time.time()  
        }