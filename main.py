import argparse, os, tkinter as tk
from tkinter import ttk, messagebox
from wipe_engine import list_block_devices, wipe_device, wipe_partition, wipe_free_space, get_root_device
from cert import make_certificate, sign_certificate

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SecureWipe Prototype")
        self.geometry("650x450")
        self.create_widgets()

    def create_widgets(self):
        self.mode = tk.StringVar(value="device")
        self.target = tk.StringVar()
        self.sudo_pass = tk.StringVar()
        self.passes = tk.IntVar(value=1)
        self.confirm = tk.StringVar()
        self.dry_run = tk.BooleanVar(value=True)

        ttk.Label(self, text="Select wipe mode:").pack(anchor="w", padx=10, pady=5)
        self.device_radio = ttk.Radiobutton(self, text="Entire Drive", variable=self.mode, value="device")
        self.device_radio.pack(anchor="w", padx=20)
        self.partition_radio = ttk.Radiobutton(self, text="Partition Only", variable=self.mode, value="partition")
        self.partition_radio.pack(anchor="w", padx=20)
        ttk.Radiobutton(self, text="Free Space", variable=self.mode, value="freespace").pack(anchor="w", padx=20)

        ttk.Label(self, text="Target (e.g. /dev/sdb, /dev/sdb1, /mount/point):").pack(anchor="w", padx=10, pady=5)
        ttk.Entry(self, textvariable=self.target, width=50).pack(padx=20)

        ttk.Label(self, text="Passes (HDD only)").pack(anchor="w", padx=10, pady=5)
        ttk.Entry(self, textvariable=self.passes).pack(padx=20)

        ttk.Checkbutton(self, text="Dry-run (no destructive commands)", variable=self.dry_run).pack(anchor="w", padx=20, pady=5)

        ttk.Label(self, text="Type DELETE to confirm:").pack(anchor="w", padx=10, pady=5)
        ttk.Entry(self, textvariable=self.confirm).pack(padx=20)

        ttk.Label(self, text="Sudo password").pack(anchor="w", padx=10, pady=5)
        ttk.Entry(self, textvariable=self.sudo_pass, show="*").pack(padx=20)

        self.warning_label = tk.Label(self, text="", fg="red")
        self.warning_label.pack(pady=5)

        ttk.Button(self, text="Start Wipe", command=self.start_wipe).pack(pady=15)

    def safety_check(self, mode, target):
        root_dev = get_root_device()
        if not root_dev:
            return True, ""

        # Block full wipe on OS device
        if mode == "device" and target in root_dev:
            return False, "Full Wipe blocked: You are running from this device. Use bootable USB instead."

        # Block partition wipe if partition contains root
        if mode == "partition" and target in root_dev:
            return False, "Partition Wipe blocked: This partition contains the OS or the app."

        return True, ""

    def start_wipe(self):
        if self.confirm.get() != "DELETE":
            messagebox.showerror("Error", "You must type DELETE")
            return

        mode, tgt = self.mode.get(), self.target.get()
        ok, msg = self.safety_check(mode, tgt)
        if not ok:
            self.warning_label.config(text=msg)
            return
        self.warning_label.config(text="")

        res = ""
        if mode == "device":
            res = wipe_device(tgt, self.passes.get(), self.sudo_pass.get(), self.dry_run.get())
        elif mode == "partition":
            res = wipe_partition(tgt, self.passes.get(), self.sudo_pass.get(), self.dry_run.get())
        elif mode == "freespace":
            res = wipe_free_space(tgt, self.sudo_pass.get(), self.dry_run.get())

        cert = make_certificate({
            "target": tgt,
            "mode": mode,
            "passes": self.passes.get(),
            "dry_run": self.dry_run.get(),
            "result": res
        })
        sig = sign_certificate(cert)
        messagebox.showinfo("Done", f"Wipe complete.\nCertificate: {cert}\nSignature: {sig}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if args.gui:
        App().mainloop()
    else:
        print("Run with --gui for interactive mode")
