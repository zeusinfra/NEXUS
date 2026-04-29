# ZEUS — Cognitive Operating System & AI Interface

ZEUS is a modular, high-performance cognitive system designed to integrate large language models (LLMs), vision, voice, and browser control into a unified command center. It features a FastAPI backend, a Flutter-based mobile extension, and a Rust-powered file watcher.

## 🚀 Key Features

- **Multi-Modal Interaction**: Integrated support for Gemini, Ollama, and other LLMs.
- **Cognitive Core**: Advanced memory hierarchy (long-term, vector memory, and synaptic maps).
- **Unified Interface**: Accessible via Browser (FastAPI + WebSockets), Desktop App (PyQt wrapper), and Mobile (Flutter).
- **Voice Sensing & ASR**: Real-time voice interaction and speech-to-text capabilities.
- **Vision & Browser Control**: Ability to "see" and interact with web pages and local files.
- **Evolution Engine**: Self-optimizing logic and pattern recognition.

## 🏗️ Architecture

The project is divided into several modules:

- `zeus_core/`: The "brain" of the system, containing the agent logic, memory managers, and execution engines.
- `apps/`: Main entry points for the system (Web GUI, Evolution Engine, v4 Core).
- `zeus_extension/`: Flutter mobile application for remote control and cognitive sync.
- `watcher_rs/` & `core-rust/`: High-performance Rust components for system monitoring and core operations.
- `communication/`: WebSocket and API protocols for inter-component synchronization.

## 🛠️ Getting Started

### Prerequisites

- Python 3.10+
- Flutter SDK (for the mobile extension)
- Rust (for the core-rust/watcher components)
- Ollama or Gemini API Key (optional, for LLM features)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ZEUS_SYSTEM.git
   cd ZEUS_SYSTEM
   ```

2. **Setup Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy the example environment file (if available) or create a `.env` file in the root:
   ```bash
   # .env
   GEMINI_API_KEY=your_key_here
   ZEUS_LLM_URL=http://127.0.0.1:11434/api/chat
   ```

4. **Launch the System**:
   Use the unified launcher in `bin/`:
   ```bash
   chmod +x bin/zeus
   ./bin/zeus web      # Starts the Web Command Center
   ./bin/zeus desktop  # Starts the Desktop App
   ```

## 📱 Mobile Extension

The mobile extension is located in `zeus_extension/`. To build and run:
```bash
cd zeus_extension
flutter pub get
flutter run
```

## 📜 License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details. (Note: Adjust license as needed).

---
*ZEUS — The ultimate interface between human intelligence and machine cognition.*
