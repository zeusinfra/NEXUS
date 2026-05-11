#![allow(non_local_definitions)]

use dashmap::DashMap;
use pyo3::prelude::*;
use serde_json::Value;
use std::sync::Arc;

#[pyclass]
pub struct BlackboardRust {
    state: Arc<DashMap<String, Value>>,
}

#[pymethods]
impl BlackboardRust {
    #[new]
    pub fn new() -> Self {
        BlackboardRust {
            state: Arc::new(DashMap::new()),
        }
    }

    pub fn set(&self, key: String, value_json: String) -> PyResult<()> {
        let value: Value = serde_json::from_str(&value_json).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
        })?;
        self.state.insert(key, value);
        Ok(())
    }

    pub fn get(&self, key: String) -> PyResult<Option<String>> {
        match self.state.get(&key) {
            Some(v) => {
                let json = serde_json::to_string(v.value()).map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                        "Serialization error: {}",
                        e
                    ))
                })?;
                Ok(Some(json))
            }
            None => Ok(None),
        }
    }

    pub fn update_nested(&self, key: String, path: String, value_json: String) -> PyResult<()> {
        let new_val: Value = serde_json::from_str(&value_json).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
        })?;

        let mut entry = self
            .state
            .entry(key)
            .or_insert_with(|| Value::Object(serde_json::Map::new()));

        if let Some(obj) = entry.as_object_mut() {
            obj.insert(path, new_val);
        }

        Ok(())
    }

    pub fn keys(&self) -> Vec<String> {
        self.state.iter().map(|r| r.key().clone()).collect()
    }

    pub fn clear(&self) {
        self.state.clear();
    }
}

impl Default for BlackboardRust {
    fn default() -> Self {
        Self::new()
    }
}

#[pymodule]
fn zeus_state(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BlackboardRust>()?;
    Ok(())
}
