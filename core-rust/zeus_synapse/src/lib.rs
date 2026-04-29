use pyo3::prelude::*;
use rusqlite::{params, Connection, Result};
use chrono::Utc;

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
            ).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        }

        // Atualiza Synapse
        conn.execute(
            "INSERT INTO synapses (source, target, weight, last_interaction) 
             VALUES (?1, ?2, ?3, ?4) 
             ON CONFLICT(source, target) DO UPDATE SET 
                weight = weight + ?3, 
                last_interaction = excluded.last_interaction",
            params![source, target, weight_inc, now],
        ).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

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
        ).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        conn.execute(
            "UPDATE nodes SET weight = MAX(1, CAST(weight * ?1 AS INTEGER))",
            params![factor],
        ).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(())
    }

    /// Busca contextos relacionados (sinapses mais fortes).
    pub fn get_working_context(&self, path: String, limit: usize) -> PyResult<Vec<String>> {
        let conn = Connection::open(&self.db_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let mut stmt = conn.prepare(
            "SELECT target FROM synapses 
             WHERE source = ?1 
             ORDER BY weight DESC, last_interaction DESC 
             LIMIT ?2"
        ).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let rows = stmt.query_map(params![path, limit], |row| {
            row.get(0)
        }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let mut results = Vec::new();
        for row in rows {
            results.push(row.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?);
        }

        Ok(results)
    }
}

#[pymodule]
fn zeus_synapse(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<SynapseManagerRust>()?;
    Ok(())
}
