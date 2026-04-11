# Tashi Vertex Swarm Starter Kit (Webots Edition)

A **Decentralized Swarm Controller** for Webots, powered by the **Tashi Vertex** consensus engine. These drones form a peer-to-peer (P2P) mesh and reach verifiable agreement on mission commands without a central server.

## Prerequisites

- **Webots** R2021a or newer
- **Rust** (install from https://rustup.rs)
- **CMake 4.0+** (`pip install cmake`)
- **Python 3.8+**
- **Windows (WSL)**: If on Windows, you can use WSL to build and run the Tashi binaries. The starter kit will automatically detect and use WSL as a bridge.

## Quick Start

### 1. Setup
```bash
./setup.sh
```

This will:
- Build the Tashi tools (`drone-comm`, `key-generate`)
- Generate unique P2P keys for each drone
- Create `swarm_config.json`

### 2. Run
1. Open Webots
2. Load `worlds/sample.wbt`
3. Press **Play**

Watch the console for `Consensus Layer: READY` and mission consensus.

## Project Structure

```
├── tashi-tools/              # Rust binaries (uses tashi-vertex crate)
│   ├── Cargo.toml
│   └── src/bin/
│       ├── drone-comm.rs     # P2P node for Webots
│       └── key-generate.rs   # Key generation tool
├── controllers/tashi_drone/  # Webots controller
│   ├── tashi_drone.py        # Main loop
│   ├── tashi_manager.py      # Tashi node interface
│   ├── config.py             # Configuration
│   └── swarm_config.json     # Generated keys (git-ignored)
├── worlds/                   # Webots world files
│   └── sample.wbt            # 2-drone example
├── utils/
│   └── generate_config.py    # Key generation script
└── setup.sh                  # One-command setup
```

## Architecture

- **Decentralized Control**: Each drone runs its own Python controller
- **P2P Consensus**: Each drone launches a Tashi node that communicates directly with peers
- **Zero-Trust Identity**: Dynamically generated Ed25519 keys sign and verify all messages

## Adding More Drones

1. Edit `utils/generate_config.py` and add names to `DRONE_NAMES`
2. Run `python utils/generate_config.py`
3. Add matching drones in Webots with the same names

## Troubleshooting

**Socket Error ("Failed to bind socket")**
- Kill lingering processes: `pkill -f drone-comm`
- On Windows: Close `drone-comm.exe` in Task Manager
- On WSL: Run `wsl --shutdown` in your terminal

**Identity Mismatch**
- Ensure drone `name` in Webots matches keys in `DRONE_NAMES`

**Build Errors**
- Ensure CMake 4.0+: `pip install cmake --upgrade`
- Check Rust is installed: `cargo --version`

## License

Apache 2.0 - See LICENSE file
