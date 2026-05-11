#![allow(non_local_definitions)]

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub struct SyncNode {
    pub path: String,
    pub weight: usize,
    pub last_accessed: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct SyncSynapse {
    pub source: String,
    pub target: String,
    pub weight: usize,
}

#[pyclass]
pub struct SyncEngineRust {}

#[pymethods]
impl SyncEngineRust {
    #[new]
    pub fn new() -> Self {
        SyncEngineRust {}
    }

    pub fn format_neural_map(
        &self,
        timestamp: String,
        total_nodes: usize,
        total_synapses: usize,
        sensory_size: usize,
        top_nodes_json: String,
        top_synapses_json: String,
    ) -> String {
        let top_nodes: Vec<SyncNode> = serde_json::from_str(&top_nodes_json).unwrap_or_default();
        let top_synapses: Vec<SyncSynapse> =
            serde_json::from_str(&top_synapses_json).unwrap_or_default();

        let mut lines = vec![
            "# Mapa Neural ZEUS (Rust Optimized)".to_string(),
            String::new(),
            format!("> Snapshot gerado em {}", timestamp),
            String::new(),
            "## Resumo".to_string(),
            String::new(),
            "| Métrica | Valor |".to_string(),
            "|---|---|".to_string(),
            format!("| Nós totais | {} |", total_nodes),
            format!("| Sinapses totais | {} |", total_synapses),
            format!("| Buffer sensorial | {} |", sensory_size),
            String::new(),
            "## Top Nós (por peso)".to_string(),
            String::new(),
            "| Caminho | Peso | Último Acesso |".to_string(),
            "|---|---|---|".to_string(),
        ];

        for node in top_nodes {
            let basename = node.path.split('/').next_back().unwrap_or(&node.path);
            lines.push(format!(
                "| `{}` | {} | {} |",
                basename,
                node.weight,
                node.last_accessed.as_deref().unwrap_or("N/A")
            ));
        }

        lines.push(String::new());
        lines.push("## Sinapses Mais Fortes".to_string());
        lines.push(String::new());
        lines.push("| Origem | Destino | Peso |".to_string());
        lines.push("|---|---|---|".to_string());

        for syn in top_synapses {
            let src = syn.source.split('/').next_back().unwrap_or(&syn.source);
            let tgt = syn.target.split('/').next_back().unwrap_or(&syn.target);
            lines.push(format!("| `{}` | `{}` | {} |", src, tgt, syn.weight));
        }

        lines.join("\n")
    }
}

impl Default for SyncEngineRust {
    fn default() -> Self {
        Self::new()
    }
}

#[pymodule]
fn zeus_sync(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<SyncEngineRust>()?;
    Ok(())
}
