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
            format!("# Mapa Neural ZEUS (Rust Optimized)"),
            format!(""),
            format!("> Snapshot gerado em {}", timestamp),
            format!(""),
            format!("## Resumo"),
            format!(""),
            format!("| Métrica | Valor |"),
            format!("|---|---|"),
            format!("| Nós totais | {} |", total_nodes),
            format!("| Sinapses totais | {} |", total_synapses),
            format!("| Buffer sensorial | {} |", sensory_size),
            format!(""),
            format!("## Top Nós (por peso)"),
            format!(""),
            format!("| Caminho | Peso | Último Acesso |"),
            format!("|---|---|---|"),
        ];

        for node in top_nodes {
            let basename = node.path.split('/').last().unwrap_or(&node.path);
            lines.push(format!(
                "| `{}` | {} | {} |",
                basename,
                node.weight,
                node.last_accessed.as_deref().unwrap_or("N/A")
            ));
        }

        lines.push(format!(""));
        lines.push(format!("## Sinapses Mais Fortes"));
        lines.push(format!(""));
        lines.push(format!("| Origem | Destino | Peso |"));
        lines.push(format!("|---|---|---|"));

        for syn in top_synapses {
            let src = syn.source.split('/').last().unwrap_or(&syn.source);
            let tgt = syn.target.split('/').last().unwrap_or(&syn.target);
            lines.push(format!("| `{}` | `{}` | {} |", src, tgt, syn.weight));
        }

        lines.join("\n")
    }
}

#[pymodule]
fn zeus_sync(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<SyncEngineRust>()?;
    Ok(())
}
