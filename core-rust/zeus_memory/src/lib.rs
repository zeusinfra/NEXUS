use pyo3::prelude::*;
use std::collections::HashMap;
use rayon::prelude::*;

#[pyclass]
pub struct VectorMemoryRust {
    #[pyo3(get)]
    pub vectors: HashMap<String, Vec<f32>>,
    pub storage_path: String,
}

#[pymethods]
impl VectorMemoryRust {
    #[new]
    pub fn new(storage_path: String) -> Self {
        let mut mem = VectorMemoryRust {
            vectors: HashMap::new(),
            storage_path,
        };
        let _ = mem.load(); // Tenta carregar ao iniciar
        mem
    }

    pub fn add_vector(&mut self, key: String, vector: Vec<f32>) {
        self.vectors.insert(key, vector);
    }

    /// Encontra os top_k vetores mais similares usando Cosine Similarity.
    /// Utiliza 'rayon' para processar milhares de vetores em paralelo.
    pub fn find_similar(&self, query_vector: Vec<f32>, top_k: usize) -> PyResult<Vec<(String, f32)>> {
        if query_vector.is_empty() {
            return Ok(vec![]);
        }

        let mut similarities: Vec<(&String, f32)> = self.vectors
            .par_iter() // Processamento paralelo automático!
            .map(|(key, vector)| {
                let sim = cosine_similarity(&query_vector, vector);
                (key, sim)
            })
            .collect();

        // Ordena por similaridade (maior primeiro)
        similarities.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        // Retorna os top_k
        let result = similarities.into_iter()
            .take(top_k)
            .map(|(key, sim)| (key.clone(), sim))
            .collect();

        Ok(result)
    }

    /// Salva os vetores em formato binário (bincode).
    /// Muito mais rápido e compacto que JSON.
    pub fn save(&self) -> PyResult<()> {
        let file = std::fs::File::create(&self.storage_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        bincode::serialize_into(file, &self.vectors)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        
        Ok(())
    }

    /// Carrega os vetores do arquivo binário.
    pub fn load(&mut self) -> PyResult<()> {
        if !std::path::Path::new(&self.storage_path).exists() {
            return Ok(());
        }

        let file = std::fs::File::open(&self.storage_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        let decoded: HashMap<String, Vec<f32>> = bincode::deserialize_from(file)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
        
        self.vectors = decoded;
        Ok(())
    }
}

/// Função auxiliar para cálculo de similaridade de cosseno otimizada
fn cosine_similarity(v1: &[f32], v2: &[f32]) -> f32 {
    if v1.len() != v2.len() { return 0.0; }
    
    let mut dot_product = 0.0;
    let mut norm_a = 0.0;
    let mut norm_b = 0.0;

    for i in 0..v1.len() {
        dot_product += v1[i] * v2[i];
        norm_a += v1[i] * v1[i];
        norm_b += v2[i] * v2[i];
    }

    if norm_a <= 0.0 || norm_b <= 0.0 {
        return 0.0;
    }

    dot_product / (norm_a.sqrt() * norm_b.sqrt())
}

#[pymodule]
fn zeus_memory(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<VectorMemoryRust>()?;
    Ok(())
}
