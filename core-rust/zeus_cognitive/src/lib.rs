use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Serialize, Deserialize, Clone)]
pub struct Goal {
    pub title: String,
    pub priority: f32,
    #[serde(rename = "type")]
    pub gtype: String,
    pub risk: String,
}

#[pyclass]
pub struct CognitiveEngineRust {}

impl CognitiveEngineRust {
    fn score_goal(&self, goal: &Goal, context: &Value) -> f32 {
        let mut score = goal.priority;
        let attention_state = context
            .get("attention")
            .and_then(|a| a.get("state"))
            .and_then(|v| v.as_str())
            .unwrap_or("idle");

        match attention_state {
            "development" => {
                if goal.gtype == "technical" || goal.gtype == "operational" {
                    score *= 1.2;
                } else if goal.gtype == "maintenance" {
                    score *= 0.8;
                }
            }
            "deep_focus" => {
                if goal.gtype == "security" {
                    score *= 1.5;
                } else {
                    score *= 0.5;
                }
            }
            "mining" => {
                if goal.gtype == "maintenance" {
                    score *= 1.3;
                } else {
                    score *= 0.7;
                }
            }
            _ => {}
        }

        if goal.risk == "high" {
            score += 20.0;
        }

        score
    }
}

#[pymethods]
impl CognitiveEngineRust {
    #[new]
    pub fn new() -> Self {
        CognitiveEngineRust {}
    }

    pub fn orchestrate(
        &self,
        goals_json: String,
        context_json: String,
        max_active: usize,
    ) -> PyResult<String> {
        let goals: Vec<Goal> = serde_json::from_str(&goals_json).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid Goals JSON: {}", e))
        })?;
        let context: Value = serde_json::from_str(&context_json).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid Context JSON: {}", e))
        })?;

        // 1. Calculate capacity
        let mut capacity = max_active;
        let sys = context.get("perception").and_then(|p| p.get("system"));
        if let Some(sys) = sys {
            let cpu = sys
                .get("cpu_percent")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let ram = sys
                .get("ram_percent")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            if cpu > 85.0 || ram > 90.0 {
                capacity = capacity.saturating_sub(1);
            }
        }

        // 2. Score goals
        let mut scored_goals: Vec<(f32, Goal)> = goals
            .into_iter()
            .map(|g| {
                let score = self.score_goal(&g, &context);
                (score, g)
            })
            .collect();

        // 3. Sort
        scored_goals.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        // 4. Split
        let selected: Vec<Goal> = scored_goals
            .iter()
            .take(capacity)
            .map(|x| x.1.clone())
            .collect();
        let deferred: Vec<Goal> = scored_goals
            .iter()
            .skip(capacity)
            .map(|x| x.1.clone())
            .collect();

        let result = serde_json::json!({
            "selected": selected,
            "deferred": deferred,
            "rationale": format!("Selecionadas {} metas. Capacidade: {}.", selected.len(), capacity)
        });

        Ok(result.to_string())
    }
}

#[pymodule]
fn zeus_cognitive(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<CognitiveEngineRust>()?;
    Ok(())
}
