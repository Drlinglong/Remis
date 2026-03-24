# **Remis Project: Full-Stack AI Development Guidelines**

These guidelines define the operational principles, architectural standards, and design philosophy for the **Remis** project. They combine general AI development best practices with the specific technical constraints of this local desktop application.

---

## **1. Core Architecture & Environment**

The AI operates within a **Windows-based local development environment**, building a desktop-class application.

### **The "Decoupled" Stack**
*   **Goal**: A local desktop application (eventually via Tauri/Electron).
*   **Frontend**: **React** (Vite) + **Mantine** (UI Library).
    *   Runs on a dev server (e.g., port 5173).
    *   Proxies API requests to the backend.
*   **Backend**: **Python 3.x** (FastAPI).
    *   Runs as a local server (e.g., port 8081).
    *   **Strict Separation**: Core logic (`scripts/core/`) must be callable by both the Web UI and CLI/Tests without modification.
*   **Communication**: REST API via `axios`.

### **Data Persistence Strategy**
1.  **Project State (JSON Sidecar)**:
    *   Project-specific data (Kanban progress, user notes, config) is stored in a **`.remis_project.json`** file in the user's project root.
    *   *Why?* To support portability and "folder-as-project" workflows.
2.  **Global Data (SQLite)**:
    *   **`database.sqlite`**: Central Glossary/Dictionary storage.
    *   **`mods_cache.sqlite`**: Version control and translation archives.
    *   **`translation_progress.sqlite`**: Resume capability for long tasks.

---

## **2. Development Philosophy**

These principles guide *how* the AI should approach tasks to ensure quality and stability.

### **Iterative Workflow**
1.  **Plan**: Before coding, analyze requirements and generate a plan.
2.  **Blueprint**: Maintain a mental or actual blueprint of the system state.
3.  **Implement**: Write code in small, verifiable chunks.
4.  **Verify**: Immediately check terminal outputs, logs, and UI behavior.

### **Automated Error Detection & Remediation**
*   **"Fix as you go"**: After *every* modification, monitor:
    *   **Vite Terminal**: For compilation errors.
    *   **Python Console**: For traceback errors (500 Internal Server Error).
    *   **Browser Console**: For React runtime errors.
*   **Self-Correction**: Attempt to fix syntax errors, import issues, or type mismatches automatically before asking the user.

### **Code Quality Standards**
*   **DRY (Don't Repeat Yourself)**: Extract common logic into hooks (Frontend) or utility modules (Backend).
*   **Async/Await**: Use consistently for all API calls and file I/O.
*   **Type Safety**: Use Prop Types or TypeScript interfaces (where applicable) and Pydantic models for Backend schemas.

### **Defensive Programming Principles**
*   **Whitelist Success**: In critical workflows (e.g., translation status), only mark as `Success` if explicitly confirmed. Default to `Failed` or `Pending` for any ambiguity.
*   **Standardize & Centralize**: Avoid hardcoding shared constants (timeouts, retry counts, buffer sizes). Centralize them in `app_settings.py`.
*   **Regression Proofing**: For every bug fix, ensure a corresponding test case is added to `tests/` or a verification script is provided.
*   **Environment Parity**: Always consider packaging constraints (PyInstaller) when adding dependencies or file I/O. Use `get_app_root()` for relative pathing.

---

## **3. UI/UX Design System**

**Aesthetics**: The UI must feel like a **Premium Desktop App**, not a website.
*   **Keywords**: *Dark Mode*, *Glassmorphism*, *Skeuomorphic Details*, *Cinematic*.
*   **Visuals**: Use deep shadows, blurred backgrounds (`backdrop-filter`), and rich textures.

### **Technical Implementation**
*   **Theme System**:
    *   5 distinct themes (Victorian, Byzantine, Sci-Fi, etc.).
    *   Controlled via CSS Variables and `data-theme` attribute on `<html>`.
*   **Layout Engine**:
    *   **Flexbox** over Grid for main layouts.
    *   **Scrolling**: Scrollbars must be on *internal* content areas, never the `body`. Use `flex: 1` + `overflow: hidden` on containers.
*   **Components**:
    *   Use **Mantine** components as the base.
    *   Wrap or style them to fit the "Remis" aesthetic (e.g., custom glass panels).

---

## **4. Backend Engineering Standards**

### **Logic & Workflows**
*   **Generators for Concurrency**: Long-running tasks (translation, scanning) must use Python **generators (`yield`)** to stream progress to the UI.
*   **Validation**:
    *   **Input**: Validate all API payloads using Pydantic.
    *   **Output**: Use `post_process_validator.py` to ensure translation integrity (tags, variables).

### **Robustness & Compatibility**
*   **Encoding Defense**: When reading files, use the "Three-Layer Defense":
    1.  `utf-8-sig` (Best for Windows/Excel).
    2.  System default.
    3.  `utf-8` with `errors='replace'` (Fallback).
*   **Path Handling**: Always use `pathlib.Path`. Resolve paths relative to the project root or user configuration.
*   **Windows Specifics**: When calling external tools (like git or mod tools), use PowerShell-compatible commands and handle BOM-UTF8 correctly.

---

## **5. Documentation & Maintenance**

*   **`task.md`**: Keep the task list updated.
*   **Comments**: Write meaningful comments for complex logic, especially in regex patterns or data migration scripts.
*   **Commit Messages**: Use semantic, descriptive messages (e.g., `feat:`, `fix:`, `docs:`).