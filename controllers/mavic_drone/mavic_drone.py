from controller import Robot, Keyboard
import math

def clamp(value, low, high):
    return max(low, min(value, high))

class MavicAutonomous:
    def __init__(self):
        self.robot = Robot()
        self.timestep = int(self.robot.getBasicTimeStep())

        # 1. Initialize Devices
        self.imu = self.robot.getDevice("inertial unit")
        self.imu.enable(self.timestep)
        self.gps = self.robot.getDevice("gps")
        self.gps.enable(self.timestep)
        self.gyro = self.robot.getDevice("gyro")
        self.gyro.enable(self.timestep)
        self.gripper = self.robot.getDevice("gripper_connector")
        self.gripper.enablePresence(self.timestep)

        # 2. Initialize Motors (Velocity Mode)
        self.m = {}
        names = ["front left", "front right", "rear left", "rear right"]
        for name in names:
            dev = self.robot.getDevice(name + " propeller")
            dev.setPosition(float('inf'))
            dev.setVelocity(1.0)
            self.m[name] = dev

        # 3. Constants (From the C code you provided)
        self.k_vertical_thrust = 68.5
        self.k_vertical_offset = 0.6
        self.k_vertical_p = 3.0
        self.k_roll_p = 50.0
        self.k_pitch_p = 30.0
        
        # Mission Variables
        self.target_altitude = 1.0
        self.target_y = 2.0 # The Y coordinate of your box
        self.state = "TAKEOFF"

    def run(self):
        print("Drone starting... Aiming for Box at Y=2.0")
        
        while self.robot.step(self.timestep) != -1:
            # Read Sensors
            roll = self.imu.getRollPitchYaw()[0]
            pitch = self.imu.getRollPitchYaw()[1]
            altitude = self.gps.getValues()[2]
            roll_velocity = self.gyro.getValues()[0]
            pitch_velocity = self.gyro.getValues()[1]
            current_y = self.gps.getValues()[1]

            if math.isnan(altitude): continue

            # --- Autonomous State Machine ---
            pitch_disturbance = 0.0
            
            if self.state == "TAKEOFF":
                if altitude > 0.8: self.state = "NAVIGATE"
            
            elif self.state == "NAVIGATE":
                # Move toward box (Y=2.0)
                dist_y = self.target_y - current_y
                pitch_disturbance = clamp(dist_y * -2.0, -2.0, 2.0)
                if abs(dist_y) < 0.05: self.state = "DESCEND"
            
            elif self.state == "DESCEND":
                self.target_altitude = 0.25 # Lower to box
                if self.gripper.getPresence() == 1:
                    self.gripper.lock()
                    print("📦 BOX SECURED!")
                    self.state = "LIFT"
            
            elif self.state == "LIFT":
                self.target_altitude = 1.5

            # --- PID Logic (Mirroring your C code) ---
            roll_input = self.k_roll_p * clamp(roll, -1.0, 1.0) + roll_velocity
            pitch_input = self.k_pitch_p * clamp(pitch, -1.0, 1.0) + pitch_velocity + pitch_disturbance
            
            diff_alt = clamp(self.target_altitude - altitude + self.k_vertical_offset, -1.0, 1.0)
            vertical_input = self.k_vertical_p * pow(diff_alt, 3.0)

            # Extra lift if holding the box
            box_bonus = 5.0 if self.gripper.isLocked() else 0.0

            # --- Motor Mixing (Note the +/- signs matching the C code) ---
            fl = self.k_vertical_thrust + vertical_input - roll_input + pitch_input + box_bonus
            fr = self.k_vertical_thrust + vertical_input + roll_input + pitch_input + box_bonus
            rl = self.k_vertical_thrust + vertical_input - roll_input - pitch_input + box_bonus
            rr = self.k_vertical_thrust + vertical_input + roll_input - pitch_input + box_bonus

            # IMPORTANT: Invert the signs for FR and RL to account for propeller direction
            self.m["front left"].setVelocity(fl)
            self.m["front right"].setVelocity(-fr) # Inverted
            self.m["rear left"].setVelocity(-rl)  # Inverted
            self.m["rear right"].setVelocity(rr)

if __name__ == "__main__":
    MavicAutonomous().run()
