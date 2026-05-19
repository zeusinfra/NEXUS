use crate::events::RiskLevel;
use std::path::{Path, PathBuf};

#[derive(Clone)]
pub struct Sandbox {
    workspace_root: PathBuf,
}

impl Sandbox {
    pub fn new(workspace_root: impl Into<PathBuf>) -> Self {
        Self {
            workspace_root: workspace_root.into().canonicalize().unwrap_or_default(),
        }
    }

    /// Validates if a given path is safe to operate on (prevents traversal outside workspace)
    pub fn is_path_safe(&self, target_path: &str) -> bool {
        if target_path.contains("..") || target_path.starts_with('~') {
            return false;
        }

        let path = Path::new(target_path);

        // Block known dangerous directories
        if path.starts_with("/etc") || path.starts_with("/bin") || path.starts_with("/sbin") {
            return false;
        }

        // If absolute, must be within workspace
        if path.is_absolute() {
            if let Ok(canonical) = path.canonicalize() {
                return canonical.starts_with(&self.workspace_root);
            }
            return path.starts_with(&self.workspace_root);
        }

        true
    }
}

pub struct RiskClassifier;

impl RiskClassifier {
    pub fn classify(command: &str) -> RiskLevel {
        let first_word = command.split_whitespace().next().unwrap_or("");

        // Critical overrides
        if command.contains("rm -rf /")
            || first_word == "dd"
            || first_word == "mkfs"
            || first_word == "shutdown"
            || first_word == "systemctl"
        {
            return RiskLevel::Critical;
        }
        if command.contains("/etc/") {
            return RiskLevel::Critical;
        }

        match first_word {
            // Safe
            "ls" | "cat" | "grep" | "find" => RiskLevel::Safe,

            // Safe composites
            "git" => {
                if command.contains("status") || command.contains("diff") || command.contains("log")
                {
                    RiskLevel::Safe
                } else {
                    RiskLevel::Moderate
                }
            }
            "cargo" => {
                if command.contains("check") || command.contains("test") {
                    RiskLevel::Safe
                } else {
                    RiskLevel::Moderate // build, run
                }
            }
            "npm" => {
                if command.contains("test") || command.contains("run lint") {
                    RiskLevel::Safe
                } else {
                    RiskLevel::Moderate // install, run build
                }
            }

            // Moderate
            "pip" | "python" | "rustc" => RiskLevel::Moderate,

            // Dangerous
            "rm" | "sudo" | "chmod" | "chown" | "mv" | "cp" | "curl" | "wget" => {
                RiskLevel::Dangerous
            }

            // Default fallback
            _ => RiskLevel::Moderate,
        }
    }
}
