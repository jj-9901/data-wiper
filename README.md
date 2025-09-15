# data-wiper

SECUREWIPE-PROTO - Prototype instructions

# ⚠️ WARNING: This tool can DESTROY DATA. Only run inside a disposable VM or against a virtual disk.
1) Environment (Ubuntu recommended)
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip openssl util-linux hdparm nvme-cli secure-delete

2) Create venv and install:
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt    # (optional)

3) Run GUI (recommended):
   sudo python3 main.py --gui

   Or run CLI dry-run (no sudo needed for dry-run):
   python3 main.py --list-devices
   python3 main.py --mode freespace --target /mnt/test-drive --confirm "DELETE" --dry-run

4) Test plan (recommended):
   - Create a new virtual disk in VirtualBox / attach to VM (e.g., 2GB).
   - Partition and mount it.
   - Run the freespace wipe or partition wipe targeting the VM disk.
   - Inspect output and the generated certificate JSON in ./certs/

5) After successful wipe the tool writes a JSON certificate and signs it using openssl.

If you are unsure, DO NOT PROCEED.
