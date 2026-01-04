# Development Environment Setup

This guide explains how to set up a local development environment for Project Remis.

## Prerequisites

- [Git](https://git-scm.com/)
- [Conda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [NVM for Windows](https://github.com/coreybutler/nvm-windows) (or `nvm` on macOS/Linux)

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

# Install the specified Node.js version
nvm install v20.12.2
nvm use v20.12.2

# Install frontend dependencies
npm install
```

### 4. Start Development Servers

Use the one-click launcher script:

```bash
./run-dev.bat
```

This will start both:
- **Backend**: FastAPI (port 8000)
- **Frontend**: Vite React (port 5173)

Or start manually:

**Terminal 1 - Backend:**
```bash
conda activate local_factory
uvicorn scripts.web_server:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd scripts/react-ui
npm run dev
```

## Directory Structure

```
remis-mod-factory/
├── src-tauri/                     # Tauri desktop shell (Rust)
├── scripts/
│   ├── react-ui/                  # React frontend
│   ├── web_server.py              # FastAPI backend entry point
│   ├── routers/                   # API routes
│   ├── services/                  # Business service layer
│   ├── core/                      # Core translation engine
│   └── workflows/                 # Translation workflows
├── data/                          # Data directory
├── tests/                         # Test suite
└── docs/                          # Documentation
```

## Building the Desktop App

Building the Tauri desktop app requires the Rust toolchain:

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build
npm run tauri build
```

## Related Documentation

- [Project Technical Documentation](../main.md)
- [Frontend Development Guide](../frontend/)
- [API Documentation](../../technical/)
