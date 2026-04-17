import math
from controller import Supervisor


class InstantAttachSupervisor:
    def __init__(self):
        self.supervisor = Supervisor()
        self.timestep = int(self.supervisor.getBasicTimeStep())

        self.drone = self.supervisor.getFromDef("MAVIC_DRONE")
        self.package = self.supervisor.getFromDef("LIGHT_MYBOT")

        self.attached = False
        # Very permissive "nearby" thresholds for instant attachment.
        self.attach_distance = 2.5
        self.attach_horizontal = 2.5
        self.attach_vertical = 2.0
        self.pickup_altitude_ceiling = 0.45
        self.follow_offset = [0.0, 0.0, -0.12]

        if not self.drone:
            print("[attach_supervisor] Missing DEF MAVIC_DRONE node.")
        if not self.package:
            print("[attach_supervisor] Missing DEF LIGHT_MYBOT node.")

    def _distance(self, a, b):
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def _attach_on_proximity(self):
        if self.attached or not self.drone or not self.package:
            return

        drone_pos = self.drone.getPosition()
        package_pos = self.package.getPosition()
        dist = self._distance(drone_pos, package_pos)
        dx = drone_pos[0] - package_pos[0]
        dy = drone_pos[1] - package_pos[1]
        dz = drone_pos[2] - package_pos[2]
        horizontal_dist = math.sqrt(dx * dx + dy * dy)
        vertical_dist = abs(dz)

        if (
            dist <= self.attach_distance
            or (horizontal_dist <= self.attach_horizontal and vertical_dist <= self.attach_vertical)
        ) and drone_pos[2] <= self.pickup_altitude_ceiling:
            self.attached = True
            # Keep the package under the drone body once attached.
            self.follow_offset = [0.0, 0.0, -0.12]
            print(
                "[attach_supervisor] Attached package "
                f"(3D={dist:.3f} m, XY={horizontal_dist:.3f} m, Z={vertical_dist:.3f} m)"
            )

    def _follow_drone(self):
        if not self.attached or not self.drone or not self.package:
            return

        drone_pos = self.drone.getPosition()
        drone_rot = self.drone.getField("rotation").getSFRotation()

        target = [
            drone_pos[0] + self.follow_offset[0],
            drone_pos[1] + self.follow_offset[1],
            drone_pos[2] + self.follow_offset[2],
        ]

        self.package.getField("translation").setSFVec3f(target)
        self.package.getField("rotation").setSFRotation(drone_rot)
        self.package.resetPhysics()

    def run(self):
        print("[attach_supervisor] Running instant-attachment supervisor")
        while self.supervisor.step(self.timestep) != -1:
            self._attach_on_proximity()
            self._follow_drone()


if __name__ == "__main__":
    InstantAttachSupervisor().run()
