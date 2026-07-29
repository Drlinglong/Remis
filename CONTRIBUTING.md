# Contributing to Remis

Remis is a Windows-first desktop application with a Python backend, a React frontend, and a Tauri/Rust shell. Small, focused pull requests are easier to review and safer to release.

## Development setup

Follow the [development setup guide](docs/zh/developer/development-setup.md) for Python, Node.js, and Rust prerequisites. The React Router 8 toolchain requires Node.js 22.22.0 or newer.

## Before opening a pull request

Run the checks relevant to your change from the repository root.

### Python

```powershell
python -m pip install -r requirements.txt
python -m compileall -q scripts tests
python -m flake8 scripts tests --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest --tb=short
```

### React

```powershell
cd scripts/react-ui
npm ci
npm run lint
npm run test
npm run build
```

### Tauri/Rust

```powershell
cargo fmt --manifest-path scripts/react-ui/src-tauri/Cargo.toml -- --check
New-Item -ItemType File -Force scripts/react-ui/src-tauri/web_server-x86_64-pc-windows-msvc.exe | Out-Null
cargo check --locked --manifest-path scripts/react-ui/src-tauri/Cargo.toml
```

The sidecar placeholder is ignored by Git. It only satisfies Tauri configuration validation during `cargo check`; release builds create the real Python sidecar through the build pipeline.

## Pull request expectations

- Explain the problem and why the chosen change is appropriately scoped.
- Add or update tests for behavioral changes.
- Keep generated builds, local databases, model artifacts, benchmark downloads, and credentials out of Git.
- Do not make tests contact paid model APIs or depend on local model servers.
- Treat LLM output as untrusted input. It must not bypass hard validators or approval gates.

GitHub Actions reruns the backend, frontend, Rust, and dependency-review checks on every pull request. Passing CI is necessary but does not replace human review of behavior and risk.
