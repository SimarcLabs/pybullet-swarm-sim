"""FastAPI Server for SwarmSim Dashboard."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Dict

import numpy as np
import plotly.graph_objects as go
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="SwarmSim Dashboard")

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory job tracker
JOBS: Dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open(STATIC_DIR / "index.html", "r") as f:
        return f.read()


@app.get("/algorithms")
async def get_algorithms():
    return [
        {
            "id": "flocking",
            "name": "Reynolds Boids",
            "icon": "fa-solid fa-crow",
            "desc": "Separation · Alignment · Cohesion"
        },
        {
            "id": "formation",
            "name": "Formation Flight",
            "icon": "fa-solid fa-fighter-jet",
            "desc": "Track geometric formations",
            "has_shapes": True
        },
        {
            "id": "hover",
            "name": "Hover Swarm",
            "icon": "fa-solid fa-location-dot",
            "desc": "Fixed-point station keeping"
        },
        {
            "id": "pso",
            "name": "PSO Search",
            "icon": "fa-solid fa-magnifying-glass-chart",
            "desc": "Particle Swarm Optimization"
        },
        {
            "id": "aco",
            "name": "ACO Path Planning",
            "icon": "fa-solid fa-bug",
            "desc": "Ant Colony pheromone trails"
        },
        {
            "id": "consensus",
            "name": "Consensus",
            "icon": "fa-solid fa-network-wired",
            "desc": "Distributed rendezvous & coverage"
        },
        {
            "id": "custom",
            "name": "Custom Upload",
            "icon": "fa-solid fa-file-arrow-up",
            "desc": "Upload your own algorithm .py file",
            "is_custom": True
        }
    ]


@app.post("/run")
async def run_simulation(
    algo: str = Form(...),
    drones: int = Form(...),
    duration: float = Form(...),
    formation_type: str = Form("v"),
    custom_file: UploadFile = File(None)
):
    job_id = str(uuid.uuid4())[:8]
    
    # Save custom file if provided
    custom_path = ""
    if algo == "custom" and custom_file is not None:
        upload_dir = Path("results") / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        custom_path = upload_dir / custom_file.filename
        with open(custom_path, "wb") as buffer:
            shutil.copyfileobj(custom_file.file, buffer)
    
    # Spawn runner.py subprocess
    runner_path = Path(__file__).parent / "runner.py"
    
    cmd = [
        sys.executable, str(runner_path),
        "--algo", algo,
        "--drones", str(drones),
        "--duration", str(duration),
        "--job-id", job_id,
        "--formation-type", formation_type
    ]
    
    if custom_path:
        cmd.extend(["--custom-algo", str(custom_path)])
        
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1  # line buffered
    )
    
    JOBS[job_id] = {
        "process": process,
        "status": "running"
    }
    
    return {"job_id": job_id}


@app.get("/stream/{job_id}")
async def stream_logs(job_id: str):
    if job_id not in JOBS:
        return {"error": "Job not found"}
        
    process = JOBS[job_id]["process"]
    
    async def log_generator():
        while True:
            # Non-blocking read would be ideal, but for simplicity in thread:
            line = await asyncio.to_thread(process.stdout.readline)
            if not line:
                break
                
            line = line.strip()
            if line:
                if line.startswith("PROGRESS:"):
                    pct = line.split(":")[1]
                    yield f"event: progress\ndata: {pct}\n\n"
                else:
                    yield f"data: {line}\n\n"
                    
        process.wait()
        JOBS[job_id]["status"] = "completed"
        yield "event: done\ndata: complete\n\n"
        
    return StreamingResponse(log_generator(), media_type="text/event-stream")


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    res_dir = Path("results") / job_id
    json_path = res_dir / "metrics.json"
    npz_path = res_dir / "telemetry.npz"
    manifest_path = res_dir / "manifest.json"
    
    if not json_path.exists() or not npz_path.exists() or not manifest_path.exists():
        return {"error": "Results not ready or failed"}
        
    with open(json_path, "r") as f:
        metrics_data = json.load(f)
        
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        
    metrics = {
        "algo": manifest.get("algo", "Unknown"),
        "num_drones": manifest.get("num_drones", 0),
        "duration": manifest.get("duration", 0),
        "health_score": metrics_data.get("health_score", 0.0),
        "detailed_metrics": metrics_data.get("metrics", {}),
        "emergence": metrics_data.get("emergence", [])
    }
        
    # Generate Plotly JSON for 3D trajectory
    data = np.load(npz_path)
    positions = data["positions"]  # (total_steps, num_drones, 3)
    num_steps = positions.shape[0]
    num_drones = positions.shape[1]
    
    fig = go.Figure()
    
    colors = [
        '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e', 
        '#10b981', '#06b6d4', '#0ea5e9', '#3b82f6', '#6366f1', 
        '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e'
    ]
    
    for i in range(num_drones):
        x = positions[:, i, 0]
        y = positions[:, i, 1]
        z = positions[:, i, 2]
        c = colors[i % len(colors)]
        
        # Trajectory line
        fig.add_trace(go.Scatter3d(
            x=x, y=y, z=z,
            mode='lines',
            name=f'Drone {i}',
            line=dict(color=c, width=3)
        ))
        
        # Start marker (Circle)
        fig.add_trace(go.Scatter3d(
            x=[x[0]], y=[y[0]], z=[z[0]],
            mode='markers',
            name=f'Drone {i} Start',
            marker=dict(color=c, size=5, symbol='circle'),
            showlegend=False
        ))
        
        # End marker (Diamond)
        fig.add_trace(go.Scatter3d(
            x=[x[-1]], y=[y[-1]], z=[z[-1]],
            mode='markers',
            name=f'Drone {i} End',
            marker=dict(color=c, size=6, symbol='diamond'),
            showlegend=False
        ))
        
    fig.update_layout(
        margin=dict(l=0, r=0, b=0, t=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#9ca3af'),
        scene=dict(
            xaxis=dict(showbackground=False, gridcolor='#374151', zerolinecolor='#4b5563', title='X (m)'),
            yaxis=dict(showbackground=False, gridcolor='#374151', zerolinecolor='#4b5563', title='Y (m)'),
            zaxis=dict(showbackground=False, gridcolor='#374151', zerolinecolor='#4b5563', title='Z (m)'),
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
        ),
        legend=dict(
            yanchor="top", y=0.99,
            xanchor="left", x=0.01,
            bgcolor="rgba(17, 24, 39, 0.8)",
            font=dict(color="#f3f4f6")
        )
    )
    
    plotly_json = json.loads(fig.to_json())
    
    return {
        "metrics": metrics,
        "plotly_data": plotly_json
    }
