#![allow(non_local_definitions)]

use chrono::Utc;
use pyo3::prelude::*;
use rusqlite::{params, Connection};

#[pyclass]
pub struct SynapseManagerRust {
    db_path: String,
}

#[pymethods]
impl SynapseManagerRust {
    #[new]
    pub fn new(db_path: String) -> Self {
        SynapseManagerRust { db_path }
    }

    /// Atualiza ou cria uma conexão entre dois nós (source -> target).
    /// Executa as operações de forma atômica em Rust.
    pub fn update_synapse(&self, source: String, target: String, weight_inc: i32) -> PyResult<()> {
        let conn = Connection::open(&self.db_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let now = Utc::now().to_rfc3339();

        // Transação para garantir integridade e velocidade
        conn.execute("BEGIN TRANSACTION", [])
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        // Atualiza Nodes
        for path in &[&source, &target] {
            conn.execute(
                "INSERT INTO nodes (path, weight, last_accessed) 
                 VALUES (?1, ?2, ?3) 
                 ON CONFLICT(path) DO UPDATE SET 
                    weight = weight + 1, 
                    last_accessed = excluded.last_accessed",
                params![path, 1, now],
            )
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        }

        // Atualiza Synapse
        conn.execute(
            "INSERT INTO synapses (source, target, weight, last_interaction) 
             VALUES (?1, ?2, ?3, ?4) 
             ON CONFLICT(source, target) DO UPDATE SET 
                weight = weight + ?3, 
                last_interaction = excluded.last_interaction",
            params![source, target, weight_inc, now],
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        conn.execute("COMMIT", [])
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(())
    }

    /// Aplica o fator de "esquecimento" (decay) em massa.
    /// Em Rust, isso é extremamente rápido.
    pub fn decay_memory(&self, factor: f32) -> PyResult<()> {
        let conn = Connection::open(&self.db_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        conn.execute(
            "UPDATE synapses SET weight = MAX(1, CAST(weight * ?1 AS INTEGER))",
            params![factor],
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        conn.execute(
            "UPDATE nodes SET weight = MAX(1, CAST(weight * ?1 AS INTEGER))",
            params![factor],
        )
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(())
    }

    /// Busca contextos relacionados (sinapses mais fortes).
    pub fn get_working_context(&self, path: String, limit: usize) -> PyResult<Vec<String>> {
        let conn = Connection::open(&self.db_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let mut stmt = conn
            .prepare(
                "SELECT target FROM synapses 
             WHERE source = ?1 
             ORDER BY weight DESC, last_interaction DESC 
             LIMIT ?2",
            )
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let rows = stmt
            .query_map(params![path, limit], |row| row.get(0))
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let mut results = Vec::new();
        for row in rows {
            results.push(
                row.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?,
            );
        }

        Ok(results)
    }

    /// [PONTE DE COMANDO] Executa uma operação de alto desempenho diretamente em Rust.
    pub fn call_native_bridge(&self, action: String, payload: String) -> PyResult<String> {
        match action.as_str() {
            "sys_info" => {
                // Simulação de telemetria ultra-rápida em Rust
                Ok(format!("{{ \"status\": \"stable\", \"core_ver\": \"1.5.0-rust\", \"payload\": \"{}\" }}", payload))
            },
            "prune_noise" => {
                // Poda de ruído em massa diretamente no DB
                let conn = Connection::open(&self.db_path)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
                let deleted = conn.execute("DELETE FROM synapses WHERE weight < 2 AND last_interaction < date('now', '-7 days')", [])
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
                Ok(format!("{{ \"deleted\": {} }}", deleted))
            },
            _ => Ok(format!("{{ \"error\": \"Action '{}' not implemented in Rust bridge\" }}", action))
        }
    }
}

#[pymodule]
fn nexus_synapse(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SynapseManagerRust>()?;
    Ok(())
}
