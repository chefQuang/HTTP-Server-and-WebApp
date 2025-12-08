#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import json
import socket
import argparse
import sqlite3
import os

from daemon.weaprous import WeApRous

PORT = 8000  # Default port

app = WeApRous()


DB_PATH = os.path.join("db", "chat.db")

def init_db():
    if not os.path.exists("db"):
        os.makedirs("db")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    #Bảng user: Lưu tài khoản

    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')

    #Bảng peers: Lưu thông tin online của peer (gồm IP và port)
    #username làm primary key để 1 user chỉ online 1 nơi tại 1 thời điểm
    c.execute('''CREATE TABLE IF NOT EXISTS peers (username TEXT PRIMARY KEY, ip TEXT, port INTEGER, web_port INTEGER)''')

    conn.commit()
    conn.close()
    print("[DB] Database initialized at {}".format(DB_PATH))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    print("[DB] Connect Successfully")
    conn.row_factory = sqlite3.Row #Truy cập cột theo tên
    return conn


#Hàm helper để parse dữ liệu form gửi lên
def parse_from_data(body):
    if not body:
        return {}
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    body = body.strip()
    try:
        return json.loads(body)
    except ValueError:
        try:
            data = {}
            for pair in body.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    data[k] = v
            return data
        except Exception:
            pass
    except Exception as e:
        print("[Parse Error] Cannot parse body: '{}'. Error: {}".format(body, e))
    return {}
            

def get_user_from_cookie(headers):
    cookie_str = headers.get('cookie', '')
    if 'auth=' in cookie_str:
        #Format cookie: auth=username
        try:
            #Tách chuỗi cookie để lấy username
            for part in cookie_str.split(';'):
                if 'auth=' in part:
                    return part.split('=', 1)[1].strip()
        except:
            pass
    return None

@app.route('/register', methods=['POST'])
def register(headers, body):
    data = parse_from_data(body)
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return "Missing username or password", 400, {}

    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        msg = "Registered successfully user: " + username
        print("[Auth]" + msg)
        return "<html><body><h1>Success!</h1><a href='/login.html'>Go to Login</a></body></html>", 200, {}
    except sqlite3.IntegrityError:
        return "Username already exists", 409, {}
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login(headers, body):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    print ("[SampleApp] Logging in {} to {}".format(headers, body))

    data = parse_from_data(body)
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()


    print("[SampleApp] Login attempt: user={}, pass={}".format(username, password)) #Để debug thoi

    #if username == 'admin' and password == 'password':
        #response_body = "<html><body><h1>Login Successful!</h1><a href='/home'>Go to Home</a></body></html>"
        #return response_body, 200, {'Set-Cookie': 'auth=true; Path=/'}
    #else:
        #return "<html><body><h1>401 Unauthorized</h1><p>Wrong credentials</p></body></html>", 401, {}

    if user:
        print("[Auth] User logged in: {}".format(username))
        cookie_val = "auth={}; Path/".format(username)
        return (
            "", 302,
            {
                'Set-Cookie': cookie_val,
                'Location': '/home'
            }
        )
    else:
        print("[Auth] Login failed for: {}".format(username))
        return "<html><body><h1>Login Failed</h1><p>Check username/password</p></body></html>", 401, {}

@app.route('/submit-info', methods=['POST'])
def submit_info(headers, body):
    data = parse_from_data(body)
    current_user = data.get('username')
    if not current_user:
        current_user = get_user_from_cookie(headers)
    if not current_user:
        return json.dumps({"error": "Unauthorized. Please login first."}), 401, {'Content-Type': 'application/json'}
    ip = data.get('ip')
    port = data.get('port')
    web_port = data.get('web_port')
    if not ip or not port:
        return json.dumps({"error": "Missing IP or Port"}), 400, {'Content-Type': 'application/json'}

    conn = get_db_connection()
    conn.execute("REPLACE INTO peers (username, ip, port, web_port) VALUES (?, ?, ?, ?)", (current_user, ip, port, web_port))
    conn.commit()
    conn.close()
    print(f"[Tracker] Registered {current_user}: P2P={ip}:{port}, Web={web_port}")
    return json.dumps({"status": "success", "user": current_user}), 200, {'Content-Type': 'application/json'}

@app.route('/get-list', methods=['GET'])
def get_list(headers, body):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM peers").fetchall()
    conn.close

    peers = {}
    for row in rows:
        peers[row['username']] = {'ip': row['ip'], 'port': row['port'], 'web_port': row['web_port']}
    return json.dumps(peers), 200, {'Content-Type': 'application/json'}

@app.route('/logout', methods=['POST'])
def logout(headers, body):
    current_user = get_user_from_cookie(headers)
    if current_user:
        try:
            conn = get_db_connection()
            conn.execute("DELETE FROM peers WHERE username = ?", (current_user,))
            conn.commit()
            conn.close()
            print(f"[Tracker] User '{current_user}' logged out and removed from peer list.")
        except Exception as e:
            print(f"[Tracker Error] Logout DB error: {e}")
    expire_cookie = "auth=; Path=/; Expires=Thu, 01 Jan 2026 00:00:00 GMT"
    return "", 302, {'Set-Cookie': expire_cookie, 'Location': '/login.html'}

@app.route('/hello', methods=['PUT'])
def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print ("[SampleApp] ['PUT'] Hello in {} to {}".format(headers, body))


@app.route('/get-my-info', methods=['GET'])
def get_my_info(headers, body):
    current_user = get_user_from_cookie(headers)
    if not current_user:
        return json.dumps({"error": "Login first"}), 401, {}
    conn = get_db_connection()
    row = conn.execute("SELECT ip, web_port FROM peers WHERE username = ?", (current_user,)).fetchone()
    conn.close()

    if row and row['web_port']:
        engine_url = "http://{}:{}".format(row['ip'], row['web_port'])
        return json.dumps({"engine_url": engine_url}), 200, {'Content-Type': 'application/json'}
    else:
        return json.dumps({"error": "No engine found"}), 404, {'Content-Type': 'application/json'}

if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    init_db()
    parser = argparse.ArgumentParser(prog='Backend', description='', epilog='Beckend daemon')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=PORT)
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()