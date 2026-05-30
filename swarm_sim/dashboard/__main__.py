"""
Entry point for the SwarmSim Dashboard.

Usage:
    python -m swarm_sim.dashboard
"""

import sys
import webbrowser
import threading
import time
import uvicorn


def open_browser():
    """Wait briefly for server to start, then open browser."""
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    print("[SwarmSim] Starting dashboard server...")
    
    # Start browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run uvicorn server
    uvicorn.run(
        "swarm_sim.dashboard.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False
    )
