import math
from controller import Robot

def CLAMP(value, low, high):
    return low if value < low else (high if value > high else value)

class MavicAutonomous:
    def __init__(self):
        self.robot = Robot()
        self.timestep = int(self.robot.getBasicTimeStep())

        # Devices
        self.camera = self.robot.getDevice("camera")
        if self.camera: self.camera.enable(self.timestep)
        self.front_left_led = self.robot.getDevice("front left led")
        self.front_right_led = self.robot.getDevice("front right led")
        self.imu = self.robot.getDevice("inertial unit")
        self.imu.enable(self.timestep)
        self.gps = self.robot.getDevice("gps")
        self.gps.enable(self.timestep)
        self.gyro = self.robot.getDevice("gyro")
        self.gyro.enable(self.timestep)
        self.camera_roll_motor = self.robot.getDevice("camera roll")
        self.camera_pitch_motor = self.robot.getDevice("camera pitch")
        self.gripper = self.robot.getDevice("gripper_connector")
        if self.gripper:  
            self.gripper.enablePresence(self.timestep)  

        # Motors
        self.front_left_motor = self.robot.getDevice("front left propeller")
        self.front_right_motor = self.robot.getDevice("front right propeller")
        self.rear_left_motor = self.robot.getDevice("rear left propeller")
        self.rear_right_motor = self.robot.getDevice("rear right propeller")
        
        self.motors = [self.front_left_motor, self.front_right_motor, self.rear_left_motor, self.rear_right_motor]
        for m in self.motors:
            m.setPosition(float('inf'))
            m.setVelocity(1.0)

        # Exact Webots PID Constants
        self.k_vertical_thrust = 68.5
        self.k_vertical_offset = 0.6
        self.k_vertical_p = 3.0
        self.k_roll_p = 50.0
        self.k_pitch_p = 30.0

        # MISSION WAYPOINTS
        self.box_pos = [0.0, 1.5, 0.26]    # Box is exactly to the Left
        self.drop_pos = [0.0, -1.5, 0.35]  # Drop is exactly to the Right
        self.cruise_alt = 1.0
        
        self.state = "TAKEOFF"
        self.target_altitude = self.cruise_alt
        self.target_x = 0.0
        self.target_y = 0.0
        
        self.timer = 0
        self.step_counter = 0

    def run(self):
        print("🚀 Robust Navigation Mission Started")

        while self.robot.step(self.timestep) != -1:
            time = self.robot.getTime()
            self.step_counter += 1

            # Read Sensors
            roll, pitch, yaw = self.imu.getRollPitchYaw()
            pos = self.gps.getValues()
            if math.isnan(pos[0]): continue
            current_x, current_y, altitude = pos[0], pos[1], pos[2]
            roll_vel, pitch_vel, _ = self.gyro.getValues()

            # Hardware Stabilizers
            if self.front_left_led:
                led_state = int(time) % 2
                self.front_left_led.set(led_state)
                self.front_right_led.set(not led_state)
            if self.camera_roll_motor:
                self.camera_roll_motor.setPosition(-0.115 * roll_vel)
                self.camera_pitch_motor.setPosition(-0.1 * pitch_vel)

            # === GLOBAL ERROR CALCULATION ===
            dx = self.target_x - current_x
            dy = self.target_y - current_y
            dist_to_target = math.hypot(dx, dy)

            if self.step_counter % 32 == 0:
                print(f"[{self.state}] Dist: {dist_to_target:.2f}m | Alt: {altitude:.2f}m")

            # === MISSION STATE MACHINE ===
            if self.state == "TAKEOFF":
                self.target_x, self.target_y = 0.0, 0.0
                self.target_altitude = self.cruise_alt
                if altitude > self.cruise_alt - 0.05:
                    print("✅ Takeoff complete. Sliding to box...")
                    self.state = "FLY_TO_BOX"

            elif self.state == "FLY_TO_BOX":
                self.target_x, self.target_y = self.box_pos[0], self.box_pos[1]
                if dist_to_target < 0.05:
                    print("🛑 Arrived at box. Braking...")
                    self.timer = 150 
                    self.state = "STABILIZE_BOX"

            elif self.state == "STABILIZE_BOX":
                self.timer -= 1
                if self.timer <= 0:
                    print("⬇️ Descending to grab...")
                    self.state = "DESCEND"

            elif self.state == "DESCEND":  
                self.target_altitude = max(self.box_pos[2], self.target_altitude - 0.001)  
                if self.gripper and self.gripper.getPresence() == 1:  
                    self.gripper.lock()  
                    print("📦 Box Locked! Stabilizing...")  
                    self.timer = 50  # Add stabilization delay  
                    self.state = "STABILIZE_AFTER_LOCK" 

            elif self.state == "STABILIZE_AFTER_LOCK":  
                self.timer -= 1  
                if self.timer <= 0:  
                    print("✅ Stable. Lifting...")  
                    self.target_altitude = self.cruise_alt  
                    self.state = "LIFT"

            elif self.state == "DESCEND":  
                self.target_altitude = max(self.box_pos[2], self.target_altitude - 0.001)  
                if self.gripper:  
                    presence = self.gripper.getPresence()  
                    # Only lock if we're close enough and stable  
                    if presence == 1 and dist_to_target < 0.1:  
                        self.gripper.lock()  
                        print("📦 Box Locked! Lifting...")  
                        self.target_altitude = self.cruise_alt  
                        self.state = "LIFT"


            
            elif self.state == "LIFT":
                if altitude > self.cruise_alt - 0.05:
                    print("✅ Lifted safely. Sliding to drop zone...")
                    self.state = "FLY_TO_DROP"

            elif self.state == "FLY_TO_DROP":
                self.target_x, self.target_y = self.drop_pos[0], self.drop_pos[1]
                if dist_to_target < 0.05:
                    print("🛑 Arrived at drop zone. Braking...")
                    self.timer = 150
                    self.state = "STABILIZE_DROP"

            elif self.state == "STABILIZE_DROP":
                self.timer -= 1
                if self.timer <= 0:
                    print("⬇️ Descending to drop...")
                    self.state = "DROP_DESCEND"

            elif self.state == "DROP_DESCEND":
                self.target_altitude = max(self.drop_pos[2], self.target_altitude - 0.001)
                if altitude < self.drop_pos[2] + 0.05:
                    if self.gripper: self.gripper.unlock()
                    print("🏁 Box Dropped! Returning to hover...")
                    self.target_altitude = self.cruise_alt
                    self.state = "FINISH"
                    
            elif self.state == "FINISH":
                self.target_x, self.target_y = self.drop_pos[0], self.drop_pos[1]
                self.target_altitude = self.cruise_alt

            # === NAVIGATION KINEMATICS (The Fix) ===
            pitch_disturbance = 0.0
            roll_disturbance = 0.0
            
            # Force drone to permanently face Forward (Yaw = 0)
            yaw_disturbance = CLAMP(-yaw * 1.5, -0.5, 0.5) 

            # Only translate if we are in a flying state
            if dist_to_target > 0.05 and self.state in ["FLY_TO_BOX", "FLY_TO_DROP"]:
                
                # 1. Rotate the global error into the drone's local physical frame
                local_x = dx * math.cos(yaw) + dy * math.sin(yaw)
                local_y = -dx * math.sin(yaw) + dy * math.cos(yaw)
                
                # 2. Increased power authority (0.5) gives the drone brakes to stop drifting!
                p_gain = 0.5
                max_thrust = 0.5
                
                # 3. Corrected physical motor mapping
                pitch_disturbance = CLAMP(-local_x * p_gain, -max_thrust, max_thrust)
                roll_disturbance = CLAMP(local_y * p_gain, -max_thrust, max_thrust)

            # === ATTITUDE CONTROLLER (Inner Loop) ===
            roll_input = self.k_roll_p * CLAMP(roll, -1.0, 1.0) + roll_vel + roll_disturbance
            pitch_input = self.k_pitch_p * CLAMP(pitch, -1.0, 1.0) + pitch_vel + pitch_disturbance
            
            clamped_alt_diff = CLAMP(self.target_altitude - altitude + self.k_vertical_offset, -1.0, 1.0)
            vertical_input = self.k_vertical_p * (clamped_alt_diff ** 3.0)

            weight_comp = 7.0 if (self.gripper and self.gripper.isLocked()) else 0.0
            base_thrust = self.k_vertical_thrust + weight_comp

            # Apply final motor assignments
            fl = base_thrust + vertical_input - roll_input + pitch_input - yaw_disturbance
            fr = base_thrust + vertical_input + roll_input + pitch_input + yaw_disturbance
            rl = base_thrust + vertical_input - roll_input - pitch_input + yaw_disturbance
            rr = base_thrust + vertical_input + roll_input - pitch_input - yaw_disturbance
            
            self.front_left_motor.setVelocity(fl)
            self.front_right_motor.setVelocity(-fr)
            self.rear_left_motor.setVelocity(-rl)
            self.rear_right_motor.setVelocity(rr)

if __name__ == '__main__':
    MavicAutonomous().run()