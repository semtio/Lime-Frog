import os
import subprocess
import sys
from pathlib import Path


REQUIRED_MODULES = ["flask", "httpx", "bs4", "lxml", "psutil"]


def ensure_dependencies():
    missing = []
    for module in REQUIRED_MODULES:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if not missing:
        return
    req_file = Path(__file__).parent / "requirements.txt"
    print("Устанавливаю зависимости...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])


def main():
    ensure_dependencies()
    from app import app  # import after installing

    port = (
        int(sys.argv[1])
        if len(sys.argv) > 1
        else int((os.environ.get("PORT") or "5000"))
    )
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
