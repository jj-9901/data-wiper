import subprocess, json, os, time, re, shlex, signal
from typing import Dict, Optional

def run_cmd(cmd, sudo_pass=None, capture_output=True, check=False, shell=False):
    """Run system command. If sudo_pass provided, prefix sudo -S."""
    if sudo_pass:
        if isinstance(cmd, str) and not shell:
            cmd = shlex.split(cmd)
        full = ["sudo", "-S"] + (cmd if isinstance(cmd, list) else [cmd])
        p = subprocess.Popen(full, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
        out, err = p.communicate(input=(sudo_pass + "\n").encode())
        rc = p.returncode
        out = out.decode(errors="ignore")
        err = err.decode(errors="ignore")
    else:
        if isinstance(cmd, str) and not shell:
            cmd = shlex.split(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
        out, err = p.communicate()
        rc = p.returncode
        out = out.decode(errors="ignore")
        err = err.decode(errors="ignore")
    if check and rc != 0:
        raise RuntimeError(f"Command failed: {cmd}\nRC={rc}\nOUT={out}\nERR={err}")
    return rc, out, err

def list_block_devices() -> Dict:
    rc, out, err = run_cmd(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,SERIAL,ROTA,RO"])
    if rc != 0:
        raise RuntimeError("lsblk failed: " + err)
    return json.loads(out)

def _basename(dev_path: str) -> str:
    return os.path.basename(dev_path)

def detect_device_type(dev: str, sudo_pass: Optional[str]=None) -> Dict:
    short = _basename(dev)
    info = {"kind": "unknown", "model": "", "serial": "", "rotational": None}

    # rotational info
    try:
        with open(f"/sys/block/{short}/queue/rotational", "r") as f:
            val = f.read().strip()
            info["rotational"] = (val == "1")
    except Exception:
        info["rotational"] = None

    # NVMe
    if short.startswith("nvme"):
        info["kind"] = "nvme"
    else:
        rc, out, err = run_cmd(["udevadm", "info", "--query=property", "--name", dev])
        if "ID_ATA_FEATURE_SET_SECURE_ERASE" in out or "ID_MODEL=" in out:
            if info["rotational"] is False:
                info["kind"] = "sata_ssd"
            elif info["rotational"] is True:
                info["kind"] = "hdd"
            else:
                info["kind"] = "sata_ssd" if "SSD" in out.upper() else "hdd"
        else:
            try:
                j = list_block_devices()
                for d in j.get("blockdevices", []):
                    if d["name"] == short:
                        info["model"] = d.get("model") or ""
                        info["serial"] = d.get("serial") or ""
                        if "rota" in d:
                            info["rotational"] = (str(d["rota"]) == "1")
                            info["kind"] = "hdd" if info["rotational"] else "sata_ssd"
                        break
            except Exception:
                pass

    try:
        rc, out, err = run_cmd(["hdparm", "-I", dev], sudo_pass)
        if rc == 0:
            m = re.search(r"Model Number:\s*(.+)", out)
            s = re.search(r"Serial Number:\s*(.+)", out)
            if m: info["model"] = m.group(1).strip()
            if s: info["serial"] = s.group(1).strip()
    except Exception:
        pass
    return info

# --- Wipe implementations ---

class WipeProcess:
    """Manage a wipe subprocess so UI can pause/resume."""
    def __init__(self, cmd, sudo_pass=None, shell=False):
        self.cmd = cmd if isinstance(cmd, list) else (shlex.split(cmd) if not shell else cmd)
        self.sudo_pass = sudo_pass
        self.shell = shell
        self.proc = None

    def start(self):
        if self.sudo_pass:
            full = ["sudo", "-S"] + (self.cmd if isinstance(self.cmd, list) else [self.cmd])
            self.proc = subprocess.Popen(full, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=self.shell, bufsize=1)
            try:
                self.proc.stdin.write((self.sudo_pass + "\n").encode()); self.proc.stdin.flush()
            except Exception:
                pass
        else:
            self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=self.shell, bufsize=1)

    def read_stdout_lines(self):
        if self.proc is None or self.proc.stdout is None:
            return
        for line in iter(self.proc.stdout.readline, b''):
            yield line.decode(errors="ignore")

    def pause(self):
        if self.proc:
            self.proc.send_signal(signal.SIGSTOP)

    def resume(self):
        if self.proc:
            self.proc.send_signal(signal.SIGCONT)

    def terminate(self):
        if self.proc:
            self.proc.terminate()

    def wait(self):
        if self.proc:
            return self.proc.wait()
        return None

def supports_blkdiscard(dev, sudo_pass=None):
    short = _basename(dev)
    try:
        with open(f"/sys/block/{short}/queue/discard_granularity", "r") as f:
            val = f.read().strip()
            return val != "" and int(val) >= 0
    except Exception:
        return False

def wipe_device(dev, passes=1, sudo_pass=None, dry_run=False, progress_callback=None):
    info = detect_device_type(dev, sudo_pass)
    kind = info.get("kind", "unknown")
    result = {"device": dev, "kind": kind, "method": None, "passes": passes, "start": time.time(), "stdout": []}

    if dry_run:
        result["stdout"].append(f"[DRY-RUN] would wipe {dev} kind={kind} passes={passes}")
        return result

    if kind == "nvme":
        result["method"] = "nvme-format-secure"
        cmd = ["nvme", "format", "-s1", dev]
        rc, out, err = run_cmd(cmd, sudo_pass)
        result["stdout"].append(out+err)
        result["rc"] = rc
        return result

    if kind == "sata_ssd":
        result["method"] = "hdparm-secure-erase"
        passwd = "securewipeprot"
        try:
            rc, out, err = run_cmd(["hdparm", "--user-master", "u", "--security-set-pass", passwd, dev], sudo_pass)
            result["stdout"].append(out+err)
            if rc != 0 and supports_blkdiscard(dev, sudo_pass):
                rc, out, err = run_cmd(["blkdiscard", dev], sudo_pass)
                result["stdout"].append(out+err)
                result["method"] = "blkdiscard-fallback"
            result["rc"] = rc
            return result
        except Exception as e:
            result["stdout"].append(str(e))
            result["rc"] = 1
            return result

    if kind in ("hdd","unknown"):
        result["method"] = "dd-multi-pass"
        for p in range(passes):
            cmd = ["dd", "if=/dev/zero", f"of={dev}", "bs=4M", "status=progress", "oflag=direct"]
            wp = WipeProcess(cmd, sudo_pass)
            wp.start()
            for line in wp.read_stdout_lines():
                result["stdout"].append(line)
                if progress_callback:
                    progress_callback(line)
            rc = wp.wait()
            result["rc"] = rc
            if rc != 0:
                break
        return result

def wipe_partition(partition, passes=1, sudo_pass=None, dry_run=False, progress_callback=None):
    return wipe_device(partition, passes, sudo_pass, dry_run, progress_callback)

def wipe_free_space(mountpoint, sudo_pass=None, dry_run=False, progress_callback=None):
    if dry_run:
        return {"method": "sfill", "target": mountpoint, "dry_run": True}
    rc, out, err = run_cmd(["sfill", "-v", mountpoint], sudo_pass)
    return {"method": "sfill", "target": mountpoint, "rc": rc, "stdout": out+err}
