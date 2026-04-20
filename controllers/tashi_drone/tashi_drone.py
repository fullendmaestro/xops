from controller import Robot  
import json  
import math  
import os  
import sys  
import time  
from enum import Enum  
from typing import Any, Dict, Optional, Tuple  
  
# Ensure local modules can be found  
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  
  
try:  
    from tashi_manager import TashiNode  
    import config  
    from xops.delivery_state import DeliveryStateMachine, DeliveryState  
    from xops.marketplace_manager import MarketplaceManager  
    from xops.reputation_system import ReputationEventType  
    from xops.locations import HOME_POINTS  
except ImportError as e:  
    print(f"IMPORT ERROR: {e}. Check if required modules are in this folder.")  
    raise  
  
  
def clamp(value: float, value_min: float, value_max: float) -> float:  
    return min(max(value, value_min), value_max)  
  
  
def normalize_angle(angle: float) -> float:  
    while angle > math.pi:  
        angle -= 2.0 * math.pi  
    while angle < -math.pi:  
        angle += 2.0 * math.pi  
    return angle  
  
  
class MessageType(Enum):  
    DELIVERY_REQUEST = "delivery_request"  
    DELIVERY_BID = "delivery_bid"  
    BID_AWARDED = "bid_awarded"  
    DELIVERY_CONFIRMATION = "delivery_confirmation"  
    SUPERVISOR_EVENT = "supervisor_event"  
  
  
class NavMode(Enum):  
    TO_PICKUP = "to_pickup"  
    TO_DROPOFF = "to_dropoff"  
    TO_HOME = "to_home"  
  
  
class NavPhase(Enum):  
    ASCEND = "ascend"  
    CRUISE = "cruise"  
    DESCEND = "descend"  
    HOLD = "hold"  
    LAND = "land"  
  
  
class TashiDroneController:  
    """Main Webots controller for decentralized XOPS flight + marketplace logic."""  
  
    K_VERTICAL_THRUST = 68.5  
    K_VERTICAL_OFFSET = 0.6  
    K_VERTICAL_P = 3.0  
    K_ROLL_P = 50.0  
    K_PITCH_P = 30.0  
    MAX_YAW_DISTURBANCE = 0.45  
    MAX_PITCH_DISTURBANCE = -1.0  
  
    CRUISE_ALTITUDE = 12.0  
    PICKUP_ALTITUDE = 1.8  
    DROPOFF_ALTITUDE = 1.8  
    PRECISION_LAND_ALTITUDE = 0.28  
    XY_PRECISION = 0.7  
    ALT_PRECISION = 0.35  
    HOME_GROUND_ALTITUDE = 0.12  
  
    def __init__(self):  
        self.robot = Robot()  
        self.name = self.robot.getName()  
        self.timestep = int(self.robot.getBasicTimeStep())  
  
        print(f"[{self.name}] Initializing distributed XOPS controller")  
  
        if self.name not in config.DRONE_CONFIG:  
            print(  
                f"[{self.name}] CRITICAL: Identity mismatch. Check Webots robot name and swarm_config.json"  
            )  
            return  
  
        cfg = config.DRONE_CONFIG[self.name]  
        self.tashi = TashiNode(  
            node_id=self.name,  
            bind_addr=f"127.0.0.1:{cfg['port']}",  
            secret_key=cfg["secret"],  
            peer_list=config.get_peers(exclude_node=self.name),  
            tools_dir=config.TASHI_TOOLS_DIR,  
        )  
        self.tashi.on_message_callback = self.on_message_received  
        self.tashi.start()  
  
        self.state_machine = DeliveryStateMachine(self.name)  
        self.marketplace = MarketplaceManager(  
            self.name,  
            self.tashi,  
            config.get_drone_capabilities(self.name),  
        )  
  
        self.handshake_verified = False  
        self.delivery_package: Optional[Dict[str, Any]] = None  
        self.package_attached = False  
        self.last_confirmed_request_id: Optional[str] = None  
  
        self.nav_mode: Optional[NavMode] = None  
        self.nav_phase: NavPhase = NavPhase.ASCEND  
  
        self.flight_ready = False  
        self.home_location = HOME_POINTS.get(self.name, {"x": 0.0, "y": 0.0, "z": 0.15})  
  
        self.target_waypoint: Optional[Dict[str, float]] = None  
        self.target_altitude = self.CRUISE_ALTITUDE  
  
        self._init_flight_devices()  
  
    def _init_flight_devices(self):  
        self.imu = self.robot.getDevice("inertial unit")  
        self.gps = self.robot.getDevice("gps")  
        self.gyro = self.robot.getDevice("gyro")  
  
        self.imu.enable(self.timestep)  
        self.gps.enable(self.timestep)  
        self.gyro.enable(self.timestep)  
  
        self.front_left_motor = self.robot.getDevice("front left propeller")  
        self.front_right_motor = self.robot.getDevice("front right propeller")  
        self.rear_left_motor = self.robot.getDevice("rear left propeller")  
        self.rear_right_motor = self.robot.getDevice("rear right propeller")  
  
        self.motors = [  
            self.front_left_motor,  
            self.front_right_motor,  
            self.rear_left_motor,  
            self.rear_right_motor,  
        ]  
        for motor in self.motors:  
            motor.setPosition(float("inf"))  
            motor.setVelocity(1.0)  
  
    def validate_message_schema(self, data: Dict[str, Any], message_type: str) -> bool:  
        try:  
            if message_type == MessageType.DELIVERY_REQUEST.value:  
                required_fields = [  
                    "request_id",  
                    "customer_id",  
                    "pickup",  
                    "dropoff",  
                    "package_weight",  
                    "bid_deadline",  
                ]  
                return all(field in data for field in required_fields)  
            if message_type == MessageType.DELIVERY_BID.value:  
                required_fields = ["drone_id", "request_id", "bid_price", "eta_minutes"]  
                return all(field in data for field in required_fields)  
            if message_type == MessageType.BID_AWARDED.value:  
                required_fields = ["request_id", "awarded_drone_id", "final_price"]  
                return all(field in data for field in required_fields)  
            if message_type == MessageType.DELIVERY_CONFIRMATION.value:  
                required_fields = ["request_id", "drone_id", "status", "timestamp"]  
                return all(field in data for field in required_fields)  
            if message_type == MessageType.SUPERVISOR_EVENT.value:  
                required_fields = ["event", "request_id", "drone_id"]  
                return all(field in data for field in required_fields)  
            return False  
        except Exception:  
            return False  
  
    def on_message_received(self, msg: str):  
        print(f"[{self.name}] Message recieved {msg}")  
        try:  
            data = json.loads(msg)  
            message_type = data.get("type")  
  
            if not message_type:  
                if "text" in data and "Mission START" in data["text"]:  
                    print(f"[{self.name}] Verified consensus handshake")  
                    self.handshake_verified = True  
                return  
  
            if not self.validate_message_schema(data, message_type):  
                print(f"[{self.name}] Invalid schema for {message_type}")  
                return  
  
            if message_type == MessageType.DELIVERY_REQUEST.value:  
                self.handle_delivery_request(data)  
            elif message_type == MessageType.DELIVERY_BID.value:  
                self.marketplace.handle_delivery_bid(data)  
            elif message_type == MessageType.BID_AWARDED.value:  
                self.handle_bid_awarded(data)  
            elif message_type == MessageType.DELIVERY_CONFIRMATION.value:  
                self.handle_delivery_confirmation(data)  
            elif message_type == MessageType.SUPERVISOR_EVENT.value:  
                self.handle_supervisor_event(data)  
            elif message_type == "reputation_update":  
                self.marketplace.reputation_system.handle_reputation_update(data)  
        except json.JSONDecodeError:  
            return  
        except Exception as exc:  
            print(f"[{self.name}] Message processing error: {exc}")  
  
    def handle_delivery_request(self, data: Dict[str, Any]):  
        request_id = data["request_id"]  
        if self.marketplace.handle_delivery_request(data):  
            if request_id in self.marketplace.active_requests:  
                delivery_request = self.marketplace.active_requests[request_id]  
                self.state_machine.transition_to(DeliveryState.BIDDING, {"delivery": delivery_request})  
  
    def handle_delivery_bid(self, data: Dict[str, Any]):  
        request_id = data["request_id"]  
        if request_id in self.marketplace.active_requests:  
            self.marketplace.active_requests[request_id].bids.append(data)  
  
    def handle_bid_awarded(self, data: Dict[str, Any]):  
        request_id = data["request_id"]  
        awarded_drone_id = data["awarded_drone_id"]  

        # Ignore duplicate award notifications for the same request.
        if self.last_confirmed_request_id == request_id:
            return
  
        if awarded_drone_id != self.name:  
            if self.state_machine.current_state == DeliveryState.BIDDING:  
                self.state_machine.transition_to(DeliveryState.IDLE)  
            return  
  
        if request_id not in self.marketplace.active_requests:  
            return  
  
        print(f"[{self.name}] Won bid for request {request_id}")  
        delivery = self.marketplace.active_requests[request_id]  
        assigned_ok = self.state_machine.transition_to(DeliveryState.ASSIGNED, {"delivery": delivery})
        if assigned_ok:
            self.state_machine.transition_to(DeliveryState.NAVIGATING_PICKUP)
            self.last_confirmed_request_id = request_id
  
        self.nav_mode = NavMode.TO_PICKUP  
        self.nav_phase = NavPhase.ASCEND  
        self.target_waypoint = delivery.pickup  
        self.target_altitude = self.CRUISE_ALTITUDE  
  
    def handle_delivery_confirmation(self, data: Dict[str, Any]):  
        self.marketplace.handle_delivery_confirmation(data)  
  
    # def handle_supervisor_event(self, data: Dict[str, Any]):  
    #     if data.get("drone_id") != self.name:  
    #         return  
        
    #     if data.get("event") == "attached":  
    #         self.package_attached = True  
    #         print(f"[{self.name}] Package attachment confirmed by supervisor")

    def handle_supervisor_event(self, data: Dict[str, Any]):  
        if data.get("drone_id") != self.name:  
            return  
  
        if self.state_machine.current_delivery and data.get("request_id") != self.state_machine.current_delivery.request_id:  
            return  
  
        event = data.get("event")  
        if event == "attached":  
            self.package_attached = True  
            self.delivery_package = {"attached_at": time.time()}  
            print(f"[{self.name}] Supervisor confirmed package attached")  
        elif event == "detached":  
            self.package_attached = False  
            self.delivery_package = None  
            print(f"[{self.name}] Supervisor confirmed package detached")  
  
    def _read_sensors(self) -> Tuple[float, float, float, float, float, float, float, float, float]:  
        roll, pitch, yaw = self.imu.getRollPitchYaw()  
        x_pos, y_pos, altitude = self.gps.getValues()  
        roll_rate, pitch_rate, yaw_rate = self.gyro.getValues()  
        return roll, pitch, yaw, x_pos, y_pos, altitude, roll_rate, pitch_rate, yaw_rate  
  
    def _xy_distance_to_target(self, x_pos: float, y_pos: float, target: Dict[str, float]) -> float:  
        dx = target["x"] - x_pos  
        dy = target["y"] - y_pos  
        return math.sqrt(dx * dx + dy * dy)  
  
    def _apply_flight_control(  
        self,  
        roll: float,  
        pitch: float,  
        yaw: float,  
        x_pos: float,  
        y_pos: float,  
        altitude: float,  
        roll_rate: float,  
        pitch_rate: float,  
    ):  
        yaw_disturbance = 0.0  
        pitch_disturbance = 0.0  
  
        if self.target_waypoint is not None:  
            dx = self.target_waypoint["x"] - x_pos  
            dy = self.target_waypoint["y"] - y_pos  
            desired_yaw = math.atan2(dy, dx)  
            yaw_error = normalize_angle(desired_yaw - yaw)  
            yaw_disturbance = clamp(  
                self.MAX_YAW_DISTURBANCE * yaw_error / math.pi,  
                -self.MAX_YAW_DISTURBANCE,  
                self.MAX_YAW_DISTURBANCE,  
            )  
  
            distance_xy = math.sqrt(dx * dx + dy * dy)  
            yaw_alignment = 1.0 - min(abs(yaw_error) / 1.2, 1.0)  
            pitch_disturbance = clamp(  
                -0.25 * distance_xy * yaw_alignment,  
                self.MAX_PITCH_DISTURBANCE,  
                0.1,  
            )  
  
        roll_input = self.K_ROLL_P * clamp(roll, -1, 1) + roll_rate  
        pitch_input = self.K_PITCH_P * clamp(pitch, -1, 1) + pitch_rate + pitch_disturbance  
        yaw_input = yaw_disturbance  
  
        clamped_altitude_error = clamp(  
            self.target_altitude - altitude + self.K_VERTICAL_OFFSET,  
            -1,  
            1,  
        )  
        vertical_input = self.K_VERTICAL_P * pow(clamped_altitude_error, 3.0)  
  
        front_left = self.K_VERTICAL_THRUST + vertical_input - yaw_input + pitch_input - roll_input  
        front_right = self.K_VERTICAL_THRUST + vertical_input + yaw_input + pitch_input + roll_input  
        rear_left = self.K_VERTICAL_THRUST + vertical_input + yaw_input - pitch_input - roll_input  
        rear_right = self.K_VERTICAL_THRUST + vertical_input - yaw_input - pitch_input + roll_input  
  
        self.front_left_motor.setVelocity(front_left)  
        self.front_right_motor.setVelocity(-front_right)  
        self.rear_left_motor.setVelocity(-rear_left)  
        self.rear_right_motor.setVelocity(rear_right)  
  
    def _navigate_pickup_or_dropoff(self, mode: NavMode, target: Dict[str, float]) -> bool:  
        (  
            roll,  
            pitch,  
            yaw,  
            x_pos,  
            y_pos,  
            altitude,  
            roll_rate,  
            pitch_rate,  
            _,  
        ) = self._read_sensors()  
  
        low_altitude = self.PICKUP_ALTITUDE if mode == NavMode.TO_PICKUP else self.DROPOFF_ALTITUDE  
  
        if self.nav_phase == NavPhase.ASCEND:  
            self.target_waypoint = target  
            self.target_altitude = self.CRUISE_ALTITUDE  
            if altitude >= self.CRUISE_ALTITUDE - 0.6:  
                self.nav_phase = NavPhase.CRUISE  
  
        elif self.nav_phase == NavPhase.CRUISE:  
            self.target_waypoint = target  
            self.target_altitude = self.CRUISE_ALTITUDE  
            if self._xy_distance_to_target(x_pos, y_pos, target) <= self.XY_PRECISION:  
                self.nav_phase = NavPhase.DESCEND  
  
        elif self.nav_phase == NavPhase.DESCEND:  
            self.target_waypoint = target  
            self.target_altitude = low_altitude  
            close_xy = self._xy_distance_to_target(x_pos, y_pos, target) <= self.XY_PRECISION  
            close_z = abs(altitude - low_altitude) <= self.ALT_PRECISION  
            if close_xy and close_z:  
                self.nav_phase = NavPhase.HOLD  
  
        elif self.nav_phase == NavPhase.HOLD:  
            self.target_waypoint = target  
            self.target_altitude = low_altitude  
            self._apply_flight_control(  
                roll,  
                pitch,  
                yaw,  
                x_pos,  
                y_pos,  
                altitude,  
                roll_rate,  
                pitch_rate,  
            )  
            return True  
  
        self._apply_flight_control(  
            roll,  
            pitch,  
            yaw,  
            x_pos,  
            y_pos,  
            altitude,  
            roll_rate,  
            pitch_rate,  
        )  
        return False  
  
    def _navigate_home(self) -> bool:  
        (  
            roll,  
            pitch,  
            yaw,  
            x_pos,  
            y_pos,  
            altitude,  
            roll_rate,  
            pitch_rate,  
            _,  
        ) = self._read_sensors()  
  
        if self.nav_phase == NavPhase.ASCEND:  
            self.target_waypoint = self.home_location  
            self.target_altitude = self.CRUISE_ALTITUDE  
            if altitude >= self.CRUISE_ALTITUDE - 0.6:  
                self.nav_phase = NavPhase.CRUISE  
  
        elif self.nav_phase == NavPhase.CRUISE:  
            self.target_waypoint = self.home_location  
            self.target_altitude = self.CRUISE_ALTITUDE  
            if self._xy_distance_to_target(x_pos, y_pos, self.home_location) <= self.XY_PRECISION:  
                self.nav_phase = NavPhase.LAND  
  
        elif self.nav_phase == NavPhase.LAND:  
            self.target_waypoint = self.home_location  
            self.target_altitude = self.PRECISION_LAND_ALTITUDE  
            close_xy = self._xy_distance_to_target(x_pos, y_pos, self.home_location) <= 0.35  
            close_z = altitude <= self.PRECISION_LAND_ALTITUDE + 0.2  
            if close_xy and close_z:  
                self._apply_flight_control(  
                    roll,  
                    pitch,  
                    yaw,  
                    x_pos,  
                    y_pos,  
                    altitude,  
                    roll_rate,  
                    pitch_rate,  
                )  
                return True  
  
        self._apply_flight_control(  
            roll,  
            pitch,  
            yaw,  
            x_pos,  
            y_pos,  
            altitude,  
            roll_rate,  
            pitch_rate,  
        )  
        return False  
  
    def _confirm_delivery(self):  
        if not self.state_machine.current_delivery:  
            return  
  
        request_id = self.state_machine.current_delivery.request_id  
        confirmation_message = {  
            "type": "delivery_confirmation",  
            "request_id": request_id,  
            "drone_id": self.name,  
            "status": "completed",  
            "timestamp": time.time()  
        }  
          
        self.tashi.broadcast(json.dumps(confirmation_message))  
        print(f"[{self.name}] ✅ Delivery confirmation sent for {request_id}")  
  
    def _set_motors_idle(self):  
        """Set all motors to minimum velocity"""  
        for motor in self.motors:  
            motor.setVelocity(0.0)  
  
    def run(self):  
        print(f"[{self.name}] Running XOPS drone controller")  
        count = 0  
          
        while self.robot.step(self.timestep) != -1:  
            count += 1  
              
            # Broadcast consensus handshake  
            if not self.handshake_verified and count == 100:  
                self.tashi.broadcast(  
                    json.dumps(  
                        {  
                            "text": "Mission START: Verified by Tashi Consensus",  
                            "timestamp": time.time(),  
                        }  
                    )  
                )  
  
            # Test delivery

            # if self.name == "Drone1" and count == 500:  
            #     self.tashi.broadcast(  
            #         json.dumps(  
            #             {'type': 'delivery_request', 'customer_id': 'cust_001', 'pickup': {'x': -8.0, 'y': 6.0, 'z': 0.35}, 'dropoff': {'x': 4.0, 'y': 15.0, 'z': 0.35}, 'package_weight': 1, 'bid_deadline': 2776632718.092778, 'request_id': 'req_1776632688092'}  
            #         )  
            #     )
            
  
            current_state = self.state_machine.current_state  
  
            if current_state == DeliveryState.NAVIGATING_PICKUP and self.state_machine.current_delivery:  
                reached = self._navigate_pickup_or_dropoff(  
                    NavMode.TO_PICKUP,  
                    self.state_machine.current_delivery.pickup,  
                )  
                if reached:  
                    self.state_machine.transition_to(DeliveryState.AT_PICKUP)  
  
            elif current_state == DeliveryState.AT_PICKUP:  
                if self.package_attached:  
                    self.state_machine.transition_to(DeliveryState.CARRYING)  
                    self.state_machine.transition_to(DeliveryState.NAVIGATING_DROPOFF)  
                    self.nav_mode = NavMode.TO_DROPOFF  
                    self.nav_phase = NavPhase.ASCEND  
  
            elif current_state == DeliveryState.NAVIGATING_DROPOFF and self.state_machine.current_delivery:  
                reached = self._navigate_pickup_or_dropoff(  
                    NavMode.TO_DROPOFF,  
                    self.state_machine.current_delivery.dropoff,  
                )  
                if reached:  
                    self.state_machine.transition_to(DeliveryState.DELIVERED)  
  
            elif current_state == DeliveryState.DELIVERED:  
                if not self.package_attached:  
                    self._confirm_delivery()  
                    self.state_machine.transition_to(DeliveryState.RETURNING)  
                    self.nav_mode = NavMode.TO_HOME  
                    self.nav_phase = NavPhase.ASCEND  
  
            elif current_state == DeliveryState.RETURNING:  
                if self._navigate_home():  
                    print(f"[{self.name}] Precision landing complete at home pad")  
                    self.state_machine.transition_to(DeliveryState.IDLE)  
                    self.nav_mode = None  
                    self.nav_phase = NavPhase.ASCEND  
                    self.last_confirmed_request_id = None
                    self.target_waypoint = None  
                    self.target_altitude = self.CRUISE_ALTITUDE  
  
            else:  
                # Default behavior: stay stationed at home waypoint and keep motors off when grounded.  
                (  
                    roll,  
                    pitch,  
                    yaw,  
                    x_pos,  
                    y_pos,  
                    altitude,  
                    roll_rate,  
                    pitch_rate,  
                    _,  
                ) = self._read_sensors()  
  
                has_delivery = self.state_machine.current_delivery is not None  
                home_target = {  
                    "x": self.home_location["x"],  
                    "y": self.home_location["y"],  
                    "z": self.HOME_GROUND_ALTITUDE,  
                }  
  
                xy_to_home = self._xy_distance_to_target(x_pos, y_pos, home_target)  
                at_home_ground = (  
                    xy_to_home <= 0.35 and altitude <= self.HOME_GROUND_ALTITUDE + 0.1  
                )  
  
                if not has_delivery and current_state in (DeliveryState.IDLE, DeliveryState.BIDDING) and at_home_ground:  
                    self.target_waypoint = home_target  
                    self.target_altitude = self.HOME_GROUND_ALTITUDE  
                    self._set_motors_idle()  
                else:  
                    self.target_waypoint = home_target  
                    self.target_altitude = self.HOME_GROUND_ALTITUDE  
                    self._apply_flight_control(  
                        roll,  
                        pitch,  
                        yaw,  
                        x_pos,  
                        y_pos,  
                        altitude,  
                        roll_rate,  
                        pitch_rate,  
                    )  
  
  
if __name__ == "__main__":  
    controller = TashiDroneController()  
    controller.run()