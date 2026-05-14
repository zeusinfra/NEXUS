#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::api::process::{Command, CommandEvent};
use tauri::{CustomMenuItem, SystemTray, SystemTrayMenu, SystemTrayMenuItem, SystemTrayEvent};

fn main() {
    let quit = CustomMenuItem::new("quit".to_string(), "Sair");
    let hide = CustomMenuItem::new("hide".to_string(), "Ocultar");
    let show = CustomMenuItem::new("show".to_string(), "Mostrar");
    let tray_menu = SystemTrayMenu::new()
        .add_item(show)
        .add_item(hide)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit);

    let system_tray = SystemTray::new().with_menu(tray_menu);

    tauri::Builder::default()
        .system_tray(system_tray)
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::MenuItemClick { id, .. } => {
                match id.as_str() {
                    "quit" => {
                        std::process::exit(0);
                    }
                    "hide" => {
                        let window = app.get_window("main").unwrap();
                        window.hide().unwrap();
                    }
                    "show" => {
                        let window = app.get_window("main").unwrap();
                        window.show().unwrap();
                    }
                    _ => {}
                }
            }
            _ => {}
        })
        .setup(|app| {
            let app_handle = app.handle();
            
            // Spawn the Sidecar Watchdog
            tauri::async_runtime::spawn(async move {
                loop {
                    println!("🚀 [NEXUS SHELL] Iniciando Backend Watchdog...");
                    let (mut rx, child) = Command::new_sidecar("nexus-backend")
                        .expect("Failed to create nexus-backend sidecar")
                        .spawn()
                        .expect("Failed to spawn nexus-backend sidecar");

                    let app_handle_clone = app_handle.clone();
                    
                    // Monitorar o processo
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                println!("Backend: {}", line);
                            }
                            CommandEvent::Stderr(line) => {
                                eprintln!("Backend Error: {}", line);
                            }
                            CommandEvent::Terminated(payload) => {
                                eprintln!("⚠️ [NEXUS SHELL] Backend encerrado inesperadamente (Code: {:?}). Reiniciando em 3s...", payload.code);
                                break; // Sai do loop interno para reiniciar
                            }
                            _ => {}
                        }
                    }
                    
                    tokio::time::sleep(std::time::Duration::from_secs(3)).await;
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
