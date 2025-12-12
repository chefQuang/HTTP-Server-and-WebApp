#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.
PROXY_PASS = {
    "127.0.0.1:8080": ('127.0.0.1', 9000),
    "app1.local": ('127.0.0.1', 9001),
    "app2.local": ('127.0.0.1', 9002),
}


def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                  fails, returns a 404 Not Found response.
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        backend.connect((host, port))
        #backend.sendall(request.encode())
        backend.sendall(request)
        response = b""
        while True:
            #chunk = backend.recv(4096)
            chunk = backend.recv(8192)
            if not chunk:
                break
            response += chunk
        return response
    except socket.error as e:
      print("Socket error: {}".format(e))
      return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode('utf-8')


def resolve_routing_policy(hostname, routes, path=""):
    """
    Handles an routing policy to return the matching proxy_pass.
    It determines the target backend to forward the request to.

    :params host (str): IP address of the request target server.
    :params port (int): port number of the request target server.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    print(hostname)
    proxy_map, policy = routes.get(hostname,('127.0.0.1:9000','round-robin'))
    print (proxy_map)
    print (policy)

    proxy_host = '127.0.0.1'
    proxy_port = '9000'
    #if isinstance(proxy_map, list):
        #if len(proxy_map) == 0:
            #print("[Proxy] Emtpy resolved routing of hostname {}".format(hostname))
            #print ("Empty proxy_map result")
            # TODO: implement the error handling for non mapped host
            #       the policy is design by team, but it can be 
            #       basic default host in your self-defined system
            # Use a dummy host to raise an invalid connection
            #proxy_host = '192.168.102.100'

    #CODE CŨ

    app_keywords = ['/login', '/chat', 'user', '/register', '/get-list', '/submit-info', '/logout', '/get-my-info', '/channels/create', '/channels/list', '/channels']
    if any(keyword in path for keyword in app_keywords):
        print("[Routing] Path '{}' detected -> WebApp (8000)".format(path))
        return '127.0.0.1', 8000

    if hostname in routes:
        proxy_map, policy = routes[hostname]
        if isinstance(proxy_map, list) and len(proxy_map) > 0:
            target = proxy_map[0]
            if '://' in target:
                target = target.split(':')
                proxy_host = parts[0]
                proxy_port = parts[1].strip(';/')

    return proxy_host, proxy_port

def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    matches the hostname against known routes. In the matching
    condition,it forwards the request to the appropriate backend.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): port number of the proxy server.
    :params conn (socket.socket): client connection socket.
    :params addr (tuple): client address (IP, port).
    :params routes (dict): dictionary mapping hostnames and location.
    """

    #request = conn.recv(1024).decode()

    # Extract hostname
    #for line in request.splitlines():
        #if line.lower().startswith('host:'):
            #hostname = line.split(':', 1)[1].strip()

    #print("[Proxy] {} at Host: {}".format(addr, hostname))

    # Resolve the matching destination in routes and need conver port
    # to integer value
    #resolved_host, resolved_port = resolve_routing_policy(hostname, routes)
    #try:
        #resolved_port = int(resolved_port)
    #except ValueError:
        #print("Not a valid integer")

    #if resolved_host:
        #print("[Proxy] Host name {} is forwarded to {}:{}".format(hostname,resolved_host, resolved_port))
        #response = forward_request(resolved_host, resolved_port, request)        
    #else:
        #response = (
            #"HTTP/1.1 404 Not Found\r\n"
            #"Content-Type: text/plain\r\n"
            #"Content-Length: 13\r\n"
            #"Connection: close\r\n"
            #"\r\n"
            #"404 Not Found"
        #).encode('utf-8')
    #conn.sendall(response)
    #conn.close()

    try:
        # 1. Nhận dữ liệu (Raw bytes)
        request_data = conn.recv(4096)
        if not request_data:
            conn.close()
            return

        # 2. Parse Header để lấy Hostname
        path = "/"
        hostname = ""

        try:
            # Decode header (không decode body)
            header_str = request_data.decode('utf-8', errors='ignore')
            lines = header_str.splitlines()
            if len(lines) > 0:
                request_line = lines[0]
                method, path, _ = request_line.split()
            else:
                conn.close()
                return

            if path == '/' or path == '/index.html':
                print("[Proxy] Root accessed -> Redirecting to /register.html")
                response = (
                    "HTTP/1.1 302 Found\r\n"
                    "Location: /register.html\r\n"
                    "Content-Length: 0\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                ).encode('utf-8')
                conn.sendall(response)
                conn.close()
                return
            # Lấy dòng đầu tiên để log (ví dụ: GET /index.html HTTP/1.1)
            #request_line = lines[0]
             
            for line in lines:
                if line.lower().startswith('host:'):
                    hostname = line.split(':', 1)[1].strip()
                    break
            
            if ':' in hostname:
                hostname = hostname.split(':')[0]

        except Exception:
            conn.close()
            return

        print("[Proxy] {} requesting {} | Host: {}".format(addr, request_line, hostname))

        target_host, target_port = resolve_routing_policy(hostname, routes, path)
        
        try:
            target_port = int(target_port)
        except ValueError:
            target_port = 9000

        # Gọi hàm forward
        response = forward_request(target_host, target_port, request_data)
        conn.sendall(response)

    except Exception as e:
        print("[Proxy] Error: {}".format(e))
    finally:
        conn.close()

def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections. 

    The process dinds the proxy server to the specified IP and port.
    In each incomping connection, it accepts the connections and
    spawns a new thread for each client using `handle_client`.
 

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.

    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on IP {} port {}".format(ip,port))
        while True:
            conn, addr = proxy.accept()
            #
            #  TODO: implement the step of the client incomping connection
            #        using multi-thread programming with the
            #        provided handle_client routine
            #
            #Tạo thread cho các client nè
            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes)
            )
            client_thread.daemon = True
            client_thread.start()
    except socket.error as e:
      print("Socket error: {}".format(e))

def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)
