# Development Environment Setup

This guide explains how to set up a local development environment for Project Remis.

## Prerequisites

- [Git](https://git-scm.com/)
- [Conda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [NVM for Windows](https://github.com/coreybutler/nvm-windows) (or `nvm` on macOS/Linux)
- [Rust](https://rustup.rs/) (required only for Tauri shell development and release builds)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Drlinglong/Remis.git
cd Remis
```

### 2. Set Up Python Environment

```bash
# Create Conda environment
conda create -n local_factory python=3.10 -y
conda activate local_factory

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up Node.js Environment

```bash
cd scripts/react-ui

# React Router 8 / Vite 8 require Node.js 22.22.0 or newer
nvm install 22.22.0
nvm use 22.22.0

# Install frontend dependencies
npm ci
```

### 4. Start Development Servers

Use the one-click launcher script:

```powershell
.\scripts\developer_tools\windows\run-dev.bat
```

This will start both:
- **Backend**: FastAPI (`127.0.0.1:1453` by default; the launcher selects an available port if needed)
- **Frontend**: Vite React / Tauri development UI (port 5174 by default)

Use this launcher for development checkouts. It selects the intended Python
environment, backend port, and frontend proxy configuration together.

## Directory Structure

```
Remis/
├── scripts/
│   ├── react-ui/                  # React frontend
│   │   └── src-tauri/             # Tauri desktop shell (Rust)
│   ├── web_server.py              # FastAPI backend entry point
│   ├── routers/                   # API routes
│   ├── core/                      # Core translation engine
│   └── workflows/                 # Translation workflows
├── website/                       # Product website
├── data/                          # Data directory
├── tests/                         # Test suite
└── docs/                          # Documentation
```

## Building the Desktop App

Check the Tauri desktop shell locally:

```powershell
cargo fmt --manifest-path scripts/react-ui/src-tauri/Cargo.toml -- --check
New-Item -ItemType File -Force scripts/react-ui/src-tauri/web_server-x86_64-pc-windows-msvc.exe | Out-Null
cargo check --locked --manifest-path scripts/react-ui/src-tauri/Cargo.toml
Remove-Item scripts/react-ui/src-tauri/web_server-x86_64-pc-windows-msvc.exe
```

The placeholder is only for `cargo check`. A release build must use the
repository build pipeline to create the real Python sidecar, health-check the
packaged backend, and produce the Windows installer.

## Related Documentation

- [Documentation Center](../../documentation-center.md)
- [Local CI Guide](../../zh/developer/ci-setup.md)
- [Release Build Script Guide](./build-release-script-guide.md)
