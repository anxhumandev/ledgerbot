"""Launch the Tessera API and Vite together. Run with the project's virtualenv."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    backend_port = os.environ.get("PORT_BACK", "8100")
    frontend_port = os.environ.get("FRONTEND_PORT", "5174")
    node = shutil.which("node")
    if not node:
        raise SystemExit("Install Node.js and run npm ci in frontend.")
    env = {**os.environ, "TESSERA_API": f"http://127.0.0.1:{backend_port}"}
    commands = [
        (root / "backend", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", backend_port]),
        (root / "frontend", [node, "node_modules/vite/bin/vite.js", "--host", "0.0.0.0", "--port", frontend_port]),
    ]
    processes = []

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for cwd, args in commands:
            processes.append(subprocess.Popen(args, cwd=cwd, env=env))
        while True:
            for process in processes:
                status = process.poll()
                if status is not None:
                    return status
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    sys.exit(main())
