use pyo3::prelude::*;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[pyclass]
#[derive(Serialize, Deserialize, Clone)]
pub struct VectorMemoryRust {
    #[pyo3(get)]
    pub vectors: HashMap<String, Vec<f32>>,
    pub storage_path: String,
}

impl VectorMemoryRust {
    pub fn new_rust(storage_path: String) -> Self {
        let mut mem = VectorMemoryRust {
            vectors: HashMap::new(),
            storage_path,
        };
        let _ = mem.load_rust();
        mem
    }

    pub fn add_vector_rust(&mut self, key: String, vector: Vec<f32>) {
        self.vectors.insert(key, vector);
    }

    pub fn find_similar_rust(&self, query_vector: &[f32], top_k: usize) -> Vec<(String, f32)> {
        if query_vector.is_empty() {
            return vec![];
        }

        let mut similarities: Vec<(&String, f32)> = self
            .vectors
            .par_iter()
            .map(|(key, vector)| {
                let sim = cosine_similarity(query_vector, vector);
                (key, sim)
            })
            .collect();

        similarities.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        similarities
            .into_iter()
            .take(top_k)
            .map(|(key, sim)| (key.clone(), sim))
            .collect()
    }

    pub fn save_rust(&self) -> std::io::Result<()> {
        let file = std::fs::File::create(&self.storage_path)?;
        bincode::serialize_into(file, &self.vectors)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
        Ok(())
    }

    pub fn load_rust(&mut self) -> std::io::Result<()> {
        if !std::path::Path::new(&self.storage_path).exists() {
            return Ok(());
        }
        let file = std::fs::File::open(&self.storage_path)?;
        let decoded: HashMap<String, Vec<f32>> = bincode::deserialize_from(file)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
        self.vectors = decoded;
        Ok(())
    }
}

#[pymethods]
impl VectorMemoryRust {
    #[new]
    pub fn new(storage_path: String) -> Self {
        Self::new_rust(storage_path)
    }

    pub fn add_vector(&mut self, key: String, vector: Vec<f32>) {
        self.add_vector_rust(key, vector);
    }

    pub fn find_similar(
        &self,
        query_vector: Vec<f32>,
        top_k: usize,
    ) -> PyResult<Vec<(String, f32)>> {
        Ok(self.find_similar_rust(&query_vector, top_k))
    }

    pub fn save(&self) -> PyResult<()> {
        self.save_rust()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
    }

    pub fn load(&mut self) -> PyResult<()> {
        self.load_rust()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
    }
}

fn cosine_similarity(v1: &[f32], v2: &[f32]) -> f32 {
    let n = v1.len();
    if n != v2.len() || n == 0 {
        return 0.0;
    }

    let mut dot = 0.0;
    let mut norm_a = 0.0;
    let mut norm_b = 0.0;

    // Hint to compiler for SIMD auto-vectorization
    for i in 0..n {
        let a = v1[i];
        let b = v2[i];
        dot += a * b;
        norm_a += a * a;
        norm_b += b * b;
    }

    if norm_a <= 0.0 || norm_b <= 0.0 {
        return 0.0;
    }
    dot / (norm_a.sqrt() * norm_b.sqrt())
}

#[pymodule]
fn zeus_memory(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<VectorMemoryRust>()?;
    Ok(())
}
