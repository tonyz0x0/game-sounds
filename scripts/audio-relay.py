#!/usr/bin/env python3
"""Audio relay server for playing game sounds on a local Mac from a remote server.

Receives audio files over HTTP POST and plays them with macOS `afplay`.
Designed to run on a local MacBook while Claude Code runs on a remote server,
with an SSH reverse tunnel bridging the two.

Usage:
    python3 audio-relay.py              # Start on default port 18923
    python3 audio-relay.py --port 9999  # Custom port

SSH tunnel (on your Mac):
    ssh -R 18923:localhost:18923 remote-server
"""
import argparse
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _play_and_cleanup(path, vol):
    """Play audio file and delete temp file when done."""
    try:
        subprocess.run(["afplay", "-v", vol, path])
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class AudioHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        """Receive an audio file and play it with afplay."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 10 * 1024 * 1024:  # 10MB limit
            self.send_response(413)
            self.end_headers()
            return
        data = self.rfile.read(content_length)
        ext = self.headers.get("X-Ext", ".mp3")
        if ext not in (".mp3", ".wav", ".ogg"):
            ext = ".mp3"
        vol = self.headers.get("X-Vol", "0.5")
        try:
            vol = str(max(0.0, min(1.0, float(vol))))
        except ValueError:
            vol = "0.5"
        fd, path = tempfile.mkstemp(suffix=ext)
        try:
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
            threading.Thread(
                target=_play_and_cleanup, args=(path, vol), daemon=True
            ).start()
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # Suppress request logging


def main():
    parser = argparse.ArgumentParser(description="Audio relay for remote game sounds")
    parser.add_argument("--port", type=int, default=18923, help="Port to listen on")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), AudioHandler)
    print(f"Audio relay listening on localhost:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
