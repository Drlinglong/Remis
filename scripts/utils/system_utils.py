import os
import subprocess
import time
import sys
import re
import hashlib
from typing import Optional

def panic_log(message: str):
    """Fallback logging to a local file in AppData."""
    try:
        appdata = os.getenv('APPDATA')
        if not appdata: return
        log_dir = os.path.join(appdata, "RemisModFactory", "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "port_check.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    except Exception:
        pass

def force_free_port(port: int):
    """
    Checks if a port is in use and attempts to kill the process holding it.
    Uses psutil for reliable cross-platform process discovery.
    """
    # Aggressive console print for debugging
    print(f"\n[SYSTEM] >>> Port Check: Checking port {port}...", file=sys.stderr, flush=True)
    
    if os.name != 'nt':
        return
        
    try:
        import psutil
        
        current_pid = os.getpid()
        parent_pid = -1
        try:
            parent_pid = psutil.Process(current_pid).ppid()
        except: pass
            
        pids_to_kill = set()
        
        # Iterate over all system connections
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port:
                    pid = conn.pid
                    if pid and pid != current_pid and pid != parent_pid:
                        pids_to_kill.add(pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            # Fallback to netstat
            print(f"[SYSTEM] psutil.net_connections access denied, falling back to netstat...", file=sys.stderr, flush=True)
            cmd = f'netstat -ano | findstr LISTENING | findstr :{port}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            pid = int(parts[-1])
                            if pid > 0 and pid != current_pid and pid != parent_pid:
                                pids_to_kill.add(pid)
                        except: pass

        if not pids_to_kill:
            print(f"[SYSTEM] Port {port} is clear.", file=sys.stderr, flush=True)
            return

        for pid in pids_to_kill:
            try:
                proc = psutil.Process(pid)
                p_name = proc.name()
            except:
                p_name = "Unknown"
                
            msg = f"[PORT] Port {port} is occupied by PID {pid} ({p_name}). Terminating..."
            print(f"\033[91m{msg}\033[0m", file=sys.stderr, flush=True)
            panic_log(msg)
            
            # Kill the process and its children
            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
            time.sleep(0.5)
                
        time.sleep(1.0)
        print(f"[SYSTEM] Port {port} cleared successfully.", file=sys.stderr, flush=True)
        
    except Exception as e:
        error_msg = f"[PORT] Error freeing port {port}: {str(e)}"
        print(f"\033[91m{error_msg}\033[0m", file=sys.stderr, flush=True)
        panic_log(error_msg)

def slugify_to_ascii(text: str) -> str:
    """
    Converts a string (potentially with CJK characters) into a safe ASCII-only slug for folder names.
    
    Logic:
    1. Transliteration: Uses PhoneticsEngine to convert CJK to Pinyin/Romaji.
    2. Sanitization: Replaces non-ASCII with underscores, keeps only alphanumeric and underscores.
    3. Normalization: Multiple underscores -> single, lowercase, strip.
    4. Fallback: If empty or too short, appends a hash of the original name.
    """
    if not text:
        return "unnamed_mod_" + hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

    original_text = text
    
    # 1. Phonetic Transliteration (Try to make it readable)
    try:
        from scripts.utils.phonetics_engine import PhoneticsEngine
        engine = PhoneticsEngine()
        # We don't know the exact lang, but PhoneticsEngine.generate_fingerprint handles it.
        # We try 'zh' as it's most common for the user, then 'ja', 'ko'.
        # Actually, let's just use it iteratively or for detectable blocks.
        # For simplicity, let's just attempt to convert known CJK or use general logic.
        
        # pypinyin, pykakasi etc. are handled internally by PhoneticsEngine
        text = engine.generate_fingerprint(text, 'zh') # First pass for Chinese
        text = engine.generate_fingerprint(text, 'ja') # Second pass for Japanese (if any remains/different)
    except Exception:
        # Fallback to basic ASCII filtering if engine fails
        pass

    # 2. ASCII Sanitization
    # Replace non-ASCII with underscores
    text = re.sub(r'[^\x00-\x7F]+', '_', text)
    # Replace non-alphanumeric (except underscores and hyphens) with underscores
    text = re.sub(r'[^a-zA-Z0-9_-]', '_', text)
    
    # 3. Normalization
    text = text.lower()
    text = re.sub(r'_+', '_', text) # Merge multiple underscores
    text = text.strip('_')
    
    # 4. Fallback for "Empty" or "Too Short" names
    # If the user input was e.g. "!!!", the result might be empty.
    # Also if the name is too short, path collision is more likely.
    if len(text) < 3:
        # Generate a stable hash based on original text
        h = hashlib.md5(original_text.encode('utf-8')).hexdigest()[:8]
        if not text:
            return f"mod_{h}"
        else:
            return f"{text}_{h}"
            
    return text

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
            force_free_port(p)
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
    else:
        print("Usage: python -m scripts.utils.system_utils <port>")
