use notify::{Watcher, RecursiveMode, Config};
use serde::{Serialize, Deserialize};
use std::path::Path;
use std::sync::mpsc::channel;
use walkdir::WalkDir;
use std::io::{self, Write};
use std::thread;
use std::time::Duration;

#[derive(Serialize, Deserialize, Debug)]
struct FileEvent {
    event_type: String,
    path: String,
    project: String,
}

fn get_project(path: &Path) -> String {
    let path_str = path.to_string_lossy();
    if path_str.contains("ZEUS_BRAIN") {
        return "ZEUS_BRAIN".to_string();
    }
    if path_str.contains("ZEUS_SYSTEM") {
        return "ZEUS_SYSTEM".to_string();
    }
    "unknown".to_string()
}

fn is_ignored(path: &Path) -> bool {
    let ignored = [
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        "target",
        "dist",
        ".cache",
        ".dart_tool",
        ".gradle",
        "build",
        "logs",
        "vector_db",
    ];
    for part in path.components() {
        let p = part.as_os_str().to_string_lossy();
        if p.starts_with('.') || ignored.contains(&p.as_ref()) {
            return true;
        }
        // Evita tempestade de eventos de artefatos pesados mobile/dev.
        if p == "zeus_extension" {
            return true;
        }
    }
    false
}

fn scan_files(root: &str) {
    let mut emitted = 0usize;
    for entry in WalkDir::new(root).into_iter().filter_map(|e| e.ok()) {
        if entry.file_type().is_file() && !is_ignored(entry.path()) {
            let ev = FileEvent {
                event_type: "SCAN".to_string(),
                path: entry.path().to_string_lossy().into_owned(),
                project: get_project(entry.path()),
            };
            println!("{}", serde_json::to_string(&ev).unwrap());
            emitted += 1;
            if emitted % 40 == 0 {
                io::stdout().flush().unwrap();
                thread::sleep(Duration::from_millis(12));
            }
        }
    }
    io::stdout().flush().unwrap();
}

fn main() {
    let skip_initial_scan = std::env::var("ZEUS_WATCHER_SKIP_INITIAL_SCAN")
        .unwrap_or_else(|_| "1".to_string())
        .to_lowercase();
    let skip_initial_scan = matches!(skip_initial_scan.as_str(), "1" | "true" | "yes" | "on");

    let watch_dirs = vec![
        format!("{}/Documentos/ZEUS_BRAIN", std::env::var("HOME").unwrap_or_else(|_| "/home/zeus".to_string())),
        format!("{}/Documentos/ZEUS_SYSTEM", std::env::var("HOME").unwrap_or_else(|_| "/home/zeus".to_string())),
    ];

    // Initial scan (opt-in). Por padrao desativado para reduzir latencia no boot.
    if !skip_initial_scan {
        for dir in &watch_dirs {
            scan_files(dir);
        }
    }

    let (tx, rx) = channel();
    let mut watcher = notify::RecommendedWatcher::new(tx, Config::default()).expect("Error creating watcher");

    for dir in watch_dirs {
        if Path::new(&dir).exists() {
            watcher.watch(Path::new(&dir), RecursiveMode::Recursive).expect("Error watching dir");
        }
    }

    for res in rx {
        match res {
            Ok(event) => {
                for path in event.paths {
                    if !is_ignored(&path) {
                        let ev = FileEvent {
                            event_type: format!("{:?}", event.kind),
                            path: path.to_string_lossy().into_owned(),
                            project: get_project(&path),
                        };
                        println!("{}", serde_json::to_string(&ev).unwrap());
                        io::stdout().flush().unwrap();
                    }
                }
            }
            Err(e) => eprintln!("Watch error: {:?}", e),
        }
    }
}
