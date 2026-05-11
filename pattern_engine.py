import time
from collections import deque, Counter


class PatternEngine:
    def __init__(self, memory_path="data/synaptic_memory.json"):
        self.memory_path = memory_path
        self.event_history = deque(maxlen=100)
        self.patterns = {}
        self.current_session = []
        self.start_time = time.time()

    def process_event(self, event):
        """
        Processes an incoming event (file change, browser hit, etc.)
        event: {'type': 'file_change/browser/sys', 'path': '...', 'timestamp': ...}
        """
        timestamp = time.time()
        source = self._classify_event_source(event)
        event_data = {
            "type": event.get("type"),
            "source": source,
            "path": event.get("path"),
            "timestamp": timestamp,
        }

        self.event_history.append(event_data)
        self.current_session.append(event_data)

        # Analyze pattern for a pair of consecutive events
        if len(self.event_history) >= 2:
            prev = self.event_history[-2]
            curr = self.event_history[-1]
            self._update_pattern(prev, curr)

        return self._calculate_pulse(event)

    def _classify_event_source(self, event):
        event_kind = (event.get("event") or "").upper()
        if event_kind == "WEB_VISIT":
            return "browser"
        return "file_change"

    def _update_pattern(self, prev, curr):
        if not prev.get("path") or not curr.get("path"):
            return
        pair = (prev["path"], curr["path"])
        self.patterns[pair] = self.patterns.get(pair, 0) + 1

    def _calculate_pulse(self, event):
        """
        Calculates the 'intensity' of the neural pulse for the Frontend.
        """
        intensity = "low"
        path = event.get("path") or ""

        # High activity for .md files or rapid changes in the same file
        if path.endswith(".md"):
            intensity = "high"

        # Check if this file was edited multiple times recently
        recent_hits = [e for e in self.event_history if e["path"] == path]
        if len(recent_hits) > 5:
            intensity = "hyperactive"
        elif len(recent_hits) > 2:
            intensity = "medium"

        return {"node": path, "intensity": intensity, "type": "SYNAPSE_FIRE"}

    def analyze_behavioral_state(self):
        """
        Infers the user's current cognitive state based on event density and types.
        """
        if not self.current_session:
            return "IDLE"

        recent = list(self.event_history)[-20:]
        sources = [e.get("source", "file_change") for e in recent]
        counts = Counter(sources)

        # Logic for state detection
        if counts.get("browser", 0) > counts.get("file_change", 0):
            return "RESEARCHING"
        elif counts.get("file_change", 0) > 5:
            return "CODING"
        elif any((e.get("path") or "").endswith(".md") for e in recent):
            return "REFLECTING"

        return "BALANCED"

    def sync_to_manager(self, manager):
        """
        Syncs detected patterns to the MemoryManager (SQLite).
        """
        for (path_a, path_b), count in self.patterns.items():
            if path_a and path_b:
                manager.update_synapse(path_a, path_b, weight_inc=count)

        # Clear patterns after sync to avoid double counting
        self.patterns = {}

    def sync_to_memory(self, memory):
        # ... (keep for compatibility or remove)
        pass
