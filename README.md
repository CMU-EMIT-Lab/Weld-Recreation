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
- **Rapid Weld Replication** — Enables fast reproduction of custom welds across production runs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Computer Vision | Python (OpenCV / vision pipeline) |
| Code Generation | Python → URScript |
| Robot Platform | Universal Robots UR10e |
| Interface | URScript (UR native programming language) |

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

- [ ] URScript generation pipeline
- [ ] SSH/VPN remote deployment infrastructure
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
