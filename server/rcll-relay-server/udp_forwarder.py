import socket

# RefBox public-peer settings
LISTEN_IP = "0.0.0.0"   # Listen on all interfaces inside Docker
LISTEN_PORT = 4444       # Public-peer send-port

# Destination computers
DESTINATIONS = [
    ("127.0.0.1", 4500),  # magenta_bridge (single-host; VM: Refbox-Bridge IP)
    ("127.0.0.1", 4501)   # cyan_bridge (single-host; VM: Refbox-Bridge IP)
]

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((LISTEN_IP, LISTEN_PORT))

print(f"Listening for UDP packets on {LISTEN_IP}:{LISTEN_PORT}")

while True:
    data, addr = sock.recvfrom(4096)  # Receive data from RefBox
    print(f"Received from {addr}: {data}")

    # Forward to each destination
    for dest_ip, dest_port in DESTINATIONS:
        sock.sendto(data, (dest_ip, dest_port))
        print(f"Forwarded to {dest_ip}:{dest_port}")


