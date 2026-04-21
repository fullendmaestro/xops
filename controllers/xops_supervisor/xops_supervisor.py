import json
import math
import os
import sys
import time
from typing import Any, Dict, Optional

from controller import Supervisor

# Reuse Tashi and config modules from tashi_drone controller package.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TASHI_CONTROLLER_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "tashi_drone"))
if TASHI_CONTROLLER_DIR not in sys.path:
    sys.path.append(TASHI_CONTROLLER_DIR)

try:
    import config
    from tashi_manager import TashiNode
except ImportError as exc:
    raise ImportError(f"Failed to load Tashi modules for xops_supervisor: {exc}")


class XopsSupervisor:
    def __init__(self):
        self.supervisor = Supervisor()
        self.timestep = int(self.supervisor.getBasicTimeStep())
        self.name = "XopsSupervisor"
        self.viewpoint = self.supervisor.getFromDef("MAIN_VIEWPOINT")
        self.default_viewpoint_target = "Drone1"
        self.active_viewpoint_target: Optional[str] = None

        self.package_node = self.supervisor.getFromDef("PACKAGE_BOX")

        # Dynamically build drone_nodes from all drone entries in the swarm config.
        self.drone_nodes: Dict[str, Any] = {}
        for node_name, node_cfg in config.DRONE_CONFIG.items():
            if node_cfg.get("role", "drone") == "drone":
                def_name = node_name.upper().replace(" ", "_")
                node = self.supervisor.getFromDef(def_name)
                if node:
                    self.drone_nodes[node_name] = node
                    print(f"[XopsSupervisor] Registered drone node: {node_name} (DEF={def_name})")
                else:
                    print(f"[XopsSupervisor] WARNING: DEF {def_name} not found in world for {node_name}")

        self.current_request: Optional[Dict[str, Any]] = None
        self.assigned_drone_id: Optional[str] = None
        self.package_attached = False
        self.follow_offset = [0.0, 0.0, -0.12]

        # Proximity-based attach/detach thresholds.
        self.attach_distance = 2.5
        self.attach_horizontal = 2.5
        self.attach_vertical = 2.0
        self.pickup_altitude_ceiling = 2.5
        self.detach_distance = 3.0
        self.detach_horizontal = 3.5
        self.detach_altitude_ceiling = 6.0

        if not self.package_node:
            print("[XopsSupervisor] Missing DEF PACKAGE_BOX node in world")
        if not self.viewpoint:
            print("[XopsSupervisor] Missing DEF MAIN_VIEWPOINT node in world")

        self._set_viewpoint_follow(self.default_viewpoint_target)

        self.tashi = self._init_tashi_node()

    def _find_key_generate(self) -> Optional[str]:
        tools_dir = config.TASHI_TOOLS_DIR
        release = os.path.join(tools_dir, "target", "release", "key-generate")
        debug = os.path.join(tools_dir, "target", "debug", "key-generate")
        if os.path.exists(release):
            return release
        if os.path.exists(debug):
            return debug
        return None

    def _init_tashi_node(self) -> Optional[TashiNode]:
        try:
            key_gen = self._find_key_generate()
            if not key_gen:
                print("[XopsSupervisor] key-generate binary not found; supervisor messaging disabled")
                return None

            node_cfg = config.get_node_config(self.name)
            if not node_cfg:
                print(
                    "[XopsSupervisor] Missing identity in swarm_config.json for XopsSupervisor"
                )
                return None

            tashi = TashiNode(
                node_id=self.name,
                bind_addr=f"127.0.0.1:{node_cfg['port']}",
                secret_key=node_cfg["secret"],
                peer_list=config.get_peers(exclude_node=self.name),
                tools_dir=config.TASHI_TOOLS_DIR,
            )
            tashi.on_message_callback = self._on_message_received
            tashi.start()
            print("[XopsSupervisor] Connected to Tashi swarm")
            return tashi
        except Exception as exc:
            print(f"[XopsSupervisor] Failed to initialize Tashi node: {exc}")
            return None

    @staticmethod
    def _distance(a, b) -> float:
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def _set_viewpoint_follow(self, target_def: str):
        if not self.viewpoint:
            return

        try:
            follow_field = self.viewpoint.getField("follow")
            follow_type_field = self.viewpoint.getField("followType")
            if follow_field:
                follow_field.setSFString(target_def)
            if follow_type_field:
                follow_type_field.setSFString("Pan and Tilt Shot")
                self.active_viewpoint_target = target_def
                print(f"[XopsSupervisor] Viewpoint now following {target_def}")
        except Exception as exc:
            print(f"[XopsSupervisor] Failed to update viewpoint follow target: {exc}")

    def _reset_viewpoint_to_default(self):
        self._set_viewpoint_follow(self.default_viewpoint_target)

    def _on_message_received(self, msg: str):
        print(f"[XopsSupervisor] Message received: {msg[:120]}")
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")
        if msg_type == "delivery_request":
            self.current_request = {
                "request_id": data.get("request_id"),
                "pickup": data.get("pickup"),
                "dropoff": data.get("dropoff"),
            }
            self.assigned_drone_id = None
            self.package_attached = False
            self._reset_viewpoint_to_default()
            self._place_package_at_pickup()
            print(
                f"[XopsSupervisor] Spawned package at pickup for request {data.get('request_id')}"
            )
        elif msg_type == "bid_awarded":
            request_id = data.get("request_id")
            if self.current_request and request_id == self.current_request.get("request_id"):
                self.assigned_drone_id = data.get("awarded_drone_id")
                if self.assigned_drone_id:
                    self._set_viewpoint_follow(self.assigned_drone_id)
                print(
                    f"[XopsSupervisor] Delivery {request_id} assigned to {self.assigned_drone_id}"
                )

    def _place_package_at_pickup(self):
        if not self.package_node or not self.current_request:
            return
        pickup = self.current_request.get("pickup") or {"x": 0.0, "y": 0.0, "z": 0.35}
        self.package_node.getField("translation").setSFVec3f(
            [pickup["x"], pickup["y"], max(0.3, pickup.get("z", 0.35))]
        )
        self.package_node.getField("rotation").setSFRotation([0, 0, 1, 0])
        self.package_node.resetPhysics()

    def _broadcast_event(self, event_type: str):
        if not self.tashi or not self.current_request:
            return
        payload = {
            "type": "supervisor_event",
            "event": event_type,
            "request_id": self.current_request.get("request_id"),
            "drone_id": self.assigned_drone_id,
            "timestamp": time.time(),
        }
        self.tashi.broadcast(json.dumps(payload))

    def _attach_if_ready(self):
        if self.package_attached:
            return
        if not self.current_request or not self.assigned_drone_id or not self.package_node:
            return

        drone_node = self.drone_nodes.get(self.assigned_drone_id)
        if not drone_node:
            print(f"[XopsSupervisor] WARNING: no node found for {self.assigned_drone_id}")
            return

        drone_pos = drone_node.getPosition()
        pkg_pos = self.package_node.getPosition()

        if drone_pos[2] > self.pickup_altitude_ceiling:
            return

        dist = self._distance(drone_pos, pkg_pos)
        dx = drone_pos[0] - pkg_pos[0]
        dy = drone_pos[1] - pkg_pos[1]
        dz = drone_pos[2] - pkg_pos[2]
        horizontal_dist = math.sqrt(dx * dx + dy * dy)
        vertical_dist = abs(dz)

        if (
            dist <= self.attach_distance
            or (horizontal_dist <= self.attach_horizontal and vertical_dist <= self.attach_vertical)
        ):
            self.package_attached = True
            self._broadcast_event("attached")
            print(
                f"[XopsSupervisor] Package attached to {self.assigned_drone_id} "
                f"(3D={dist:.3f}m XY={horizontal_dist:.3f}m Z={vertical_dist:.3f}m)"
            )

    def _follow_attached_package(self):
        if not self.package_attached or not self.package_node or not self.assigned_drone_id:
            return

        drone_node = self.drone_nodes.get(self.assigned_drone_id)
        if not drone_node:
            return

        drone_pos = drone_node.getPosition()
        drone_rot = drone_node.getField("rotation").getSFRotation()

        target = [
            drone_pos[0] + self.follow_offset[0],
            drone_pos[1] + self.follow_offset[1],
            drone_pos[2] + self.follow_offset[2],
        ]

        self.package_node.getField("translation").setSFVec3f(target)
        self.package_node.getField("rotation").setSFRotation(drone_rot)
        self.package_node.resetPhysics()

    def _detach_if_ready(self):
        if not self.package_attached or not self.current_request or not self.assigned_drone_id:
            return
        if not self.package_node:
            return

        drone_node = self.drone_nodes.get(self.assigned_drone_id)
        if not drone_node:
            return

        dropoff = self.current_request.get("dropoff")
        if not dropoff:
            return

        drone_pos = drone_node.getPosition()
        if drone_pos[2] > self.detach_altitude_ceiling:
            return

        target = [dropoff["x"], dropoff["y"], max(0.3, dropoff.get("z", 0.35))]
        dist_to_drop = self._distance(drone_pos, target)
        dx = drone_pos[0] - target[0]
        dy = drone_pos[1] - target[1]
        horizontal_dist = math.sqrt(dx * dx + dy * dy)

        if dist_to_drop <= self.detach_distance or horizontal_dist <= self.detach_horizontal:
            self.package_node.getField("translation").setSFVec3f(target)
            self.package_node.resetPhysics()
            self.package_attached = False
            self._broadcast_event("detached")
            print(
                f"[XopsSupervisor] Package detached near dropoff "
                f"(3D={dist_to_drop:.3f}m XY={horizontal_dist:.3f}m)"
            )

            # Clear current assignment after successful drop.
            self.current_request = None
            self.assigned_drone_id = None
            self._reset_viewpoint_to_default()

    def run(self):
        print("[XopsSupervisor] Running package supervisor")
        while self.supervisor.step(self.timestep) != -1:
            self._attach_if_ready()
            self._follow_attached_package()
            self._detach_if_ready()


if __name__ == "__main__":
    XopsSupervisor().run()
