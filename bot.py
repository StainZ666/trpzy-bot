from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"TrpZy Bot is ONLINE")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 10000), Handler)
    print("Server running on port 10000")
    server.serve_forever()
