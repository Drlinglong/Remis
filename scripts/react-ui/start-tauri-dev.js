// scripts/react-ui/start-tauri-dev.js
import { spawn } from 'child_process';
import fs from 'fs';
import net from 'net';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Helper to find a free port starting from a default port
function findFreePort(startPort) {
    return new Promise((resolve) => {
        const server = net.createServer();
        server.listen(startPort, '127.0.0.1', () => {
            const port = server.address().port;
            server.close(() => resolve(port));
        });
        server.on('error', () => {
            resolve(findFreePort(startPort + 1));
        });
    });
}

async function main() {
    const startPort = 5174;
    const port = await findFreePort(startPort);
    console.log(`\n=================================================================`);
    console.log(`[Remis Port Finder] Dynamically allocated port: ${port}`);
    console.log(`=================================================================\n`);

    // 1. Start Vite dev server on the allocated port
    // We run it with strictPort to ensure it binds exactly to the allocated port
    console.log(`[Remis Dev] Starting Vite dev server on port ${port}...`);
    const viteProcess = spawn('npx', ['vite', '--port', port.toString(), '--strictPort'], {
        stdio: 'inherit',
        shell: true
    });

    // 2. Start Tauri dev, pointing to the dynamically allocated port
    // We also read src-tauri/tauri.dev.conf.json to merge any custom configuration
    let devConfig = {};
    const devConfigPath = path.join(__dirname, 'src-tauri', 'tauri.dev.conf.json');
    if (fs.existsSync(devConfigPath)) {
        try {
            devConfig = JSON.parse(fs.readFileSync(devConfigPath, 'utf-8'));
        } catch (e) {
            console.error('[Remis Dev] Failed to parse tauri.dev.conf.json:', e);
        }
    }

    console.log(`[Remis Dev] Launching Tauri desktop shell connected to http://127.0.0.1:${port}...`);
    const mergedConfig = {
        ...devConfig,
        build: {
            ...devConfig.build,
            devUrl: `http://127.0.0.1:${port}`
        }
    };
    const tauriConfigOverride = JSON.stringify(mergedConfig);

    const tauriProcess = spawn('npx', ['tauri', 'dev', '--no-dev-server', '--config', tauriConfigOverride], {
        stdio: 'inherit',
        shell: true
    });

    // Handle clean process termination
    const cleanUp = () => {
        console.log('\n[Remis Dev] Shutting down Vite and Tauri development servers...');
        viteProcess.kill('SIGINT');
        tauriProcess.kill('SIGINT');
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
        process.exit(code);
    });
}

main().catch((err) => {
    console.error('[Remis Dev] Failed to start development launcher:', err);
    process.exit(1);
});
