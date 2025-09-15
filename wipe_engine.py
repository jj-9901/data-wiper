import subprocess
import json

def run_cmd(cmd, sudo_pass=None):
    """Run system command with optional sudo password."""
    if sudo_pass:
        cmd = ["sudo", "-S"] + cmd
        proc = subprocess.run(
            cmd, input=(sudo_pass + "\n").encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    else:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()

def list_block_devices():
    """Return block devices via lsblk JSON."""
    code, out, err = run_cmd(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,SERIAL"])
    if code != 0:
        raise RuntimeError(f"lsblk failed: {err}")
    return json.loads(out)

def get_root_device():
    """Detect which device the current OS is running from."""
    code, out, err = run_cmd(["findmnt", "-n", "-o", "SOURCE", "/"])
    if code != 0:
        return None
    return out.strip()

def wipe_device(dev, passes=1, sudo_pass=None, dry_run=False):
    """Wipe entire device."""
    if dry_run:
        return f"[DRY-RUN] would wipe {dev} with {passes} pass(es)"
    code, out, err = run_cmd(["blkdiscard", dev], sudo_pass)
    if code == 0:
        return f"blkdiscard successful on {dev}"
    for i in range(passes):
        code, out, err = run_cmd(["dd", "if=/dev/zero", f"of={dev}", "bs=1M"], sudo_pass)
        if code != 0:
            return f"dd failed: {err}"
    return f"{passes}-pass overwrite done on {dev}"

def wipe_partition(partition, passes=1, sudo_pass=None, dry_run=False):
    """Wipe partition only."""
    return wipe_device(partition, passes, sudo_pass, dry_run)

def wipe_free_space(mountpoint, sudo_pass=None, dry_run=False):
    """Overwrite free space using sfill."""
    if dry_run:
        return f"[DRY-RUN] would wipe free space on {mountpoint}"
    code, out, err = run_cmd(["sfill", "-v", mountpoint], sudo_pass)
    if code != 0:
        return f"sfill failed: {err}"
    return f"Free space wiped on {mountpoint}"
