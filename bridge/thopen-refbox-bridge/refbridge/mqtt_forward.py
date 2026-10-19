import paho.mqtt.client as mqtt
import json
import os

# กำหนดค่าของ MQTT Broker จาก environment variables
REFBRIDGE_BROKER = os.getenv("REFBRIDGE_BROKER", "mqtt://refbridge_broker_address")
MAGENTA_BROKER = os.getenv("MAGENTA_BROKER", "mqtt://magenta_broker_address")
CYAN_BROKER = os.getenv("CYAN_BROKER", "mqtt://cyan_broker_address")
PORT = 1883

# แมพ Robot IP กับทีม
TEAM_MAPPING = {
    "MAGENTA":"172.16.0.216" ,
    "CYAN":"172.16.0.211"
}

# หัวข้อ (Topics) ที่ต้องการรับส่ง
REFBRIDGE_TOPIC_PREFIX = "172.16.0."
GAME_STATE_TOPIC = "public/game_state"
PRIVATE_TOPIC_PREFIX = "private/"

# สร้าง MQTT Clients
client_refbridge = mqtt.Client()
client_magenta = mqtt.Client()
client_cyan = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to broker {client._client_id.decode()}")
        # if client == client_refbridge:
        #     for ip in TEAM_MAPPING.keys():
        #         client.subscribe(f"{ip}/pose")
        for teamColor, ip in TEAM_MAPPING.items():
            client.subscribe(f"{ip}/pose")
            # ired_refbox publishes exploration reports here (added: the VM version never forwarded them)
            client.subscribe(f"{ip}/machine_report")
        if client == client_magenta or client == client_cyan:
            client.subscribe(GAME_STATE_TOPIC)
            client.subscribe("private/#")
            client.subscribe("public/#")
        # print (client)
        # client.subscribe("public/beacon_signal")
        print("Done")
    else:
        print(f"Connection failed with code {rc}")


def on_message(client, userdata, message):
    try:
        data = json.loads(message.payload.decode())
        topic = message.topic

        # print(topic)

        if topic == "public/game_state":
            state = data.get("state")
            phase = data.get("phase")
            for teamColor, ip in TEAM_MAPPING.items():
                if teamColor == "MAGENTA" and client == client_magenta:
                    client_refbridge.publish(f"{ip}/game_state", state)
                    client_refbridge.publish(f"{ip}/phase", phase)
                    client_refbridge.publish(f"{ip}/teamColor", teamColor)
                elif teamColor == "CYAN" and client == client_cyan:
                    client_refbridge.publish(f"{ip}/game_state", state)
                    client_refbridge.publish(f"{ip}/phase", phase)
                    client_refbridge.publish(f"{ip}/teamColor", teamColor)
        elif topic == "public/beacon_signal":
            _time = data.get("time")
            for teamColor, ip in TEAM_MAPPING.items():
                if teamColor == "MAGENTA" and client == client_magenta:
                    client_refbridge.publish(f"{ip}/time", _time["sec"])
                elif teamColor == "CYAN" and client == client_cyan:
                    client_refbridge.publish(f"{ip}/time", _time["sec"])
        elif topic.startswith("private/"):
            sub_topic = topic[len("private/"):]
            private_data = json.dumps(data)
            for teamColor, ip in TEAM_MAPPING.items():
                if teamColor == "MAGENTA" and client == client_magenta:
                    client_refbridge.publish(f"{ip}/private/{sub_topic}", private_data)
                elif teamColor == "CYAN" and client == client_cyan:
                    client_refbridge.publish(f"{ip}/private/{sub_topic}", private_data)
        elif topic.startswith(REFBRIDGE_TOPIC_PREFIX):
            print("/pose")
            topic_parts = topic.split("/")  # Split the topic by "/"
            
            if len(topic_parts) > 1 and topic_parts[1] == "pose":  # Ensure it contains "/pose"
                robot_ip = topic_parts[0]  # Extract the robot's IP from the topic

                # Find the team and robot index based on the robot's IP address
                team = None
                robot_index = None
                for index, (team_name, ip) in enumerate(TEAM_MAPPING.items(), start=1):
                    if ip == robot_ip:
                        team = team_name
                        robot_index = index  # Assign correct robot index
                        break

                if team and robot_index:
                    formatted_data = {
                        "name": f"R{robot_index}",  # Dynamically set the robot name
                        "x": data.get("x", 0),
                        "y": data.get("y", 0),
                        "yaw": data.get("yaw", 0)
                    }
                    forward_data = json.dumps(formatted_data)

                    if team == "MAGENTA":
                        client_magenta.publish(f"TEAM_MAGENTA/beacon/R{robot_index}", forward_data)
                        print(f"Forwarded /pose data from {robot_ip} (Magenta) to TEAM_MAGENTA/beacon/R{robot_index}")
                    elif team == "CYAN":
                        client_cyan.publish(f"TEAM_CYAN/beacon/R{robot_index}", forward_data)
                        print(f"Forwarded /pose data from {robot_ip} (Cyan) to TEAM_CYAN/beacon/R{robot_index}")

            # Exploration report: {"machine","x","y","yaw"} from ired_refbox -> <TEAM>/report,
            # the topic the rcll-mqtt-bridge listens on (it turns x,y into a zone and snaps yaw to 45 deg)
            elif len(topic_parts) > 1 and topic_parts[1] == "machine_report" and client == client_refbridge:
                robot_ip = topic_parts[0]
                team = next((team_name for team_name, ip in TEAM_MAPPING.items() if ip == robot_ip), None)
                report_data = json.dumps({
                    "machine": data.get("machine", ""),
                    "x": data.get("x", 0),
                    "y": data.get("y", 0),
                    "yaw": data.get("yaw", 0)
                })
                if team == "MAGENTA":
                    client_magenta.publish("TEAM_MAGENTA/report", report_data)
                    print(f"Forwarded machine report from {robot_ip} (Magenta) to TEAM_MAGENTA/report: {report_data}")
                elif team == "CYAN":
                    client_cyan.publish("TEAM_CYAN/report", report_data)
                    print(f"Forwarded machine report from {robot_ip} (Cyan) to TEAM_CYAN/report: {report_data}")


    except Exception as e:
        print(f"Error processing message: {e}")


# กำหนด Callback Functions
client_refbridge.on_connect = on_connect
client_refbridge.on_message = on_message
client_magenta.on_connect = on_connect
client_magenta.on_message = on_message
client_cyan.on_connect = on_connect
client_cyan.on_message = on_message

# เชื่อมต่อ Brokers
print("Connecting to REFBRIDGE_BROKER...")
client_refbridge.connect("refbridge_broker", PORT)

print("Connecting to Magenta_Broker...")
client_magenta.connect("magenta_broker", PORT)

print("Connecting to Cyan_Broker...")
client_cyan.connect("cyan_broker", PORT)

# รัน MQTT Clients
client_refbridge.loop_start()
client_magenta.loop_start()
client_cyan.loop_start()

try:
    while True:
        pass
except KeyboardInterrupt:
    print("Disconnecting...")
    client_refbridge.loop_stop()
    client_magenta.loop_stop()
    client_cyan.loop_stop()
    client_refbridge.disconnect()
    client_magenta.disconnect()
    client_cyan.disconnect()
