import paho.mqtt.client as mqtt
import json
import time
import random

# MQTT Broker settings
BROKER_ADDRESS = "192.168.68.66"  # Fixed MQTT broker IP
PORT = 1883

# Fixed Robot IP
ROBOT_IP = "172.16.0.211"  # Robot will always use this IP

PUBLISH_INTERVAL = 2  # Seconds between messages

# Store latest game state, phase, team color, and navigation routes
latest_game_state = "PAUSED"  # Default state
latest_phase = "SETUP"  # Default phase
latest_team_color = "UNKNOWN"  # Default team color
latest_navigation_routes = {}  # Store last received navigation routes

# Function to generate random pose data
def generate_pose_data():
    return {
        "x": round(random.uniform(0, 5), 2),  # Random x position
        "y": round(random.uniform(0, 5), 2),  # Random y position
        "yaw": round(random.uniform(0, 360), 2)  # Random yaw angle
    }

# Function to handle movement when in production and running
def robot_move():
    print("🔹 Robot is MOVING... (Production & Running)")

# Function to handle when paused in production
def robot_paused():
    print("🔸 Robot is PAUSED... (Production & Paused)")

# Callback for when a message is received
# Callback for when a message is received
def on_message(client, userdata, message):
    global latest_game_state, latest_phase, latest_team_color, latest_navigation_routes

    try:
        payload_str = message.payload.decode().strip()  # Decode and strip whitespace

        if not payload_str:  # Check if the payload is empty
            print(f"⚠️ Received empty message on topic: {message.topic}, skipping...")
            return

        # Handle navigation routes (JSON format expected)
        if message.topic == f"{ROBOT_IP}/private/navigation_routes":
            try:
                latest_navigation_routes = json.loads(payload_str)  # Parse as JSON
                print(f"📥 Navigation Routes Updated: {json.dumps(latest_navigation_routes, indent=2)}")
            except json.JSONDecodeError:
                print(f"❌ Error: Invalid JSON received on {message.topic}, skipping...")
            return

        # Handle text-based messages
        if message.topic == f"{ROBOT_IP}/game_state":
            latest_game_state = payload_str  # Store raw text as game state
            print(f"📢 Game State Updated: {latest_game_state}")

        elif message.topic == f"{ROBOT_IP}/phase":
            latest_phase = payload_str  # Store raw text as phase
            print(f"📢 Phase Updated: {latest_phase}")

        elif message.topic == f"{ROBOT_IP}/teamColor":
            latest_team_color = payload_str  # Store raw text as team color
            print(f"🎨 Team Color Updated: {latest_team_color}")

        # Check conditions to call movement functions
        if latest_phase == "PRODUCTION":
            if latest_game_state == "RUNNING":
                robot_move()
            elif latest_game_state == "PAUSED":
                robot_paused()

    except Exception as e:
        print(f"❌ Unexpected error processing message on {message.topic}: {e}")


# MQTT client setup
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT broker at {BROKER_ADDRESS}")
        client.subscribe(f"{ROBOT_IP}/game_state")
        client.subscribe(f"{ROBOT_IP}/phase")
        client.subscribe(f"{ROBOT_IP}/teamColor")
        client.subscribe("private/#")
        client.subscribe(f"{ROBOT_IP}/private/navigation_routes")  # Subscribe to navigation_routes request
        print(f"✅ Subscribed to {ROBOT_IP}/game_state, {ROBOT_IP}/phase, {ROBOT_IP}/teamColor, private/#, {ROBOT_IP}/private/navigation_routes")
    else:
        print(f"❌ Failed to connect, return code {rc}")

client.on_connect = on_connect
client.on_message = on_message

# Connect to broker
print(f"🚀 Connecting to broker {BROKER_ADDRESS}...")
client.connect(BROKER_ADDRESS, PORT)
client.loop_start()

try:
    while True:
        # Publish pose data
        pose_data = generate_pose_data()
        pose_topic = f"{ROBOT_IP}/pose"
        pose_payload = json.dumps(pose_data)
        client.publish(pose_topic, pose_payload)
        print(f"📡 Published to {pose_topic}: {pose_payload}")

        time.sleep(PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print("🛑 Stopping publisher...")
    client.loop_stop()
    client.disconnect()



