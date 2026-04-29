# 🧠 ZEUS SYSTEM: Comprehensive Technical Documentation

## 1. Architecture Overview
The ZEUS System is a **Cognitive Autonomous Operating Layer** that acts as a bridge between the user and the Operating System (Linux). It implements a **Sensing $\rightarrow$ Thinking $\rightarrow$ Acting $\rightarrow$ Learning** loop.

### Core Design Patterns
- **Hybrid Polyglot:** Uses **Rust** for high-performance system monitoring and **Python** for cognitive logic.
- **Hierarchical Memory:** Three-tier memory system (Short-Term, Mid-Term, Long-Term).
- **Shadow Execution:** Commands are validated and simulated before being applied to the host.
- **Sovereign Intelligence:** Integration with Local LLMs (Ollama) and Cloud LLMs (Google Gemini 1.5 Flash) for reasoning.

---

## 2. Directory Structure & Component Mapping

### 📂 `/home/zeus/Documentos/ZEUS_SYSTEM/`
| Folder/File | Description | Role |
| :--- | :--- | :--- |
| `00 - CORE/` | Core architectural definitions. | Foundation |
| `apps/` | Entry points and interfaces. | Interface |
| `zeus_core/` | The cognitive engine (Planning, Memory, Logic). | Brain |
| `zeus_core/v4/` | Latest iteration of the cognitive loop (Reward-based). | Next-Gen Logic |
| `watcher_rs/` | Rust-based system monitor. | Sensory (Eyes/Ears) |
| `core-rust/` | Low-level system utility modules in Rust. | System Utils |
| `zeus_extension/` | Flutter-based cross-platform client. | UI/UX Front-end |
| `public/` | HTML/JS assets for the Neural Sphere 3D GUI. | Web Interface |
| `data/` | Persistent vector and synaptic memory stores. | Long-term Memory |
| `scratch/` | Temporary communication buffers and work areas. | Working Memory |
| `bin/` | Consolidated system launchers. | Bootloader |
| `docs/` | Technical documentation and reports. | Knowledge Base |
| `.env` | System environment variables and API keys. | Configuration |

---

## 3. Logic & Data Flow

### 🎙️ Voice Interface Flow
`User Voice` $\rightarrow$ `App (Websocket)` $\rightarrow$ `Server (ASR/Whisper)` $\rightarrow$ `Cognitive Core (Gemini)` $\rightarrow$ `TTS (Edge-TTS)` $\rightarrow$ `Device Speakers`.

### 📂 File System Sensing Flow
`Rust Watcher` $\rightarrow$ `Event Queue` $\rightarrow$ `Pattern Engine` $\rightarrow$ `Synaptic Update` $\rightarrow$ `Memory Manager`.

### 🧠 Cognitive Reasoning Loop (v4)
1. **Perception:** Sensors gather system state (CPU, RAM, File changes).
2. **Interpretation:** Events are analyzed to form a "Situation".
3. **Planning:** `StrategistAgent` creates a technical plan using LLM.
4. **Execution:** `OperatorAgent` proposes safe shell commands.
5. **Validation:** `CriticAgent` evaluates the result.
6. **Memory:** Successful actions are indexed in `VectorMemory` for future recall.

---

## 4. Technology Stack

- **Languages:** Python 3.12+, Rust, Dart (Flutter), JavaScript.
- **AI Models:** 
  - **Reasoning:** Google Gemini 1.5 Flash / Ollama (Gemma 4).
  - **ASR:** Faster-Whisper.
  - **TTS:** Edge-TTS (Neural Voices).
- **Infrastructure:** FastAPI, Socket.io, SQLite (Memory Storage), ChromaDB (Vector DB).
- **Tools:** ffmpeg, paplay/aplay, xdg-open.

---

## 5. Security & Safety
- **Guardian Core:** Blacklist of destructive commands (e.g., `rm -rf /`).
- **Dry-Run Mode:** Commands are Proposed $\rightarrow$ Validated $\rightarrow$ Confirmed before execution.
- **LAN Isolation:** JWT-based authentication for remote access.
