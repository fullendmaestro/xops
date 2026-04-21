import json  
import time  
import math  
from typing import List, Dict, Any, Optional  
  
import config  
from .delivery_state import DeliveryRequest, DeliveryState  
from .reputation_system import ReputationSystem, ReputationEventType  


def _count_swarm_drones() -> int:
    """Return the number of drone nodes in the swarm config."""
    return sum(
        1 for cfg in config.DRONE_CONFIG.values()
        if cfg.get("role", "drone") == "drone"
    )
  
  
class MarketplaceManager:  
    """Core marketplace logic for XOPS delivery coordination"""  
      
    def __init__(self, drone_id: str, tashi_node, capabilities: Optional[Dict[str, Any]] = None):  
        self.drone_id = drone_id  
        self.tashi_node = tashi_node  
        self.capabilities = capabilities or config.get_drone_capabilities(drone_id)  
        self.active_requests = {}  
        self.my_bids = {}  
        self.award_broadcasted = set()
        self.marketplace_stats = {  
            "total_requests_seen": 0,  
            "bids_submitted": 0,  
            "bids_won": 0,  
            "total_revenue": 0.0  
        }  
        self.reputation_system = ReputationSystem(  
            drone_id,  
            tashi_node,  
            self.capabilities.get("reputation", 100.0)  
        )  

    def handle_delivery_request(self, request_data: Dict[str, Any]):  
        """Process incoming delivery request and calculate bid"""  
        request_id = request_data["request_id"]  
        
        # Skip if already processing this request  
        if request_id in self.active_requests:  
            print(f"[{self.drone_id}] ⏭️ Already processing request {request_id}")  
            return False  
            
        print(f"[{self.drone_id}] 📦 Processing delivery request: {request_id}")  
      
        # Update marketplace stats  
        self.marketplace_stats["total_requests_seen"] += 1  
          
        # Create DeliveryRequest object  
        delivery_request = DeliveryRequest(  
            request_id=request_data["request_id"],  
            customer_id=request_data["customer_id"],  
            pickup=request_data["pickup"],  
            dropoff=request_data["dropoff"],  
            package_weight=request_data["package_weight"],  
            bid_deadline=request_data["bid_deadline"]  
        )  
          
        # Store the request  
        self.active_requests[request_id] = delivery_request  
          
        # Check if we can handle this delivery  
        if self.can_handle_delivery(delivery_request):  
            bid = self.calculate_bid(delivery_request)  
            if bid:  
                self.submit_bid(bid)  
                self.marketplace_stats["bids_submitted"] += 1  
                return True  
            else:  
                print(f"[{self.drone_id}] ❌ Bid calculation failed for {request_id}")  
        else:  
            print(f"[{self.drone_id}] ⏸️ Cannot handle request {request_id} - insufficient capabilities")  
              
        return False  
      
    def can_handle_delivery(self, request: DeliveryRequest) -> bool:  
        """Check if drone has capability for this delivery"""  
        # Check payload capacity  
        max_payload = self.capabilities.get("max_payload", 5.0)  
        if request.package_weight > max_payload:  
            print(f"[{self.drone_id}] Payload check failed: {request.package_weight}kg > {max_payload}kg")  
            return False  
              
        # Check range capability  
        distance = self.calculate_distance(request.pickup, request.dropoff)  
        max_range = self.capabilities.get("max_range", 10000)  
        if distance > max_range:  
            print(f"[{self.drone_id}] Range check failed: {distance}m > {max_range}m")  
            return False  
              
        # Check if deadline is feasible for the estimated flight duration.
        # The prior fixed 60s gate rejected normal web orders too aggressively.
        time_to_deadline = request.bid_deadline - time.time()  
        speed_mps = 10
        estimated_seconds = distance / speed_mps
        required_buffer = 15.0
        if time_to_deadline < estimated_seconds + required_buffer:  
            print(  
                f"[{self.drone_id}] Deadline check failed: {time_to_deadline}s remaining "  
                f"< estimated {estimated_seconds + required_buffer:.1f}s needed"  
            )  
            return False  
              
        # Check battery capacity (simplified)  
        battery_needed = distance * 0.001  # 1mAh per meter  
        battery_capacity = self.capabilities.get("battery_capacity", 5000)  
        if battery_needed > battery_capacity:  
            print(f"[{self.drone_id}] Battery check failed: {battery_needed}mAh > {battery_capacity}mAh")  
            return False  
              
        return True  
      
    def calculate_distance(self, pickup: Dict[str, float], dropoff: Dict[str, float]) -> float:  
        """Calculate Euclidean distance between two points"""  
        dx = dropoff["x"] - pickup["x"]  
        dy = dropoff["y"] - pickup["y"]  
        dz = dropoff["z"] - pickup["z"]  
        return math.sqrt(dx*dx + dy*dy + dz*dz)  
  
    def calculate_bid(self, request: DeliveryRequest) -> Optional[Dict[str, Any]]:  
        """Calculate competitive bid price and ETA for delivery request"""  
        if not self.can_handle_delivery(request):  
            return None  
              
        distance = self.calculate_distance(request.pickup, request.dropoff)  
          
        # Base price calculation  
        base_rate_per_meter = 0.01  # $0.01 per meter  
        weight_rate_per_kg = 0.5    # $0.50 per kg  
          
        base_price = distance * base_rate_per_meter  
        weight_cost = request.package_weight * weight_rate_per_kg  
          
        # Urgency factor (higher cost for tighter deadlines)  
        time_to_deadline = request.bid_deadline - time.time()  
        urgency_threshold = 1800  # 30 minutes  
        if time_to_deadline < urgency_threshold:  
            urgency_multiplier = (urgency_threshold - time_to_deadline) / urgency_threshold * 0.2  
        else:  
            urgency_multiplier = 0  
              
        # Reputation bonus (better reputation = lower prices)  
        reputation_bonus = 0.1  # 10% discount for good reputation  
        reputation = self.capabilities.get("reputation", 100.0)  
        if reputation > 90:  
            reputation_multiplier = -reputation_bonus  
        else:  
            reputation_multiplier = 0  
              
        total_price = max(1.0, base_price + weight_cost + urgency_multiplier + reputation_multiplier)  
        total_price = round(total_price, 2)  
          
        # ETA calculation (assuming 10 m/s average speed)  
        speed_mps = 10  
        eta_seconds = distance / speed_mps  
        eta_minutes = int(eta_seconds / 60)  

        return {  
            "drone_id": self.drone_id,  
            "request_id": request.request_id,  
            "bid_price": total_price,  
            "eta_minutes": eta_minutes,  
            "distance_meters": round(distance, 2),  
            "timestamp": time.time(),  
            "confidence": self.calculate_bid_confidence(request, distance)  
        }  
  
    def calculate_bid_confidence(self, request: DeliveryRequest, distance: float) -> float:  
        """Calculate confidence score for the bid (0.0 to 1.0)"""  
        confidence = 1.0  
          
        # Reduce confidence for very heavy packages  
        if request.package_weight > self.capabilities.get("max_payload", 5.0) * 0.8:  
            confidence -= 0.2  
              
        # Reduce confidence for very long distances  
        max_range = self.capabilities.get("max_range", 10000)  
        if distance > max_range * 0.8:  
            confidence -= 0.2  
              
        # Reduce confidence for tight deadlines  
        time_to_deadline = request.bid_deadline - time.time()  
        if time_to_deadline < 300:  # Less than 5 minutes  
            confidence -= 0.3  
              
        return max(0.1, confidence)  
      
    def submit_bid(self, bid: Dict[str, Any]):  
        """Submit bid to the marketplace via consensus"""  
        self.my_bids[bid["request_id"]] = bid  
          
        bid_message = {  
            "type": "delivery_bid",  
            **bid  
        }  
          
        success = self.tashi_node.broadcast(json.dumps(bid_message))  
        if success:  
            print(f"[{self.drone_id}] 💰 Submitted bid: ${bid['bid_price']} for {bid['request_id']} (ETA: {bid['eta_minutes']}min)")  
        else:  
            print(f"[{self.drone_id}] ❌ Failed to submit bid for {bid['request_id']}")  
              
        return success  
      

    def handle_delivery_bid(self, data: Dict[str, Any]):  
        """Track bids and award to lowest bidder when all drones have bid"""  
        request_id = data.get("request_id")  
        _ = data.get("drone_id")  
        
        if request_id in self.active_requests:  
            # Use attribute access, not dictionary access  
            self.active_requests[request_id].bids.append(data)  
            
            # Check if all drones have submitted bids  
            bids = self.active_requests[request_id].bids  
            unique_bidders = set(bid["drone_id"] for bid in bids)  
            if request_id in self.award_broadcasted:
                return

            # Award when we have bids from all eligible drones (dynamic count).
            num_drones = _count_swarm_drones()
            if len(unique_bidders) >= num_drones:
                # Elect the alphabetically-first bidder as coordinator to avoid
                # duplicate award broadcasts across the swarm.
                if self.drone_id != sorted(unique_bidders)[0]:
                    return

                # Find lowest bid (deterministic selection)  
                lowest_bid = min(bids, key=lambda x: x["bid_price"])  
                
                award_message = {  
                    "type": "bid_awarded",  
                    "request_id": request_id,  
                    "awarded_drone_id": lowest_bid["drone_id"],  
                    "final_price": lowest_bid["bid_price"]  
                }  
                
                # Broadcast through consensus network  
                self.tashi_node.broadcast(json.dumps(award_message))  
                self.award_broadcasted.add(request_id)
                print(f"[{self.drone_id}] 🏆 Awarded bid to {lowest_bid['drone_id']} at ${lowest_bid['bid_price']}")


    def handle_bid_awarded(self, award_data: Dict[str, Any]):  
        """Handle bid award notification"""  
        request_id = award_data["request_id"]  
        awarded_drone_id = award_data["awarded_drone_id"]  
        final_price = award_data["final_price"]  
          
        if awarded_drone_id == self.drone_id:  
            print(f"[{self.drone_id}] 🎉 WON BID for {request_id}! Price: ${final_price}")  
            self.marketplace_stats["bids_won"] += 1  
            self.marketplace_stats["total_revenue"] += final_price  
              
            # Update the delivery request  
            if request_id in self.active_requests:  
                self.active_requests[request_id].assigned_drone = self.drone_id  
                self.active_requests[request_id].status = "assigned"  
                  
            return True  # Signal that we should transition to ASSIGNED state  
        else:  
            print(f"[{self.drone_id}] ❌ Lost bid for {request_id} to {awarded_drone_id}")  
            # Clean up our bid for this request  
            if request_id in self.my_bids:  
                del self.my_bids[request_id]  
            return False  
      
    def handle_delivery_confirmation(self, confirmation_data: Dict[str, Any]):  
        """Handle delivery completion confirmation"""  
        request_id = confirmation_data["request_id"]  
        drone_id = confirmation_data["drone_id"]  
        status = confirmation_data["status"]  
          
        print(f"[{self.drone_id}] ✅ Delivery {request_id} by {drone_id}: {status}")  
          
        # Clean up from active tracking  
        if request_id in self.active_requests:  
            del self.active_requests[request_id]  
        if request_id in self.my_bids:  
            del self.my_bids[request_id]  
        self.award_broadcasted.discard(request_id)
              
        # Update reputation if this was our delivery  
        if drone_id == self.drone_id and status == "completed":  
            self.capabilities["reputation"] = min(100.0, self.capabilities.get("reputation", 100.0) + 1.0)  
            print(f"[{self.drone_id}] 📈 Reputation increased to {self.capabilities['reputation']}")  
      
    def get_marketplace_status(self) -> Dict[str, Any]:  
        """Get current marketplace status and statistics"""  
        return {  
            "drone_id": self.drone_id,  
            "active_requests_count": len(self.active_requests),  
            "pending_bids_count": len(self.my_bids),  
            "marketplace_stats": self.marketplace_stats.copy(),  
            "current_reputation": self.capabilities.get("reputation", 100.0),  
            "available_for_bids": all(  
                req.bid_deadline > time.time() for req in self.active_requests.values()  
            )  
        }