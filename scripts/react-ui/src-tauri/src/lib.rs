#[cfg_attr(mobile, tauri::mobile_entry_point)]
#[allow(unused_imports)]
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

const PNG_SIGNATURE: &[u8; 8] = b"\x89PNG\r\n\x1a\n";

#[tauri::command]
fn save_thumbnail_png(path: String, contents: Vec<u8>) -> Result<(), String> {
    if contents.len() > 10 * 1024 * 1024 {
        return Err("Thumbnail PNG exceeds the supported size".into());
    }
    if !path.to_ascii_lowercase().ends_with(".png") {
        return Err("Thumbnail must use a .png filename".into());
    }
    if !contents.starts_with(PNG_SIGNATURE) {
        return Err("Thumbnail contents are not a PNG image".into());
    }
    std::fs::write(path, contents).map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::save_thumbnail_png;

    #[test]
    fn rejects_non_png_extensions_before_writing() {
        let error = save_thumbnail_png("thumbnail.jpg".into(), b"not-an-image".to_vec());
        assert_eq!(error.unwrap_err(), "Thumbnail must use a .png filename");
    }

    #[test]
    fn rejects_non_png_content_before_writing() {
        let error = save_thumbnail_png("thumbnail.png".into(), b"not-an-image".to_vec());
        assert_eq!(error.unwrap_err(), "Thumbnail contents are not a PNG image");
    }
}

pub fn run() {
    tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![save_thumbnail_png])
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      app.handle().plugin(tauri_plugin_dialog::init())?;
      app.handle().plugin(tauri_plugin_shell::init())?;

      if cfg!(debug_assertions) {
        println!(
          "Development build: backend sidecar is not auto-started; use run-dev.bat or run-backend.bat."
        );
      } else {
        let sidecar_command = app.handle().shell().sidecar("web_server").map_err(|e| {
          eprintln!("Failed to create sidecar command: {}", e);
          e
        })?;

        match sidecar_command.spawn() {
          Ok((_rx, _child)) => {
            println!("Sidecar spawned successfully");
          }
          Err(e) => {
            eprintln!("CRITICAL: Failed to spawn sidecar: {}", e);
          }
        }
      }

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
