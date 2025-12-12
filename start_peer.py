import socket
import threading
import json
import argparse
import sys
import time
from http.cookiejar import CookieJar

try:
    from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
    from urllib.parse import urlencode
    from urllib.error import URLError, HTTPError
except ImportError:
    sys.exit("Please use Python 3")

from daemon.weaprous import WeApRous

app = WeApRous()
MY_USERNAME = ""
MY_PASSWORD = ""
MY_P2P_IP = ""
MY_P2P_PORT = 0
MY_WEB_PORT = 5000
TRACKER_URL = "http://127.0.0.1:8080"

# active_sockets: { "IP:Port": socket }
active_sockets = {}

# pending_sockets: { "IP:Port": socket }
pending_sockets = {}

# pending_info_list:
pending_info_list = []

joined_channels = []

chat_history = []

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
}

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
        return True, opener.open(req)
    except Exception as e:
        return False, e

def perform_tracker_handshake():
    print("\n[Engine] --- Handshaking with Tracker ---")
    # 1. Login
    ok, _ = send_http_request('/login', {"username": MY_USERNAME, "password": MY_PASSWORD})
    if not ok: sys.exit("[Engine] Login Failed!")
    
    # 2. Register
    reg_data = {"username": MY_USERNAME, "ip": MY_P2P_IP, "port": MY_P2P_PORT, "web_port": MY_WEB_PORT}
    ok, _ = send_http_request('/submit-info', reg_data)
    if ok: print("[Engine] Online & Registered!")
    else: sys.exit("[Engine] Registration Failed.")

def listen_to_peer(conn, peer_name, peer_key):
    """Vòng lặp lắng nghe tin nhắn SAU KHI đã kết nối thành công"""
    try:
        while True:
            data = conn.recv(4096)
            if not data: break
            msg = data.decode('utf-8')
            
            if msg.startswith("MSG:"):
                content = msg.split(":", 1)[1]
                chat_history.append({"sender": peer_name, "msg": content, "type": "received", "channel": "private"})
                print(f"[Private] {peer_name}: {content}")

            elif msg.startswith("CHN:"):
                try:
                    parts = msg.split(":", 2)
                    if len(parts) == 3:
                        _, ch_name, content = parts
                        if ch_name in joined_channels:
                            chat_history.append({"sender": peer_name, "msg": content, "type": "received", "channel": ch_name})
                            print(f"[Channel {ch_name}] {peer_name}: {content}")
                except: pass
            
            elif msg.startswith("BCAST:"):
                try:
                    content = msg.split(":", 1)[1]
                    chat_history.append({"sender": peer_name, "msg": content, "type": "received", "channel": "broadcast"})
                    print(f"[Broadcast] {peer_name}: {content}")
                except: pass
    except:
        pass
    finally:
        print(f"[P2P] Disconnected from {peer_name}")
        conn.close()
        if peer_key in active_sockets:
            del active_sockets[peer_key]

def handle_incoming_tcp(conn, addr):
    """Xử lý kết nối đầu vào (Handshake)"""
    remote_ip = addr[0]
    try:
        data = conn.recv(4096)
        if not data: return
        msg = data.decode('utf-8')

        if msg.startswith("REQ:"):
            _, name, port_str = msg.split(':')
            remote_port = int(port_str)
            peer_key = f"{remote_ip}:{remote_port}"
            
            print(f"[P2P] Incoming Request from {name} ({peer_key})")
            
            pending_sockets[peer_key] = conn
            pending_info_list.append({"ip": remote_ip, "port": remote_port, "name": name})
            return

        elif msg.startswith("ACK:"):
            _, name, port_str = msg.split(':')
            remote_port = int(port_str)
            peer_key = f"{remote_ip}:{remote_port}"
            
            print(f"[P2P] {name} Accepted connection!")
            
            active_sockets[peer_key] = conn
            
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
        sys.exit(f"[P2P Bind Error] {e}")


@app.route('/api/connect', methods=['POST'])
def api_connect(headers, body):
    """Gửi yêu cầu kết nối (REQ)"""
    try:
        d = json.loads(body)
        target_ip = d['ip']
        target_port = int(d['port'])
        key = f"{target_ip}:{target_port}"

        if key in active_sockets:
            return json.dumps({"status": "already_connected"}), 200, CORS_HEADERS

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((target_ip, target_port))
        
        req_msg = f"REQ:{MY_USERNAME}:{MY_P2P_PORT}"
        s.sendall(req_msg.encode('utf-8'))
        
        t = threading.Thread(target=handle_incoming_tcp, args=(s, (target_ip, target_port)))
        t.daemon = True
        t.start()

        return json.dumps({"status": "request_sent"}), 200, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/api/pending', methods=['GET'])
def api_pending(headers, body):
    """Lấy danh sách chờ duyệt"""
    return json.dumps(pending_info_list), 200, CORS_HEADERS

@app.route('/api/accept', methods=['POST'])
def api_accept(headers, body):
    """Chấp nhận kết nối (Gửi ACK)"""
    try:
        d = json.loads(body)
        ip = d['ip']
        port = int(d['port'])
        name = d.get('name', 'Unknown')
        key = f"{ip}:{port}"
        
        if key in pending_sockets:
            conn = pending_sockets[key]
            
            ack_msg = f"ACK:{MY_USERNAME}:{MY_P2P_PORT}"
            conn.sendall(ack_msg.encode('utf-8'))
            
            active_sockets[key] = conn
            del pending_sockets[key]
            
            global pending_info_list
            pending_info_list = [p for p in pending_info_list if not (p['ip']==ip and p['port']==port)]
            
            # Start Listening
            t = threading.Thread(target=listen_to_peer, args=(conn, name, key))
            t.daemon = True
            t.start()
            
            return json.dumps({"status": "accepted"}), 200, CORS_HEADERS
        return json.dumps({"error": "Request not found"}), 404, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/api/send_peer', methods=['POST'])
def send_peer(headers, body):
    """Gửi tin nhắn riêng (MSG:)"""
    try:
        d = json.loads(body)
        key = f"{d['ip']}:{d['port']}"
        msg = d['msg']
        
        if key in active_sockets:
            payload = f"MSG:{msg}".encode('utf-8')
            active_sockets[key].sendall(payload)
            chat_history.append({"sender": "Me", "msg": msg, "type": "sent", "channel": "private"})
            return json.dumps({"status": "sent"}), 200, CORS_HEADERS
        return json.dumps({"error": "Not connected"}), 404, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/broadcast-peer', methods=['POST'])
def broadcast_peer(headers, body):
    """
    API Broadcast: Gửi gói BCAST cho tất cả mọi người
    """
    try:
        data = json.loads(body)
        msg = data.get('msg', '')
        
        full_msg = f"BCAST:{msg}".encode('utf-8')
        
        count = 0
        for s in active_sockets.values():
            try:
                s.sendall(full_msg)
                count += 1
            except: pass
        
        chat_history.append({"sender": "Me", "msg": f"{msg}", "type": "sent", "channel": "broadcast"})
        return json.dumps({"status": "ok", "count": count}), 200, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS

@app.route('/api/send_channel', methods=['POST'])
def send_channel(headers, body):
    """Gửi tin nhắn kênh (CHN:) - Broadcast cho tất cả kết nối"""
    try:
        d = json.loads(body)
        ch_name = d.get('channel')
        msg = d.get('msg')
        
        payload = f"CHN:{ch_name}:{msg}".encode('utf-8')
        
        count = 0
        for s in active_sockets.values():
            try:
                s.sendall(payload)
                count += 1
            except: pass
            
        chat_history.append({"sender": "Me", "msg": msg, "type": "sent", "channel": ch_name})
        return json.dumps({"status": "sent", "count": count}), 200, CORS_HEADERS
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, CORS_HEADERS


@app.route('/api/channels/join', methods=['POST'])
def join_channel(headers, body):
    d = json.loads(body)
    ch = d.get('name')
    if ch and ch not in joined_channels:
        joined_channels.append(ch)
    return json.dumps({"status": "joined", "channels": joined_channels}), 200, CORS_HEADERS

@app.route('/api/channels/my', methods=['GET'])
def my_channels(headers, body):
    return json.dumps(joined_channels), 200, CORS_HEADERS

@app.route('/api/messages', methods=['GET'])
def get_msgs(headers, body): 
    return json.dumps(chat_history), 200, CORS_HEADERS

@app.route('/api/connect', methods=['OPTIONS'])
def o1(headers, body): return "", 200, CORS_HEADERS
@app.route('/api/send_peer', methods=['OPTIONS'])
def o2(headers, body): return "", 200, CORS_HEADERS
@app.route('/api/send_channel', methods=['OPTIONS'])
def o3(headers, body): return "", 200, CORS_HEADERS
@app.route('/api/accept', methods=['OPTIONS'])
def o4(headers, body): return "", 200, CORS_HEADERS
@app.route('/api/channels/join', methods=['OPTIONS'])
def o5(headers, body): return "", 200, CORS_HEADERS

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