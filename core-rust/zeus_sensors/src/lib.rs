use pyo3::prelude::*;
use walkdir::WalkDir;
use sysinfo::{System, Networks, Components, Disks, Users};
use std::collections::HashMap;
use std::time::UNIX_EPOCH;

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
        
        let cpu_usage = self.sys.global_cpu_info().cpu_usage();
        let mem_usage = (self.sys.used_memory() as f32 / self.sys.total_memory() as f32) * 100.0;
        
        let mut metrics = HashMap::new();
        metrics.insert("cpu".to_string(), cpu_usage);
        metrics.insert("mem".to_string(), mem_usage);
        
        metrics
    }

    pub fn fast_walk(&self, root: String, max_checked: usize) -> Vec<(String, f64)> {
        let mut results = Vec::new();
        let mut checked = 0;

        for entry in WalkDir::new(root)
            .into_iter()
            .filter_entry(|e| {
                let name = e.file_name().to_string_lossy();
                // Pruning comum em Rust
                !name.starts_with('.') && name != "node_modules" && name != "target" && name != "venv" && name != "__pycache__"
            })
            .filter_map(|e| e.ok()) 
        {
            if entry.file_type().is_file() {
                if let Ok(metadata) = entry.metadata() {
                    if let Ok(mtime) = metadata.modified() {
                        let secs = mtime.duration_since(UNIX_EPOCH).unwrap_or_default().as_secs_f64();
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

#[pymodule]
fn zeus_sensors(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<SensorEngineRust>()?;
    Ok(())
}
