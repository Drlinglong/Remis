// in src/services/fileService.ts

/**
 * 弹出操作系统的文件/文件夹选择对话框。
 * 注意：此功能在浏览器开发环境中是受限的。
 * 我们将使用一个标准的 <input type="file"> 作为临时的、兼容性好的替代方案。
 * 在最终的Tauri/Electron打包版本中，这里将被替换为真正的原生API调用。
 */
import { open } from '@tauri-apps/plugin-dialog';

/**
 * Opens a native directory selection dialog using Tauri.
 * Falls back to a browser file input if Tauri is not available.
 */
export const openProjectDialog = async (): Promise<string | null> => {
  try {
    // Attempt to open native dialog
    // The open function returns null if cancelled, or string/string[] if selected.
    // We configured directory: true, multiple: false.
    const selected = await open({
      directory: true,
      multiple: false,
      title: "Select Mod Directory"
    });

    return selected as string | null;
  } catch (err) {
    console.warn("Tauri Native Dialog failed or not available, falling back to browser mock:", err);
    return openLegacyBrowserDialog();
  }
};

const openLegacyBrowserDialog = (): Promise<string | null> => {
  return new Promise((resolve) => {
    // 1. Create hidden input
    const input = document.createElement('input');
    input.type = 'file';
    // Enable folder selection for webkit browsers
    input.setAttribute('webkitdirectory', 'true');
    input.setAttribute('directory', 'true');

    // 2. Listen for change
    input.onchange = (event) => {
      const target = event.target as HTMLInputElement;
      if (target.files && target.files.length > 0) {
        // In browser, we only get the name, not full path.
        // This acts as a simulator for development.
        // Actually, for webkitdirectory, files[0].webkitRelativePath might exist?
        // But for "Select Folder", getting the folder name is usually done via files[0].webkitRelativePath.split('/')[0]
        const file = target.files[0];
        let folderName = file.name;
        if (file.webkitRelativePath) {
          folderName = file.webkitRelativePath.split('/')[0];
        }
        console.log(`[Dev Mode] Folder selected: ${folderName}`);
        resolve(folderName);
      } else {
        resolve(null);
      }
    };

    // 3. Trigger
    input.click();
  });
};
