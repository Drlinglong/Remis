// scripts/react-ui/start-tauri-dev.js
import { execFileSync, spawn } from 'child_process';
import fs from 'fs';
import net from 'net';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';
import { loadTauriDevConfig, resolveTauriDevProfile } from './tauriDevProfile.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const npxCommand = process.platform === 'win32' ? 'npx.cmd' : 'npx';

function isWindowsProcessRunning(imageName) {
    if (process.platform !== 'win32') {
        return false;
    }

    try {
        const output = execFileSync(
            'tasklist',
            ['/FI', `IMAGENAME eq ${imageName}`, '/FO', 'CSV', '/NH'],
            { encoding: 'utf-8', windowsHide: true }
        );
        return output.toLowerCase().includes(imageName.toLowerCase());
    } catch {
        return false;
    }
}

function ensureNoRunningTauriDevApp() {
    const tauriDevExe = 'remis-mod-factory.exe';
    if (!isWindowsProcessRunning(tauriDevExe)) {
        return;
    }

    console.error('\n[Remis Dev] Another Remis desktop development window is already running.');
    console.error(`[Remis Dev] Close ${tauriDevExe} before starting run-dev.bat again.`);
    console.error('[Remis Dev] If the window is gone but the process is stuck, run stop-dev.bat from the project root.');
    process.exit(1);
}

function assertPortAvailable(port) {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.listen(port, '127.0.0.1', () => {
            server.close(() => resolve(port));
        });
        server.on('error', (error) => {
            reject(new Error(`Frontend port ${port} is unavailable: ${error.message}`));
        });
    });
}

async function main() {
    ensureNoRunningTauriDevApp();

    const profile = resolveTauriDevProfile(
        process.env.VITE_REMIS_BUILD_CHANNEL,
        process.env.REMIS_FRONTEND_PORT,
    );
    const port = await assertPortAvailable(profile.port);
    console.log(`\n=================================================================`);
    console.log(`[Remis Dev] Build channel: ${profile.channel}`);
    console.log(`[Remis Dev] Fixed frontend port: ${port}`);
    console.log(`=================================================================\n`);

    // 1. Start Vite dev server on the allocated port
    // We run it with strictPort to ensure it binds exactly to the allocated port
    console.log(`[Remis Dev] Starting Vite dev server on port ${port}...`);
    const viteProcess = spawn(npxCommand, ['vite', '--port', port.toString(), '--strictPort'], {
        stdio: 'inherit',
        shell: true
    });

    console.log(`[Remis Dev] Launching Tauri desktop shell connected to http://127.0.0.1:${port}...`);
    const mergedConfig = loadTauriDevConfig(__dirname, profile);
    const tauriConfigOverride = JSON.stringify(mergedConfig);
    const tauriConfigPath = path.join(os.tmpdir(), `remis-tauri-dev-${process.pid}.json`);
    fs.writeFileSync(tauriConfigPath, tauriConfigOverride, 'utf-8');

    const tauriProcess = spawn(npxCommand, ['tauri', 'dev', '--no-dev-server', '--config', tauriConfigPath], {
        stdio: 'inherit',
        shell: true
    });

    // Handle clean process termination
    const cleanUp = () => {
        console.log('\n[Remis Dev] Shutting down Vite and Tauri development servers...');
        viteProcess.kill('SIGINT');
        tauriProcess.kill('SIGINT');
        fs.rmSync(tauriConfigPath, { force: true });
        process.exit(0);
    };

    process.on('SIGINT', cleanUp);
    process.on('SIGTERM', cleanUp);

    // Let the processes handle their own error exits
    viteProcess.on('exit', (code) => {
        if (code !== 0) console.error(`[Remis Dev] Vite process exited with code ${code}`);
    });
    tauriProcess.on('exit', (code) => {
        if (code !== 0) console.error(`[Remis Dev] Tauri process exited with code ${code}`);
        viteProcess.kill('SIGINT');
        fs.rmSync(tauriConfigPath, { force: true });
        process.exit(code);
    });
}

main().catch((err) => {
    console.error('[Remis Dev] Failed to start development launcher:', err);
    process.exit(1);
});
