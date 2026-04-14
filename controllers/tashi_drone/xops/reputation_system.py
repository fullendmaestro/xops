import json  
import time  
import math  
from typing import Dict, Any, List, Optional  
from dataclasses import dataclass  
from enum import Enum  
  
class ReputationEventType(Enum):  
    """Types of events that affect reputation"""  
    DELIVERY_COMPLETED = "delivery_completed"  
    DELIVERY_FAILED = "delivery_failed"  
    DELIVERY_LATE = "delivery_late"  
    BID_ACCURATE = "bid_accurate"  
    BID_INACCURATE = "bid_inaccurate"  
    CUSTOMER_RATING = "customer_rating"  
  
@dataclass  
class ReputationEvent:  
    """Single reputation event with impact score"""  
    event_type: ReputationEventType  
    drone_id: str  
    request_id: str  
    impact: float  # Positive or negative impact on reputation  
    timestamp: float  
    metadata: Dict[str, Any]  
  
class ReputationSystem:  
    """Decentralized reputation management for XOPS marketplace"""  
      
    def __init__(self, drone_id: str, tashi_node, initial_reputation: float = 100.0):  
        self.drone_id = drone_id  
        self.tashi_node = tashi_node  
        self.current_reputation = initial_reputation  
        self.reputation_history = []  
        self.performance_metrics = {  
            "total_deliveries": 0,  
            "successful_deliveries": 0,  
            "failed_deliveries": 0,  
            "late_deliveries": 0,  
            "average_eta_accuracy": 0.0,  
            "customer_ratings": []  
        }  
          
        # Reputation calculation weights  
        self.weights = {  
            "delivery_success": 10.0,  
            "delivery_failure": -15.0,  
            "late_delivery": -5.0,  
            "eta_accuracy": 2.0,  
            "customer_rating": 5.0  
        }  
          
        # Reputation decay and recovery parameters  
        self.decay_rate = 0.001  # Small decay per hour to encourage activity  
        self.min_reputation = 0.0  
        self.max_reputation = 200.0  
          
    def calculate_reputation_impact(self, event_type: ReputationEventType,   
                                  metadata: Dict[str, Any]) -> float:  
        """Calculate the reputation impact for an event"""  
        if event_type == ReputationEventType.DELIVERY_COMPLETED:  
            base_impact = self.weights["delivery_success"]  
            # Bonus for early delivery  
            if metadata.get("delivered_early", False):  
                base_impact += 2.0  
            return base_impact  
              
        elif event_type == ReputationEventType.DELIVERY_FAILED:  
            base_impact = self.weights["delivery_failure"]  
            # Reduce impact if failure was due to external factors  
            if metadata.get("external_failure", False):  
                base_impact *= 0.5  
            return base_impact  
              
        elif event_type == ReputationEventType.DELIVERY_LATE:  
            # Scale impact by how late the delivery was  
            delay_minutes = metadata.get("delay_minutes", 0)  
            base_impact = self.weights["late_delivery"] * (1 + delay_minutes / 30)  
            return base_impact  
              
        elif event_type == ReputationEventType.BID_ACCURATE:  
            # Reward accurate ETA predictions  
            eta_error = metadata.get("eta_error_minutes", 0)  
            if eta_error <= 2:  # Within 2 minutes  
                return self.weights["eta_accuracy"]  
            elif eta_error <= 5:  # Within 5 minutes  
                return self.weights["eta_accuracy"] * 0.5  
            return 0  
              
        elif event_type == ReputationEventType.BID_INACCURATE:  
            # Penalize inaccurate ETA predictions  
            eta_error = metadata.get("eta_error_minutes", 0)  
            if eta_error > 10:  # More than 10 minutes off  
                return -self.weights["eta_accuracy"]  
            return -self.weights["eta_accuracy"] * 0.5  
              
        elif event_type == ReputationEventType.CUSTOMER_RATING:  
            rating = metadata.get("rating", 3)  # 1-5 scale  
            if rating >= 4:  
                return self.weights["customer_rating"] * (rating / 5)  
            elif rating <= 2:  
                return -self.weights["customer_rating"] * (3 - rating) / 3  
            return 0  
              
        return 0.0  
      
    def add_reputation_event(self, event_type: ReputationEventType,   
                           request_id: str, metadata: Dict[str, Any] = None):  
        """Add a reputation event and broadcast to swarm"""  
        if metadata is None:  
            metadata = {}  
              
        impact = self.calculate_reputation_impact(event_type, metadata)  
          
        # Create reputation event  
        event = ReputationEvent(  
            event_type=event_type,  
            drone_id=self.drone_id,  
            request_id=request_id,  
            impact=impact,  
            timestamp=time.time(),  
            metadata=metadata  
        )  
          
        # Update local reputation  
        self.update_local_reputation(event)  
          
        # Broadcast to swarm for consensus verification  
        self.broadcast_reputation_update(event)  
          
    def update_local_reputation(self, event: ReputationEvent):  
        """Update local reputation based on event"""  
        self.current_reputation += event.impact  
        self.current_reputation = max(self.min_reputation,   
                                    min(self.max_reputation, self.current_reputation))  
          
        # Add to history  
        self.reputation_history.append(event)  
          
        # Update performance metrics  
        self._update_performance_metrics(event)  
          
        print(f"[{self.drone_id}] 📊 Reputation updated: {self.current_reputation:.1f} "  
              f"({event.event_type.value}: {event.impact:+.1f})")  
      
    def _update_performance_metrics(self, event: ReputationEvent):  
        """Update performance metrics based on event"""  
        if event.event_type == ReputationEventType.DELIVERY_COMPLETED:  
            self.performance_metrics["total_deliveries"] += 1  
            self.performance_metrics["successful_deliveries"] += 1  
              
        elif event.event_type == ReputationEventType.DELIVERY_FAILED:  
            self.performance_metrics["total_deliveries"] += 1  
            self.performance_metrics["failed_deliveries"] += 1  
              
        elif event.event_type == ReputationEventType.DELIVERY_LATE:  
            self.performance_metrics["late_deliveries"] += 1  
              
        elif event.event_type in [ReputationEventType.BID_ACCURATE,   
                                ReputationEventType.BID_INACCURATE]:  
            eta_error = abs(event.metadata.get("eta_error_minutes", 0))  
            current_avg = self.performance_metrics["average_eta_accuracy"]  
            total_bids = len([e for e in self.reputation_history   
                            if e.event_type in [ReputationEventType.BID_ACCURATE,   
                                              ReputationEventType.BID_INACCURATE]])  
              
            if total_bids > 0:  
                self.performance_metrics["average_eta_accuracy"] = (  
                    (current_avg * (total_bids - 1) + eta_error) / total_bids  
                )  
            else:  
                self.performance_metrics["average_eta_accuracy"] = eta_error  
                  
        elif event.event_type == ReputationEventType.CUSTOMER_RATING:  
            rating = event.metadata.get("rating", 3)  
            self.performance_metrics["customer_ratings"].append(rating)  
      
    def broadcast_reputation_update(self, event: ReputationEvent):  
        """Broadcast reputation event to swarm for consensus"""  
        reputation_message = {  
            "type": "reputation_update",  
            "drone_id": event.drone_id,  
            "request_id": event.request_id,  
            "event_type": event.event_type.value,  
            "impact": event.impact,  
            "timestamp": event.timestamp,  
            "metadata": event.metadata,  
            "signature": self._sign_reputation_event(event)  
        }  
          
        self.tashi_node.broadcast(json.dumps(reputation_message))  
      
    def _sign_reputation_event(self, event: ReputationEvent) -> str:  
        """Create a simple signature for reputation event (in production, use proper crypto)"""  
        event_data = f"{event.drone_id}{event.request_id}{event.event_type.value}{event.timestamp}"  
        return f"sig_{hash(event_data) % 10000}"  # Simplified signature  
      
    def handle_reputation_update(self, update_data: Dict[str, Any]):  
        """Handle reputation update from another drone"""  
        drone_id = update_data["drone_id"]  
          
        if drone_id == self.drone_id:  
            # This is our own update, already processed  
            return  
              
        # Verify signature (simplified)  
        # In production, implement proper cryptographic verification  
        print(f"[{self.drone_id}] 📋 Received reputation update for {drone_id}: "  
              f"{update_data['event_type']} ({update_data['impact']:+.1f})")  
          
        # Store peer reputation data for bid evaluation  
        # In a full implementation, maintain a separate peer reputation database  
      
    def get_reputation_score(self) -> float:  
        """Get current reputation score"""  
        # Apply time-based decay  
        hours_since_last_activity = 0  
        if self.reputation_history:  
            last_event = max(self.reputation_history, key=lambda e: e.timestamp)  
            hours_since_last_activity = (time.time() - last_event.timestamp) / 3600  
          
        decayed_reputation = self.current_reputation * (1 - self.decay_rate * hours_since_last_activity)  
        return max(self.min_reputation, min(self.max_reputation, decayed_reputation))  
      
    def get_reputation_summary(self) -> Dict[str, Any]:  
        """Get comprehensive reputation summary"""  
        success_rate = 0  
        if self.performance_metrics["total_deliveries"] > 0:  
            success_rate = (self.performance_metrics["successful_deliveries"] /   
                          self.performance_metrics["total_deliveries"]) * 100  
          
        avg_customer_rating = 0  
        if self.performance_metrics["customer_ratings"]:  
            avg_customer_rating = (
                sum(self.performance_metrics["customer_ratings"])
                / len(self.performance_metrics["customer_ratings"])
            )  
          
        return {  
            "drone_id": self.drone_id,  
            "current_reputation": self.get_reputation_score(),  
            "success_rate_percent": round(success_rate, 1),  
            "total_deliveries": self.performance_metrics["total_deliveries"],  
            "failed_deliveries": self.performance_metrics["failed_deliveries"],  
            "late_deliveries": self.performance_metrics["late_deliveries"],  
            "average_eta_accuracy": round(self.performance_metrics["average_eta_accuracy"], 1),  
            "average_customer_rating": round(avg_customer_rating, 1),  
            "reputation_trend": self._calculate_reputation_trend()  
        }  
      
    def _calculate_reputation_trend(self) -> str:  
        """Calculate recent reputation trend"""  
        if len(self.reputation_history) < 5:  
            return "insufficient_data"  
          
        recent_events = self.reputation_history[-5:]  
        recent_impact = sum(e.impact for e in recent_events)  
          
        if recent_impact > 5:  
            return "improving"  
        elif recent_impact < -5:  
            return "declining"  
        else:  
            return "stable"  
      
    def apply_reputation_to_bid_calculation(self, base_price: float) -> float:  
        """Apply reputation-based pricing adjustment"""  
        reputation_score = self.get_reputation_score()  
          
        # High reputation drones get price advantages  
        if reputation_score >= 150:  
            discount = 0.1  # 10% discount  
        elif reputation_score >= 120:  
            discount = 0.05  # 5% discount  
        elif reputation_score <= 50:  
            premium = 0.2   # 20% premium for low reputation  
            return base_price * (1 + premium)  
        else:  
            discount = 0.0  
          
        return base_price * (1 - discount)