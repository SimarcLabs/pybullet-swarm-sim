"""FastAPI Server for SwarmSim Dashboard."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time as _time
import uuid
from pathlib import Path
from typing import Dict, List

import numpy as np
import plotly.graph_objects as go
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="SwarmSim Dashboard")

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
ASSETS_DIR = Path(__file__).parent.parent / "assets"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

# In-memory job tracker
JOBS: Dict[str, dict] = {}

# Run history — persisted to results/history.json
HISTORY_PATH = Path("results") / "history.json"


def _load_history() -> List[dict]:
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, "r") as f:
            return json.load(f)
    return []


def _save_history(history: List[dict]):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

# Palette shared across all Plotly charts
DRONE_COLORS = [
    '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
    '#10b981', '#06b6d4', '#0ea5e9', '#3b82f6', '#6366f1',
    '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e'
]

PLOTLY_DARK_LAYOUT = dict(
    margin=dict(l=0, r=0, b=0, t=0),
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#9ca3af', family='Inter, Arial, sans-serif'),
    legend=dict(
        yanchor="top", y=0.99,
        xanchor="left", x=0.01,
        bgcolor="rgba(21, 21, 21, 0.9)",
        font=dict(color="#f3f4f6", size=10),
        bordercolor="#444444",
        borderwidth=1,
    ),
    xaxis=dict(gridcolor='#333', zerolinecolor='#444', color='#888'),
    yaxis=dict(gridcolor='#333', zerolinecolor='#444', color='#888'),
)


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


# ─────────────────────────────────────────────────────────────────────────────
# Scenario presets — one-click demo configurations
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/presets")
async def get_presets():
    return [
        {
            "id": "search_rescue",
            "name": "Search & Rescue",
            "icon": "fa-solid fa-magnifying-glass-location",
            "desc": "PSO-driven coverage sweep across a 10×10 m area",
            "algo": "pso",
            "drones": 12,
            "duration": 15,
            "formation_type": "v",
            "color": "#22c55e",
        },
        {
            "id": "convoy_escort",
            "name": "Convoy Escort",
            "icon": "fa-solid fa-truck-fast",
            "desc": "V-formation following a forward trajectory",
            "algo": "formation",
            "drones": 8,
            "duration": 20,
            "formation_type": "v",
            "color": "#06b6d4",
        },
        {
            "id": "perimeter_defense",
            "name": "Perimeter Defense",
            "icon": "fa-solid fa-shield-halved",
            "desc": "Ring formation around a central asset",
            "algo": "formation",
            "drones": 10,
            "duration": 15,
            "formation_type": "ring",
            "color": "#8b5cf6",
        },
        {
            "id": "flock_migration",
            "name": "Flock Migration",
            "icon": "fa-solid fa-feather-pointed",
            "desc": "Reynolds Boids with 20 agents in open space",
            "algo": "flocking",
            "drones": 20,
            "duration": 15,
            "formation_type": "v",
            "color": "#f59e0b",
        },
        {
            "id": "helix_ascent",
            "name": "Helix Ascent",
            "icon": "fa-solid fa-dna",
            "desc": "Spiral formation climbing through 3D space",
            "algo": "formation",
            "drones": 10,
            "duration": 15,
            "formation_type": "helix",
            "color": "#ec4899",
        },
        {
            "id": "consensus_rendezvous",
            "name": "Consensus Rendezvous",
            "icon": "fa-solid fa-bullseye",
            "desc": "Distributed agents converging to a common point",
            "algo": "consensus",
            "drones": 15,
            "duration": 12,
            "formation_type": "v",
            "color": "#ef4444",
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Run history
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/history")
async def get_history():
    return _load_history()


@app.delete("/history/{job_id}")
async def delete_history_entry(job_id: str):
    history = _load_history()
    history = [h for h in history if h.get("job_id") != job_id]
    _save_history(history)
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Comparison endpoint — radar chart from multiple job IDs
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/compare")
async def compare_runs(ids: str):
    """Compare multiple runs. Query: /compare?ids=abc,def,ghi"""
    job_ids = [j.strip() for j in ids.split(",") if j.strip()]
    if not job_ids:
        return {"error": "No job IDs provided"}

    runs = []
    categories = ["Coverage", "Cohesion", "Connectivity", "Safety"]
    metric_keys = ["CoverageMetric", "CohesionMetric", "ConnectivityMetric", "CollisionRateMetric"]

    for jid in job_ids:
        res_dir = Path("results") / jid
        json_path = res_dir / "metrics.json"
        manifest_path = res_dir / "manifest.json"
        if not json_path.exists() or not manifest_path.exists():
            continue
        with open(json_path) as f:
            md = json.load(f)
        with open(manifest_path) as f:
            mf = json.load(f)

        detailed = md.get("metrics", {})
        values = [round(float(detailed.get(k, 0)) * 100, 1) for k in metric_keys]
        runs.append({
            "job_id": jid,
            "label": f"{mf.get('algo', '?').upper()} · {mf.get('num_drones', '?')}d",
            "health": round(md.get("health_score", 0) * 100, 1),
            "values": values,
        })

    if not runs:
        return {"error": "No valid runs found"}

    radar_colors = ["#FF4D00", "#06b6d4", "#22c55e", "#8b5cf6", "#f59e0b", "#ec4899"]

    fig = go.Figure()
    for i, run in enumerate(runs):
        c = radar_colors[i % len(radar_colors)]
        fig.add_trace(go.Scatterpolar(
            r=run["values"] + [run["values"][0]],  # close the polygon
            theta=categories + [categories[0]],
            fill='toself',
            fillcolor=c.replace(")", ", 0.1)").replace("#", "rgba(") if c.startswith("rgba") else f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.1)",
            line=dict(color=c, width=2),
            name=run["label"],
        ))

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#333",
                            tickfont=dict(color="#666", size=9)),
            angularaxis=dict(gridcolor="#333", tickfont=dict(color="#aaa", size=11)),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#ccc", family="Inter, sans-serif"),
        legend=dict(bgcolor="rgba(21,21,21,0.9)", font=dict(color="#f3f4f6", size=10),
                    bordercolor="#444", borderwidth=1),
        height=420,
        margin=dict(l=60, r=60, t=40, b=40),
    )

    return {
        "runs": runs,
        "radar_chart": json.loads(fig.to_json()),
    }


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

    # Log to history
    history = _load_history()
    history.insert(0, {
        "job_id": job_id,
        "algo": algo,
        "drones": drones,
        "duration": duration,
        "formation_type": formation_type,
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "running",
    })
    # Keep at most 50 entries
    history = history[:50]
    _save_history(history)

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

        # Update history entry status
        history = _load_history()
        for entry in history:
            if entry.get("job_id") == job_id:
                entry["status"] = "completed"
                break
        _save_history(history)

        yield "event: done\ndata: complete\n\n"

    return StreamingResponse(log_generator(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────────────────
# Results endpoint — overview + 3D trajectory
# ─────────────────────────────────────────────────────────────────────────────
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
    num_drones = positions.shape[1]

    fig = go.Figure()

    for i in range(num_drones):
        x = positions[:, i, 0]
        y = positions[:, i, 1]
        z = positions[:, i, 2]
        c = DRONE_COLORS[i % len(DRONE_COLORS)]

        fig.add_trace(go.Scatter3d(
            x=x, y=y, z=z,
            mode='lines',
            name=f'Drone {i}',
            line=dict(color=c, width=3)
        ))

        fig.add_trace(go.Scatter3d(
            x=[x[0]], y=[y[0]], z=[z[0]],
            mode='markers',
            name=f'Drone {i} Start',
            marker=dict(color=c, size=5, symbol='circle'),
            showlegend=False
        ))

        fig.add_trace(go.Scatter3d(
            x=[x[-1]], y=[y[-1]], z=[z[-1]],
            mode='markers',
            name=f'Drone {i} End',
            marker=dict(color=c, size=6, symbol='diamond'),
            showlegend=False
        ))

    fig.update_layout(
        **{k: v for k, v in PLOTLY_DARK_LAYOUT.items() if k not in ('xaxis', 'yaxis')},
        scene=dict(
            xaxis=dict(showbackground=False, gridcolor='#374151', zerolinecolor='#4b5563', title='X (m)'),
            yaxis=dict(showbackground=False, gridcolor='#374151', zerolinecolor='#4b5563', title='Y (m)'),
            zaxis=dict(showbackground=False, gridcolor='#374151', zerolinecolor='#4b5563', title='Z (m)'),
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
        ),
    )

    plotly_json = json.loads(fig.to_json())

    return {
        "metrics": metrics,
        "plotly_data": plotly_json
    }


# ─────────────────────────────────────────────────────────────────────────────
# Analysis endpoint — time-series charts for metrics
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/analysis/{job_id}")
async def get_analysis(job_id: str):
    """Return per-frame time-series data for analysis charts."""
    res_dir = Path("results") / job_id
    npz_path = res_dir / "telemetry.npz"

    if not npz_path.exists():
        return {"error": "Telemetry not found"}

    data = np.load(npz_path)
    positions = data["positions"]       # (T, N, 3)
    velocities = data["velocities"]     # (T, N, 3)
    timestamps = data["timestamps"]     # (T,)
    neighbor_graph = data.get("neighbor_graph", None)  # (T, N, N)

    T, N = positions.shape[0], positions.shape[1]
    ts = timestamps.tolist()

    # --- Cohesion over time (mean distance to centroid) ---
    cohesion = []
    for t in range(T):
        centroid = np.mean(positions[t], axis=0)
        dispersion = np.mean(np.linalg.norm(positions[t] - centroid, axis=1))
        cohesion.append(round(float(dispersion), 4))

    # --- Connectivity over time (Fiedler value) ---
    connectivity = []
    if neighbor_graph is not None and len(neighbor_graph) > 0:
        for t in range(T):
            adj = neighbor_graph[t]
            if len(adj) <= 1:
                connectivity.append(1.0)
                continue
            try:
                degree = np.diag(np.sum(adj, axis=1))
                laplacian = degree - adj
                eigenvalues = np.linalg.eigvalsh(laplacian)
                fiedler = max(0.0, float(eigenvalues[1]))
                connectivity.append(round(fiedler, 4))
            except Exception:
                connectivity.append(0.0)
    else:
        connectivity = [0.0] * T

    # --- Mean speed over time ---
    speeds = []
    for t in range(T):
        mean_speed = float(np.mean(np.linalg.norm(velocities[t], axis=1)))
        speeds.append(round(mean_speed, 4))

    # --- Collision proximity over time (min pairwise distance per frame) ---
    min_distances = []
    for t in range(T):
        if N < 2:
            min_distances.append(float('inf'))
            continue
        diffs = positions[t][:, np.newaxis, :] - positions[t][np.newaxis, :, :]
        dists = np.linalg.norm(diffs, axis=2)
        np.fill_diagonal(dists, np.inf)
        min_distances.append(round(float(np.min(dists)), 4))

    # --- Coverage accumulation over time (2D projected) ---
    visited = set()
    coverage_timeline = []
    bounds_lo = np.array([-5.0, -5.0])
    bounds_hi = np.array([5.0, 5.0])
    resolution = 1.0
    grid_dims = np.ceil((bounds_hi - bounds_lo) / resolution).astype(int)
    total_cells = int(np.prod(grid_dims))

    for t in range(T):
        for i in range(N):
            xy = positions[t, i, :2]
            idx = np.floor((xy - bounds_lo) / resolution).astype(int)
            if np.all(idx >= 0) and np.all(idx < grid_dims):
                visited.add(tuple(idx))
        pct = len(visited) / max(total_cells, 1)
        coverage_timeline.append(round(float(pct) * 100, 2))

    # --- Build Plotly charts ---
    charts = {}

    # Cohesion chart
    fig_coh = go.Figure()
    fig_coh.add_trace(go.Scatter(x=ts, y=cohesion, mode='lines', name='Dispersion',
                                  line=dict(color='#06b6d4', width=2),
                                  fill='tozeroy', fillcolor='rgba(6,182,212,0.1)'))
    fig_coh.update_layout(**PLOTLY_DARK_LAYOUT, height=280,
                          yaxis_title='Mean Distance to Centroid (m)')
    charts["cohesion"] = json.loads(fig_coh.to_json())

    # Connectivity chart
    fig_conn = go.Figure()
    fig_conn.add_trace(go.Scatter(x=ts, y=connectivity, mode='lines', name='Fiedler Value',
                                   line=dict(color='#8b5cf6', width=2),
                                   fill='tozeroy', fillcolor='rgba(139,92,246,0.1)'))
    fig_conn.update_layout(**PLOTLY_DARK_LAYOUT, height=280,
                           yaxis_title='Algebraic Connectivity')
    charts["connectivity"] = json.loads(fig_conn.to_json())

    # Speed chart
    fig_spd = go.Figure()
    fig_spd.add_trace(go.Scatter(x=ts, y=speeds, mode='lines', name='Mean Speed',
                                  line=dict(color='#f59e0b', width=2),
                                  fill='tozeroy', fillcolor='rgba(245,158,11,0.1)'))
    fig_spd.update_layout(**PLOTLY_DARK_LAYOUT, height=280,
                          yaxis_title='Speed (m/s)')
    charts["speed"] = json.loads(fig_spd.to_json())

    # Collision safety chart
    fig_col = go.Figure()
    fig_col.add_trace(go.Scatter(x=ts, y=min_distances, mode='lines', name='Min Pairwise Dist',
                                  line=dict(color='#ef4444', width=2),
                                  fill='tozeroy', fillcolor='rgba(239,68,68,0.1)'))
    # Add danger threshold
    fig_col.add_hline(y=0.2, line_dash="dash", line_color="#f97316",
                      annotation_text="Collision Threshold", annotation_font_color="#f97316")
    fig_col.update_layout(**PLOTLY_DARK_LAYOUT, height=280,
                          yaxis_title='Min Distance (m)')
    charts["collision"] = json.loads(fig_col.to_json())

    # Coverage chart
    fig_cov = go.Figure()
    fig_cov.add_trace(go.Scatter(x=ts, y=coverage_timeline, mode='lines', name='Coverage',
                                  line=dict(color='#22c55e', width=2),
                                  fill='tozeroy', fillcolor='rgba(34,197,94,0.1)'))
    fig_cov.update_layout(**PLOTLY_DARK_LAYOUT, height=280,
                          yaxis_title='Coverage (%)')
    charts["coverage"] = json.loads(fig_cov.to_json())

    return {
        "charts": charts,
        "summary": {
            "final_cohesion": cohesion[-1] if cohesion else 0,
            "final_connectivity": connectivity[-1] if connectivity else 0,
            "mean_speed": round(float(np.mean(speeds)), 4) if speeds else 0,
            "min_safe_distance": round(float(np.min(min_distances)), 4) if min_distances else 0,
            "final_coverage": coverage_timeline[-1] if coverage_timeline else 0,
            "total_frames": T,
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Replay endpoint — return per-frame position data for 2D animation
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/replay/{job_id}")
async def get_replay(job_id: str):
    """Return subsampled frames for 2D replay animation."""
    res_dir = Path("results") / job_id
    npz_path = res_dir / "telemetry.npz"

    if not npz_path.exists():
        return {"error": "Telemetry not found"}

    data = np.load(npz_path)
    positions = data["positions"]   # (T, N, 3)
    timestamps = data["timestamps"]

    T = positions.shape[0]
    # Subsample to max ~300 frames for smooth JS animation
    step = max(1, T // 300)
    frames = []
    for t in range(0, T, step):
        frames.append({
            "t": round(float(timestamps[t]), 3),
            "pos": positions[t, :, :2].tolist()  # only x,y for 2D replay
        })

    return {
        "frames": frames,
        "num_drones": int(positions.shape[1]),
        "bounds": {"lo": [-5, -5], "hi": [5, 5]}
    }


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark endpoint — structured score card
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/benchmark/{job_id}")
async def get_benchmark(job_id: str):
    """Return structured benchmark data for the score card panel."""
    res_dir = Path("results") / job_id
    json_path = res_dir / "metrics.json"
    manifest_path = res_dir / "manifest.json"

    if not json_path.exists() or not manifest_path.exists():
        return {"error": "Metrics not found"}

    with open(json_path, "r") as f:
        metrics_data = json.load(f)
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    detailed = metrics_data.get("metrics", {})

    # Build per-metric breakdown
    metric_cards = []
    names_map = {
        "CoverageMetric": {"label": "Coverage", "icon": "fa-solid fa-map",
                           "desc": "Percentage of target volume explored"},
        "CohesionMetric": {"label": "Cohesion", "icon": "fa-solid fa-compress",
                           "desc": "Swarm tightness around centroid"},
        "ConnectivityMetric": {"label": "Connectivity", "icon": "fa-solid fa-network-wired",
                               "desc": "Algebraic connectivity of communication graph"},
        "CollisionRateMetric": {"label": "Safety", "icon": "fa-solid fa-shield-halved",
                                "desc": "Absence of close-proximity violations"},
    }

    for key, val in detailed.items():
        meta = names_map.get(key, {"label": key, "icon": "fa-solid fa-chart-bar",
                                    "desc": ""})
        score = round(float(val) * 100, 1)
        grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"
        metric_cards.append({
            "key": key,
            "label": meta["label"],
            "icon": meta["icon"],
            "desc": meta["desc"],
            "score": score,
            "grade": grade,
            "raw": round(float(val), 4),
        })

    # Build benchmark gauge data for Plotly
    health = metrics_data.get("health_score", 0.0)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(health * 100, 1),
        number=dict(suffix="%", font=dict(color="#f5f5f5", size=48)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor="#666", dtick=20,
                      tickfont=dict(color="#888")),
            bar=dict(color="#FF4D00"),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[
                dict(range=[0, 40], color="rgba(239,68,68,0.15)"),
                dict(range=[40, 70], color="rgba(245,158,11,0.15)"),
                dict(range=[70, 100], color="rgba(34,197,94,0.15)"),
            ],
            threshold=dict(line=dict(color="#22c55e", width=3), thickness=0.8,
                           value=round(health * 100, 1))
        )
    ))
    fig_gauge.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#888'),
        height=260,
        margin=dict(l=30, r=30, t=40, b=10),
    )

    emergence = metrics_data.get("emergence", [])

    return {
        "health_score": round(health * 100, 1),
        "health_grade": "A" if health >= 0.8 else "B" if health >= 0.6 else "C" if health >= 0.4 else "D",
        "metric_cards": metric_cards,
        "emergence": emergence,
        "gauge_chart": json.loads(fig_gauge.to_json()),
        "manifest": manifest,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Export endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/export/{job_id}/report")
async def export_report(job_id: str):
    """Download the benchmark report markdown."""
    res_dir = Path("results") / job_id
    report_path = res_dir / "report.md"
    if not report_path.exists():
        return {"error": "Report not found"}
    return FileResponse(report_path, filename=f"swarm_report_{job_id}.md",
                        media_type="text/markdown")


@app.get("/export/{job_id}/metrics")
async def export_metrics(job_id: str):
    """Download the raw metrics JSON."""
    res_dir = Path("results") / job_id
    json_path = res_dir / "metrics.json"
    if not json_path.exists():
        return {"error": "Metrics not found"}
    return FileResponse(json_path, filename=f"metrics_{job_id}.json",
                        media_type="application/json")


@app.get("/export/{job_id}/telemetry")
async def export_telemetry(job_id: str):
    """Download the raw telemetry NPZ file."""
    res_dir = Path("results") / job_id
    npz_path = res_dir / "telemetry.npz"
    if not npz_path.exists():
        return {"error": "Telemetry not found"}
    return FileResponse(npz_path, filename=f"telemetry_{job_id}.npz",
                        media_type="application/octet-stream")


@app.get("/export/{job_id}/manifest")
async def export_manifest(job_id: str):
    """Download the manifest JSON."""
    res_dir = Path("results") / job_id
    manifest_path = res_dir / "manifest.json"
    if not manifest_path.exists():
        return {"error": "Manifest not found"}
    return FileResponse(manifest_path, filename=f"manifest_{job_id}.json",
                        media_type="application/json")
