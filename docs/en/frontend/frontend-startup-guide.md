# Frontend Development Setup

This document outlines the process for setting up and running the frontend development server.

The project uses a "one-click" launcher script to simplify the setup process.

## Prerequisites

* [Conda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
* [NVM for Windows](https://github.com/coreybutler/nvm-windows) (or `nvm` on macOS/Linux)

## One-Click Setup

1.  **Install Node.js:** Navigate to the `scripts/react-ui` directory and run `nvm install`. This will automatically read the `.nvmrc` file and install the correct Node.js version (`v20.12.2`).
2.  **Run the Launcher:** From the project root, simply execute the main development launcher:
    ```bash
    scripts\developer_tools\windows\run-dev.bat
    ```

This script will automatically perform the following steps:
- Launch a new terminal window for the backend, activate the `local_factory` Conda environment, and start the FastAPI server.
- Launch another new terminal window for the frontend, set the correct Node.js version using `nvm`, and start the Vite development server.

The frontend will be available at `http://localhost:5173` (or the next available port).
