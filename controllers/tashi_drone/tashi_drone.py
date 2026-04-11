from controller import Robot
import json
import time
import os
import sys

# Ensure local modules can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from tashi_manager import TashiNode
    import config
except ImportError as e:
    print(f"IMPORT ERROR: {e}. Check if tashi_manager.py and config.py are in this folder.")

class TashiDroneController:
    """
    Main Webots Controller for Decentralized Tashi Swarm.
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

    def on_message_received(self, msg):
        """Callback triggered when the Tashi Node verifies a consensus message"""
        try:
            data = json.loads(msg)
            print(f"[{self.name}] ✅ VERIFIED CONSENSUS: {data['text']}")
            
            # Mission logic based on verified command
            if "Mission START" in data['text']:
                self.handshake_verified = True
        except:
            pass

    def run(self):
        count = 0
        while self.robot.step(self.timestep) != -1:
            count += 1
            
            # Leader broadcast logic: Done 1 triggers a swarm-wide handshake
            if self.name == "Drone1" and count == 150:
                print(f"[{self.name}] ISSUING SWARM-WIDE HANDSHAKE...")
                self.tashi.broadcast(json.dumps({
                    "text": "Mission START: Verified by Tashi Consensus",
                    "timestamp": time.time()
                }))

            # React to consensus confirmation
            if self.handshake_verified:
                print(f"[{self.name}] Handshake confirmed. Moving to MISSION state.")
                # Add flight behavior/takeoff here
                break

if __name__ == "__main__":
    controller = TashiDroneController()
    controller.run()
