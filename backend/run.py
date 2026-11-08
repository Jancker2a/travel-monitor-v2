"""
Dual-stack server runner for Travel Monitor 2.0.
Listens simultaneously on IPv4 (0.0.0.0 / 127.0.0.1) and IPv6 (:: / ::1),
ensuring seamless compatibility with macOS Chrome/Safari ('localhost')
and standard IPv4 clients.
"""
import socket
import sys
import uvicorn
from app.main import app

def create_dual_stack_socket(port: int = 8000):
    try:
        # Create IPv6 socket with dual-stack enabled (IPV6_V6ONLY=0)
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass
        sock.bind(("::", port))
        sock.listen(2048)
        return [sock]
    except Exception:
        # Fallback to standard IPv4 if IPv6 dual-stack is unsupported by OS
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.listen(2048)
        return [sock]

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    sockets = create_dual_stack_socket(port)
    config = uvicorn.Config(
        app,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    server.run(sockets=sockets)
