#![allow(non_local_definitions)]

use pyo3::prelude::*;
use regex::{Regex, RegexBuilder};
use std::collections::HashMap;

#[pyclass]
pub struct PrivacyEngineRust {
    patterns: HashMap<String, Regex>,
    sensitive_paths: Vec<Regex>,
}

#[pymethods]
impl PrivacyEngineRust {
    #[new]
    pub fn new() -> Self {
        let mut patterns = HashMap::new();

        // Usando r#""# para suportar aspas internas sem escape
        let secret_patterns = [
            ("openai_key", r"sk-[a-zA-Z0-9]{48}"),
            (
                "generic_key",
                r#"(?i)(api[_-]?key|secret|password|token)['"]?\s*[:=]\s*['"]?([a-zA-Z0-9]{16,})['"]?"#,
            ),
            ("env_file", r"(?m)^[A-Z_]+=[^\n]+$"),
            (
                "auth_header",
                r#"(?i)Authorization:\s*(Bearer|Basic)\s+[a-zA-Z0-9\._\-+/=]+"#,
            ),
        ];

        for (name, pattern) in secret_patterns {
            match RegexBuilder::new(pattern)
                .case_insensitive(true)
                .multi_line(true)
                .build()
            {
                Ok(re) => {
                    patterns.insert(name.to_string(), re);
                }
                Err(e) => {
                    eprintln!("[NEXUS RUST ERROR] Falha ao compilar regex {}: {}", name, e);
                }
            }
        }

        let sensitive_paths_raw = [
            r"\.ssh/",
            r"\.env",
            r"\.aws/",
            r"config/.*secret",
            r"nexus_events\.db",
        ];

        let mut sensitive_paths = Vec::new();
        for pattern in sensitive_paths_raw {
            if let Ok(re) = Regex::new(pattern) {
                sensitive_paths.push(re);
            }
        }

        PrivacyEngineRust {
            patterns,
            sensitive_paths,
        }
    }

    pub fn sanitize(&self, content: String) -> (String, usize) {
        let mut sanitized = content;
        let mut total_masked = 0;

        for (name, re) in &self.patterns {
            let mask = format!("[MASKED_{}]", name.to_uppercase());

            // Contagem de matches antes da substituição
            let count = re.find_iter(&sanitized).count();
            if count > 0 {
                total_masked += count;
                sanitized = re.replace_all(&sanitized, mask.as_str()).to_string();
            }
        }

        (sanitized, total_masked)
    }

    pub fn classify(&self, content: &str) -> i32 {
        // Levels: 0=PUBLIC, 1=LOCAL_SENSITIVE, 2=HIGHLY_SENSITIVE, 3=SECRET

        for re in self.patterns.values() {
            if re.is_match(content) {
                return 3; // SECRET
            }
        }

        for re in &self.sensitive_paths {
            if re.is_match(content) {
                return 2; // HIGHLY_SENSITIVE
            }
        }

        let content_lower = content.to_lowercase();
        if (content_lower.contains("habits") || content_lower.contains("workflow"))
            && (content_lower.contains("detected") || content_lower.contains("observed"))
        {
            return 2; // HIGHLY_SENSITIVE
        }

        if content.len() > 10 {
            return 1; // LOCAL_SENSITIVE
        }

        0 // PUBLIC
    }
}

impl Default for PrivacyEngineRust {
    fn default() -> Self {
        Self::new()
    }
}

#[pymodule]
fn nexus_security(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PrivacyEngineRust>()?;
    Ok(())
}
