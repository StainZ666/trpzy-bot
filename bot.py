from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

def run():
    server = HTTPServer(("0.0.0.0", 10000), BaseHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run).start()

print("Server running")
