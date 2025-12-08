import socket
import threading
import json
import argparse
import sys
import time

try:
    from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
    from urllib.parse import urlencode
    from urllib.error import URLError, HTTPError
    from http.cookiejar import CookieJar
except ImportError:
    sys.exit("Please use Python 3")

from daemon.weaprous import WeApRous

# --- CONFIG ---
app = WeApRous()
MY_USERNAME = ""
MY_PASSWORD = ""
MY_P2P_IP = ""
MY_P2P_PORT = 0
MY_WEB_PORT = 5000
TRACKER_URL = "http://127.0.0.1:8080"

# active_sockets: { "IP:Port": socket } -> Connected & Ready to chat
active_sockets = {}

# pending_sockets: { "IP:Port": socket } -> Waiting for user to Accept
pending_sockets = {} 

# pending_info: [ {"ip":, "port":, "name":} ] -> Info to show on UI
pending_info_list = []

chat_history = []

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

#HTTP Client
cookie_jar = CookieJar()
opener = build_opener(HTTPCookieProcessor(cookie_jar))

def send_http_request(endpoint, data=None):
    url = "{}{}".format(TRACKER_URL, endpoint)
    try:
        if data:
            json_data = json.dumps(data).encode('utf-8')
            req = Request(url, data=json_data, headers={'Content-Type': 'application/json'})
        else:
            req = Request(url)
        response = opener.open(req)
        return True, response
    except Exception as e:
        return False, e

def perform_tracker_handshake():
    print("\n[Engine] --- Handshaking with Tracker ---")
    success, _ = send_http_request('/login', {"username": MY_USERNAME, "password": MY_PASSWORD})
    if not success:
        print("[Engine] Login Failed!")
        sys.exit(1)
    
    reg_data = {
        "username": MY_USERNAME,
        "ip": MY_P2P_IP,
        "port": MY_P2P_PORT,
        "web_port": MY_WEB_PORT
    }
    success, _ = send_http_request('/submit-info', reg_data)
    if success:
        print("[Engine] Registered & Online.")
    else:
        print("[Engine] Registration Failed.")
        sys.exit(1)

# --- CORE P2P LOGIC ---

def listen_to_peer(conn, peer_name, peer_key):
    """Loop to receive chat messages AFTER handshake is done"""
    try:
        while True:
            data = conn.recv(4096)
            if not data: break
            msg = data.decode('utf-8')
            
            # Format: "MSG:Content"
            if msg.startswith("MSG:"):
                content = msg.split(":", 1)[1]
                chat_history.append({"sender": peer_name, "msg": content, "type": "received"})
                print(f"\n[Chat] {peer_name}: {content}")
    except:
        pass
    finally:
        conn.close()
        if peer_key in active_sockets:
            del active_sockets[peer_key]

def handle_incoming_tcp(conn, addr):
    """
    Handle initial connection.
    Expects REQ or ACK packet.
    """
    remote_ip = addr[0]
    
    try:
        # Read the FIRST packet only
        data = conn.recv(4096)
        if not data: return
        msg = data.decode('utf-8')

        # CASE 1: Receive Connection Request (REQ)
        if msg.startswith("REQ:"):
            # Format: "REQ:Name:Port"
            _, name, port_str = msg.split(':')
            remote_port = int(port_str)
            peer_key = f"{remote_ip}:{remote_port}"
            
            print(f"[P2P] Incoming Request from {name} ({peer_key})")
            
            # Store in Pending list
            pending_sockets[peer_key] = conn
            pending_info_list.append({"ip": remote_ip, "port": remote_port, "name": name})
            
            # DO NOT start listening loop yet. Wait for API Accept.
            return

        # CASE 2: Receive Acknowledgement (ACK) - They accepted us!
        elif msg.startswith("ACK:"):
            # Format: "ACK:Name:Port"
            _, name, port_str = msg.split(':')
            remote_port = int(port_str)
            peer_key = f"{remote_ip}:{remote_port}"
            
            print(f"[P2P] {name} Accepted your request!")
            
            active_sockets[peer_key] = conn
            chat_history.append({"sender": "System", "msg": f"Connected with {name}", "type": "received"})
            
            # Start listener loop
            t = threading.Thread(target=listen_to_peer, args=(conn, name, peer_key))
            t.daemon = True
            t.start()

    except Exception as e:
        print(f"[P2P Error] {e}")
        conn.close()

def start_p2p_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((MY_P2P_IP, MY_P2P_PORT))
        s.listen(5)
        print(f"[P2P] Listening at {MY_P2P_IP}:{MY_P2P_PORT}")
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_incoming_tcp, args=(conn, addr))
            t.daemon = True
            t.start()
    except Exception as e:
        print(f"[P2P Error] Bind failed: {e}")
        sys.exit(1)

#Local API

@app.route('/api/connect', methods=['POST'])
def api_connect(headers, body):
    """Step 1: Send Request"""
    try:
        data = json.loads(body)
        target_ip = data['ip']
        target_port = int(data['port'])
        key = f"{target_ip}:{target_port}"

        if key in active_sockets:
            return json.dumps({"status": "already_connected"}), 200, CORS_HEADERS

        # Open socket and send REQ
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((target_ip, target_port))
        
        req_msg = f"REQ:{MY_USERNAME}:{MY_P2P_PORT}"
        s.sendall(req_msg.encode('utf-8'))
        
        # We assume active immediately for the sender side to wait for ACK
        # But for simplicity, we just wait for ACK in handle_incoming logic? 
        # Actually, for the initiator, we need to listen on THIS socket for the ACK.
        
        # Start a thread to wait for ACK on this specific socket
        t = threading.Thread(target=handle_incoming_tcp, args=(s, (target_ip, target_port)))
        t.daemon = True
        t.start()

        return json.dumps({"status": "request_sent"}), 200, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/api/pending', methods=['GET'])
def api_pending(headers, body):
    """UI Polls this to show notifications"""
    return json.dumps(pending_info_list), 200, CORS_HEADERS

@app.route('/api/accept', methods=['POST'])
def api_accept(headers, body):
    """Step 2: Accept Request"""
    try:
        data = json.loads(body)
        target_ip = data['ip']
        target_port = int(data['port'])
        name = data.get('name', 'Unknown')
        
        peer_key = f"{target_ip}:{target_port}"
        
        if peer_key in pending_sockets:
            conn = pending_sockets[peer_key]
            
            # Send ACK
            ack_msg = f"ACK:{MY_USERNAME}:{MY_P2P_PORT}"
            conn.sendall(ack_msg.encode('utf-8'))
            
            # Move to active
            active_sockets[peer_key] = conn
            
            # Remove from pending
            del pending_sockets[peer_key]
            # Remove from info list (filter out)
            global pending_info_list
            pending_info_list = [p for p in pending_info_list if not (p['ip']==target_ip and p['port']==target_port)]
            
            # Start Listener
            t = threading.Thread(target=listen_to_peer, args=(conn, name, peer_key))
            t.daemon = True
            t.start()
            
            return json.dumps({"status": "accepted"}), 200, CORS_HEADERS
        else:
            return json.dumps({"error": "Request not found"}), 404, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/api/send', methods=['POST'])
def api_send(headers, body):
    """Step 3: Chat"""
    try:
        data = json.loads(body)
        msg = data.get('msg', '')
        target_ip = data.get('ip')
        target_port = data.get('port')
        
        full_msg = f"MSG:{msg}" # Use MSG prefix
        target_key = f"{target_ip}:{target_port}"
        
        if target_key in active_sockets:
            conn = active_sockets[target_key]
            conn.sendall(full_msg.encode('utf-8'))
            chat_history.append({"sender": "Me", "msg": f"(to {target_ip}) {msg}", "type": "sent"})
            return json.dumps({"status": "sent"}), 200, CORS_HEADERS
        else:
            return json.dumps({"error": "Not connected"}), 404, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers, body):
    try:
        data = json.loads(body)
        msg = data.get('msg', '')
        full_msg = f"MSG:(Broadcast) {msg}"
        
        count = 0
        for key, s in active_sockets.items():
            try:
                s.sendall(full_msg.encode('utf-8'))
                count += 1
            except: pass
        
        chat_history.append({"sender": "Me", "msg": f"(Broadcast) {msg}", "type": "sent"})
        return json.dumps({"status": "ok", "count": count}), 200, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/api/messages', methods=['GET'])
def get_msgs(headers, body): 
    return json.dumps(chat_history), 200, CORS_HEADERS

# OPTIONS handlers
@app.route('/api/connect', methods=['OPTIONS'])
def o1(h, b): return "", 200, CORS_HEADERS
@app.route('/api/send', methods=['OPTIONS'])
def o2(h, b): return "", 200, CORS_HEADERS
@app.route('/broadcast-peer', methods=['OPTIONS'])
def o3(h, b): return "", 200, CORS_HEADERS
@app.route('/api/accept', methods=['OPTIONS'])
def o4(h, b): return "", 200, CORS_HEADERS
@app.route('/api/pending', methods=['OPTIONS'])
def o5(h, b): return "", 200, CORS_HEADERS

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--server-ip', required=True)
    parser.add_argument('--server-port', type=int, required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--web-port', type=int, default=5000)
    args = parser.parse_args()

    MY_USERNAME = args.username
    MY_PASSWORD = args.password
    MY_P2P_IP = args.server_ip
    MY_P2P_PORT = args.server_port
    MY_WEB_PORT = args.web_port 

    t = threading.Thread(target=start_p2p_server)
    t.daemon = True
    t.start()

    time.sleep(1)
    perform_tracker_handshake()

    print(f"\n[Engine] Ready. Web Control at Port {MY_WEB_PORT}")
    app.prepare_address('0.0.0.0', MY_WEB_PORT)
    app.run()