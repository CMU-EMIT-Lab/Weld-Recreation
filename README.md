# Virtual Cobot Welding
### Autonomous Weld Path Replication via Computer Vision and URScript Generation

> **EMIT Lab · Carnegie Mellon University**  
> Engineering Materials for Transformative Technologies Laboratory

---

## Overview

Manual weld programming is time-intensive. Replicating custom welds requires tedious hand-teaching or manual coding — a significant bottleneck in fabrication workflows that affects manufacturing shops, robotics teams, and anyone doing structural assembly where weld repeatability matters.

This project eliminates that bottleneck. Using computer vision to analyze weld geometry from images, a Python pipeline extracts spatial parameters and automatically generates URScript code, which is then deployed to a **UR10e collaborative robot arm** for autonomous execution — no manual programming required.

---

## Pipeline

```
Input Image
    │
    ▼
Computer Vision (weld geometry extraction)
    │   - Weld path detection
    │   - Spatial parameter analysis
    │   - Toolpath reconstruction
    ▼
Python Code Generation
    │   - Waypoint computation
    │   - URScript synthesis
    │   - Parameter validation
    ▼
Deployment (SSH/VPN)
    │
    ▼
UR10e Execution
    │   - Autonomous path following
    │   - Repeatable weld replication
    ▼
Output: Replicated Weld
```

---

## Features

- **Computer Vision Weld Analysis** — Extracts weld geometry, orientation, and spatial parameters directly from images
- **Automated URScript Generation** — Python pipeline converts extracted parameters to deployable UR robot programs without manual coding
- **UR10e Integration** — Full compatibility with Universal Robots UR10e collaborative arm via URScript
- **Remote Deployment** — SSH/VPN-based infrastructure for testing and deployment without direct tether
- **Rapid Weld Replication** — Enables fast reproduction of custom welds across production runs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Computer Vision | Python (OpenCV / vision pipeline) |
| Code Generation | Python → URScript |
| Robot Platform | Universal Robots UR10e |
| Deployment | SSH / VPN remote infrastructure |
| Interface | URScript (UR native programming language) |

---

## Repository Structure

```
cobot-welding/
├── vision/                  # Computer vision modules
│   ├── weld_detection.py    # Weld path and geometry extraction
│   └── spatial_analysis.py  # Spatial parameter computation
├── codegen/                 # URScript generation
│   ├── waypoint_gen.py      # Waypoint computation from vision output
│   └── urscript_gen.py      # URScript synthesis and formatting
├── deploy/                  # Deployment utilities
│   ├── ssh_deploy.py        # Remote deployment via SSH
│   └── config.yaml          # Connection and robot configuration
├── tests/                   # Unit and integration tests
├── data/                    # Sample weld images and reference paths
│   ├── samples/
│   └── ground_truth/
├── docs/                    # Additional documentation
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- UR10e robot arm with network access
- SSH/VPN access to robot network (for remote deployment)
- OpenCV and dependencies (see `requirements.txt`)

### Installation

```bash
git clone https://github.com/<your-org>/cobot-welding.git
cd cobot-welding
pip install -r requirements.txt
```

### Configuration

Edit `deploy/config.yaml` with your robot's IP address and network credentials:

```yaml
robot:
  ip: 192.168.x.x
  port: 30002
  
deploy:
  method: ssh      # or vpn
  timeout: 10
```

### Usage

**1. Run the full pipeline on a weld image:**

```bash
python main.py --input data/samples/weld_sample.jpg --output output/program.urscript
```

**2. Deploy to UR10e:**

```bash
python deploy/ssh_deploy.py --script output/program.urscript
```

**3. Run vision analysis only (without deployment):**

```bash
python vision/weld_detection.py --input data/samples/weld_sample.jpg --visualize
```

---

## How It Works

### 1. Weld Geometry Extraction
The vision module processes input images to detect weld seams, identify joint geometry, and reconstruct the 3D toolpath from 2D image data. Key outputs include weld start/end points, joint angle, and a sequence of interpolated waypoints.

### 2. URScript Code Generation
The Python codegen layer converts extracted waypoints into valid URScript programs. It handles coordinate frame transformations, motion type selection (linear/joint), approach and retract motions, and weld parameter injection (speed, blend radius).

### 3. Deployment
Generated URScript is transferred to the UR10e controller via SSH and executed autonomously. The robot replicates the detected weld path without any manual teach pendant input.

---

## Motivation

Traditional weld programming workflows require either:
- **Hand-teaching** — manually guiding the robot through each point (slow, imprecise, non-transferable)
- **Manual URScript coding** — writing robot programs by hand from measurements (time-intensive, error-prone)

Both approaches are bottlenecks at scale. This system replaces both with a vision-driven, automated pipeline — enabling rapid weld replication from a single reference image.

---

## Status

This project is under active development as part of ongoing research at the **EMIT Lab, Carnegie Mellon University**.

- [x] URScript generation pipeline
- [x] SSH/VPN remote deployment infrastructure
- [ ] Computer vision weld path extraction (in progress)
- [ ] End-to-end pipeline integration
- [ ] Validation against ground-truth weld paths

---

## Lab & Acknowledgements

**Engineering Materials for Transformative Technologies (EMIT) Lab**  
Carnegie Mellon University  

---

## License

This project is part of academic research at Carnegie Mellon University. Contact the EMIT Lab for usage and licensing information.
