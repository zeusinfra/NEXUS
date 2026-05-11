#![allow(non_local_definitions)]

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::UNIX_EPOCH;
use sysinfo::{Disks, System};
use walkdir::WalkDir;

#[derive(Serialize, Deserialize)]
struct ProcessSnapshot {
    name: String,
    cpu: f32,
    memory: f32,
    family: String,
}

#[derive(Serialize, Deserialize)]
struct OsSnapshot {
    cpu_per_core: Vec<f32>,
    cpu_avg: f32,
    ram: f32,
    disk: f32,
    top_processes: Vec<ProcessSnapshot>,
    pressure: String,
}

#[pyclass]
pub struct SensorEngineRust {
    sys: System,
}

#[pymethods]
impl SensorEngineRust {
    #[new]
    pub fn new() -> Self {
        let mut sys = System::new_all();
        sys.refresh_all();
        SensorEngineRust { sys }
    }

    pub fn poll_os_metrics(&mut self) -> HashMap<String, f32> {
        self.sys.refresh_cpu();
        self.sys.refresh_memory();

        let cpu_usage = round1(self.sys.global_cpu_info().cpu_usage());
        let mem_usage = memory_percent(&self.sys);

        let mut metrics = HashMap::new();
        metrics.insert("cpu".to_string(), cpu_usage);
        metrics.insert("mem".to_string(), mem_usage);

        metrics
    }

    pub fn os_snapshot_json(&mut self) -> PyResult<String> {
        self.sys.refresh_cpu();
        self.sys.refresh_memory();
        self.sys.refresh_processes();

        let cpu_per_core: Vec<f32> = self
            .sys
            .cpus()
            .iter()
            .map(|cpu| round1(cpu.cpu_usage()))
            .collect();
        let cpu_avg = if cpu_per_core.is_empty() {
            0.0
        } else {
            round1(cpu_per_core.iter().sum::<f32>() / cpu_per_core.len() as f32)
        };
        let ram = memory_percent(&self.sys);
        let disk = root_disk_percent();
        let total_memory = self.sys.total_memory() as f32;

        let mut process_rows: Vec<ProcessSnapshot> = self
            .sys
            .processes()
            .values()
            .filter_map(|process| {
                let cpu = round1(process.cpu_usage());
                let memory = if total_memory <= 0.0 {
                    0.0
                } else {
                    round1((process.memory() as f32 / total_memory) * 100.0)
                };
                if cpu < 1.0 && memory < 1.0 {
                    return None;
                }
                let name = process.name().to_string();
                Some(ProcessSnapshot {
                    family: classify_process_family(&name),
                    name,
                    cpu,
                    memory,
                })
            })
            .collect();

        process_rows.sort_by(|a, b| {
            b.cpu
                .partial_cmp(&a.cpu)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        process_rows.truncate(3);

        let pressure = if cpu_avg > 80.0 || ram > 85.0 || disk > 92.0 {
            "critical"
        } else if cpu_avg > 55.0 || ram > 70.0 {
            "active"
        } else if cpu_avg > 25.0 || ram > 55.0 {
            "stable"
        } else {
            "calm"
        }
        .to_string();

        let snapshot = OsSnapshot {
            cpu_per_core,
            cpu_avg,
            ram,
            disk,
            top_processes: process_rows,
            pressure,
        };

        serde_json::to_string(&snapshot)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
    }

    pub fn fast_walk(&self, root: String, max_checked: usize) -> Vec<(String, f64)> {
        let mut results = Vec::new();
        let mut checked = 0;

        for entry in WalkDir::new(root)
            .into_iter()
            .filter_entry(|e| {
                let name = e.file_name().to_string_lossy();
                // Pruning comum em Rust
                !name.starts_with('.')
                    && name != "node_modules"
                    && name != "target"
                    && name != "venv"
                    && name != "__pycache__"
            })
            .filter_map(|e| e.ok())
        {
            if entry.file_type().is_file() {
                if let Ok(metadata) = entry.metadata() {
                    if let Ok(mtime) = metadata.modified() {
                        let secs = mtime
                            .duration_since(UNIX_EPOCH)
                            .unwrap_or_default()
                            .as_secs_f64();
                        results.push((entry.path().to_string_lossy().to_string(), secs));
                    }
                }
                checked += 1;
                if checked >= max_checked {
                    break;
                }
            }
        }
        results
    }
}

impl Default for SensorEngineRust {
    fn default() -> Self {
        Self::new()
    }
}

fn round1(value: f32) -> f32 {
    (value * 10.0).round() / 10.0
}

fn memory_percent(sys: &System) -> f32 {
    if sys.total_memory() == 0 {
        0.0
    } else {
        round1((sys.used_memory() as f32 / sys.total_memory() as f32) * 100.0)
    }
}

fn root_disk_percent() -> f32 {
    let disks = Disks::new_with_refreshed_list();
    let root = disks
        .iter()
        .find(|disk| disk.mount_point().to_string_lossy() == "/")
        .or_else(|| disks.iter().next());

    if let Some(disk) = root {
        let total = disk.total_space() as f32;
        if total <= 0.0 {
            return 0.0;
        }
        let available = disk.available_space() as f32;
        round1(((total - available) / total) * 100.0)
    } else {
        0.0
    }
}

fn classify_process_family(name: &str) -> String {
    let normalized = name.to_lowercase();
    if contains_any(&normalized, &["chrome", "brave", "firefox", "edge"]) {
        "browser"
    } else if contains_any(&normalized, &["code", "nvim", "vim", "pycharm", "idea"]) {
        "editor"
    } else if contains_any(
        &normalized,
        &["python", "node", "bun", "cargo", "rust", "java"],
    ) {
        "runtime"
    } else if contains_any(&normalized, &["docker", "podman", "qemu", "vm"]) {
        "infra"
    } else if contains_any(
        &normalized,
        &["pipewire", "pulseaudio", "wireplumber", "spotify", "vlc"],
    ) {
        "media"
    } else {
        "system"
    }
    .to_string()
}

fn contains_any(value: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| value.contains(needle))
}

#[pymodule]
fn nexus_sensors(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SensorEngineRust>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classifies_process_families() {
        assert_eq!(classify_process_family("brave"), "browser");
        assert_eq!(classify_process_family("python3"), "runtime");
        assert_eq!(classify_process_family("dockerd"), "infra");
        assert_eq!(classify_process_family("unknown"), "system");
    }

    #[test]
    fn returns_os_snapshot_json() {
        let mut engine = SensorEngineRust::new();
        let raw = engine.os_snapshot_json().unwrap();
        let snapshot: OsSnapshot = serde_json::from_str(&raw).unwrap();
        assert!(snapshot.cpu_avg >= 0.0);
        assert!(snapshot.ram >= 0.0);
        assert!(snapshot.disk >= 0.0);
        assert!(matches!(
            snapshot.pressure.as_str(),
            "calm" | "stable" | "active" | "critical"
        ));
    }
}
