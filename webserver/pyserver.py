#!/usr/bin/python3
import http.server
import socketserver
import threading
from datetime import datetime


class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        """Handle TCP GET request."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Hello from the HTTP server!\n\nCurrent date and time: {current_time}\n"
        self.wfile.write(message.encode('utf-8'))


class MyUDPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        """Receive UDP data and respond to it."""
        data = self.request[0].strip()
        socket = self.request[1]
        print(f"Received UDP message: {data.decode()} from {self.client_address}")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Hello from the UDP server!\n\nCurrent date and time: {current_time}\n"
        response = message.encode('utf-8')
        socket.sendto(response, self.client_address)


def start_http_server():
    """Starts HTTP server."""
    with socketserver.TCPServer(("0.0.0.0", 8080), MyHTTPRequestHandler) as httpd:
        print("HTTP server running on port 8080...\n")
        httpd.serve_forever()


def start_udp_server():
    """Starts UDP server."""
    with socketserver.UDPServer(("0.0.0.0", 9090), MyUDPRequestHandler) as udpd:
        print("UDP server running on port 9090...\n")
        udpd.serve_forever()


if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server)
    udp_thread = threading.Thread(target=start_udp_server)

    http_thread.start()
    udp_thread.start()

    udp_thread.join()
    http_thread.join()
