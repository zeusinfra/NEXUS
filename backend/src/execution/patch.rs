use crate::events::{SystemEvent, EventBus};
use std::fs;
use std::path::{Path, PathBuf};
use chrono::Utc;
use similar::{ChangeTag, TextDiff};

#[derive(Clone)]
pub struct FilePatchEngine {
    event_bus: EventBus,
    workspace_root: PathBuf,
}

impl FilePatchEngine {
    pub fn new(event_bus: EventBus, workspace_root: impl Into<PathBuf>) -> Self {
        Self {
            event_bus,
            workspace_root: workspace_root.into(),
        }
    }

    pub async fn apply_patch(&self, relative_path: &str, new_content: &str) -> Result<String, String> {
        let target_path = self.workspace_root.join(relative_path);
        let mut old_content = String::new();
        let mut backup_path_str = String::new();
        
        // 1. Create Backup and Read Old Content
        if target_path.exists() {
            old_content = fs::read_to_string(&target_path).unwrap_or_default();
            let timestamp = Utc::now().format("%Y%m%d_%H%M%S").to_string();
            let backup_dir = self.workspace_root.join(format!(".nexus/backups/{}", timestamp));
            
            fs::create_dir_all(&backup_dir).map_err(|e| e.to_string())?;
            
            let backup_file = backup_dir.join(Path::new(relative_path).file_name().unwrap_or_default());
            fs::copy(&target_path, &backup_file).map_err(|e| e.to_string())?;
            
            backup_path_str = backup_file.to_string_lossy().to_string();

            let _ = self.event_bus.publish(SystemEvent::RollbackCreated {
                backup_path: backup_path_str.clone(),
            });
        }

        // 2. Generate Diff using 'similar'
        let diff = TextDiff::from_lines(&old_content, new_content);
        let mut unified_diff = String::new();
        for op in diff.ops() {
            for change in diff.iter_changes(op) {
                let sign = match change.tag() {
                    ChangeTag::Delete => "-",
                    ChangeTag::Insert => "+",
                    ChangeTag::Equal => " ",
                };
                unified_diff.push_str(&format!("{}{}", sign, change));
            }
        }

        let _ = self.event_bus.publish(SystemEvent::PatchPreview {
            path: relative_path.to_string(),
            diff: unified_diff.clone(),
        });

        // 3. Write new content
        if let Some(parent) = target_path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        
        fs::write(&target_path, new_content).map_err(|e| e.to_string())?;

        // 4. Emit Patched event
        let _ = self.event_bus.publish(SystemEvent::FilePatched {
            path: relative_path.to_string(),
        });

        Ok(unified_diff)
    }

    pub async fn rollback(&self, relative_path: &str, backup_path: &str) -> Result<(), String> {
        let target_path = self.workspace_root.join(relative_path);
        let backup_path = PathBuf::from(backup_path);
        
        if backup_path.exists() {
            fs::copy(&backup_path, &target_path).map_err(|e| e.to_string())?;
            Ok(())
        } else {
            Err("Backup file not found".to_string())
        }
    }
}
