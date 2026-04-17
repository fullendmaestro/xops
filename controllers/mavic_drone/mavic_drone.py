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
  
        # Exact Webots PID Constants [1](#9-0)   
        self.k_vertical_thrust = 68.5  
        self.k_vertical_offset = 0.6  
        self.k_vertical_p = 3.0  
        self.k_roll_p = 50.0  
        self.k_pitch_p = 30.0  
  
        # MISSION WAYPOINTS  
        self.box_pos = [0.0, 3.5, 0.1]    # Box position (Cardboard box location)  
        self.drop_pos = [2.5, -2.5, 0.3]  # Drop location - different from initial pickup  
        self.cruise_alt = 1.0  
        self.climb_alt = 1.5  # Higher altitude for horizontal movement  
          
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
                self.target_altitude = max(self.box_pos[2] + 0.05, self.target_altitude - 0.002)    
                if self.gripper:  
                    presence = self.gripper.getPresence()  
                    if self.step_counter % 8 == 0:  
                        print(f"Connector presence: {presence}, distance: {self.gripper.getDistance()}")  
                    if self.gripper.isLocked() or presence == 1:  
                        if not self.gripper.isLocked():
                            self.gripper.lock()  
                        print("📦 Box Locked! Stabilizing...")    
                        self.timer = 100  
                        self.state = "STABILIZE_AFTER_LOCK"  
  
            elif self.state == "STABILIZE_AFTER_LOCK":    
                self.timer -= 1    
                if self.timer <= 0:    
                    print("✅ Stable. Lifting...")    
                    self.target_altitude = self.cruise_alt    
                    self.state = "LIFT"  
              
            elif self.state == "LIFT":  
                if altitude > self.climb_alt - 0.05:  
                    print("⬆️ Climbing to high altitude...")  
                    self.target_altitude = self.climb_alt  
                    self.state = "FLY_HORIZONTAL"  
  
            elif self.state == "FLY_HORIZONTAL":  
                self.target_x, self.target_y = self.drop_pos[0], self.drop_pos[1]  
                if dist_to_target < 0.3:  
                    print("↗️ Reached horizontal destination. Climbing more...")  
                    self.state = "FLY_VERTICAL_UP_MORE"  
  
            elif self.state == "FLY_VERTICAL_UP_MORE":  
                self.target_altitude = self.climb_alt + 0.3  
                if altitude > self.climb_alt + 0.25:  
                    print("⬇️ At peak altitude. Descending to drop zone...")  
                    self.state = "DROP_DESCEND"  
  
            elif self.state == "DROP_DESCEND":  
                self.target_x, self.target_y = self.drop_pos[0], self.drop_pos[1]  
                self.target_altitude = max(self.drop_pos[2], self.target_altitude - 0.003)  
                if altitude < self.drop_pos[2] + 0.1:  
                    if self.gripper and self.gripper.isLocked():  
                        self.gripper.unlock()  
                        print("🏁 Box Dropped at new location! Returning home...")  
                    self.state = "RETURN_HOME"  
                      
            elif self.state == "RETURN_HOME":  
                self.target_x, self.target_y = 0.0, 0.0  
                self.target_altitude = self.cruise_alt  
  
            # === NAVIGATION KINEMATICS (Fixed) ===  
            pitch_disturbance = 0.0  
            roll_disturbance = 0.0  
              
            # Force drone to permanently face Forward (Yaw = 0)  
            yaw_disturbance = CLAMP(-yaw * 1.5, -0.5, 0.5)   
  
            # Only translate if we are in a flying state  
            if dist_to_target > 0.05 and self.state in ["FLY_TO_BOX", "FLY_TO_DROP"]:  
                  
                # Fixed coordinate transformation  
                local_x = dx * math.cos(-yaw) - dy * math.sin(-yaw)  
                local_y = dx * math.sin(-yaw) + dy * math.cos(-yaw)  
                  
                # Reduced gains for stability  
                p_gain = 0.3  
                max_thrust = 0.3  
                  
                # Corrected physical motor mapping  
                pitch_disturbance = CLAMP(-local_x * p_gain, -max_thrust, max_thrust)  
                roll_disturbance = CLAMP(local_y * p_gain, -max_thrust, max_thrust)  
  
            # === ATTITUDE CONTROLLER (Inner Loop) ===  
            roll_input = self.k_roll_p * CLAMP(roll, -1.0, 1.0) + roll_vel + roll_disturbance  
            pitch_input = self.k_pitch_p * CLAMP(pitch, -1.0, 1.0) + pitch_vel + pitch_disturbance  
              
            clamped_alt_diff = CLAMP(self.target_altitude - altitude + self.k_vertical_offset, -1.0, 1.0)  
            vertical_input = self.k_vertical_p * (clamped_alt_diff ** 3.0)  
  
            weight_comp = 7.0 if (self.gripper and self.gripper.isLocked()) else 0.0  
            base_thrust = self.k_vertical_thrust + weight_comp  
  
            # Apply final motor assignments (corrected) [2](#9-1)   
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