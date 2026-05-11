#![allow(non_local_definitions)]

use chrono::Utc;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Serialize, Deserialize, Clone)]
pub struct EventLog {
    pub kind: String,
    pub timestamp: f64,
    pub data: HashMap<String, String>,
}

#[pyclass]
pub struct PatternEngineRust {
    event_history: Vec<EventLog>,
    habit_counters: HashMap<String, usize>,
    max_history: usize,
}

#[pymethods]
impl PatternEngineRust {
    #[new]
    pub fn new(max_history: usize) -> Self {
        PatternEngineRust {
            event_history: Vec::with_capacity(max_history),
            habit_counters: HashMap::new(),
            max_history,
        }
    }

    pub fn record_event(&mut self, kind: String, timestamp: f64, data: HashMap<String, String>) {
        if self.event_history.len() >= self.max_history {
            self.event_history.remove(0);
        }

        let event = EventLog {
            kind: kind.clone(),
            timestamp,
            data,
        };
        self.event_history.push(event);

        let counter = self.habit_counters.entry(kind).or_insert(0);
        *counter += 1;
    }

    pub fn detect_anomalies(&self, threshold: usize) -> Vec<String> {
        let mut anomalies = Vec::new();

        for (kind, count) in &self.habit_counters {
            if *count > threshold {
                anomalies.push(format!(
                    "Anomalia detectada: excesso de eventos do tipo '{}' ({})",
                    kind, count
                ));
            }
        }

        anomalies
    }

    pub fn get_burst_patterns(&self, window_seconds: f64, burst_threshold: usize) -> Vec<String> {
        if self.event_history.len() < burst_threshold {
            return Vec::new();
        }

        let now = Utc::now().timestamp() as f64;
        let mut bursts = Vec::new();
        let mut counts = HashMap::new();

        for event in self.event_history.iter().rev() {
            if now - event.timestamp > window_seconds {
                break;
            }
            let count = counts.entry(&event.kind).or_insert(0);
            *count += 1;
        }

        for (kind, count) in counts {
            if count >= burst_threshold {
                bursts.push(kind.to_string());
            }
        }

        bursts
    }

    pub fn clear_history(&mut self) {
        self.event_history.clear();
        self.habit_counters.clear();
    }
}

#[pymodule]
fn nexus_patterns(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PatternEngineRust>()?;
    Ok(())
}
