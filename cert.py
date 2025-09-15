import json, os, datetime, uuid, subprocess
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

CERT_DIR = "certs"
KEYS_DIR = "keys"
os.makedirs(CERT_DIR, exist_ok=True)
os.makedirs(KEYS_DIR, exist_ok=True)

def ensure_keys():
    priv = os.path.join(KEYS_DIR, "private.pem")
    pub = os.path.join(KEYS_DIR, "public.pem")
    if os.path.exists(priv) and os.path.exists(pub):
        return priv, pub
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", priv, "-pkeyopt", "rsa_keygen_bits:2048"], check=True)
    subprocess.run(["openssl", "-in", priv, "-pubout", "-out", pub], check=True)
    return priv, pub

def make_tamper_checklist(dev: str, kind: str, methods_attempted: list):
    checklist = []
    checklist.append(("HPA/DCO check attempted", "Recommended to run hdparm --dco-restore if HPA present"))
    if kind == "nvme":
        checklist.append(("NVMe secure format attempted", "nvme format -s1"))
    if "hdparm-secure-erase" in methods_attempted:
        checklist.append(("ATA secure erase attempted", "hdparm --security-erase"))
    if "blkdiscard" in methods_attempted or "blkdiscard-fallback" in methods_attempted:
        checklist.append(("TRIM/blkdiscard attempted", "blkdiscard used"))
    checklist.append(("Filesystem unmounted", "Partition/device should be unmounted before block-level wipe"))
    checklist.append(("LUKS/BitLocker detection", "If encrypted, crypto-erase recommended"))
    return checklist

def _render_pdf(cert: dict, pdf_path: str):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, h-60, f"Certificate of Erasure - {cert['certificate_id']}")
    c.setFont("Helvetica", 10)
    y = h-90
    entries = [
        ("Device", cert.get("device")),
        ("Device Type", cert.get("device_kind")),
        ("Model", cert.get("device_model")),
        ("Serial", cert.get("device_serial")),
        ("Method", cert.get("method")),
        ("Passes", str(cert.get("passes"))),
        ("Start", cert.get("start_time")),
        ("End", cert.get("end_time")),
        ("Operator", cert.get("operator")),
        ("Result", cert.get("result"))
    ]
    for k,v in entries:
        c.drawString(40, y, f"{k}: {v}")
        y -= 16
    y -= 8
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Tamper-checklist:")
    y -= 16
    c.setFont("Helvetica", 10)
    for item, note in cert.get("tamper_checklist", []):
        c.drawString(48, y, f"- {item}: {note}")
        y -= 12
        if y < 80:
            c.showPage()
            y = h-60
    c.save()
    return pdf_path

def make_certificate(info: dict, methods_attempted=None):
    priv, pub = ensure_keys()
    cert = {
        "certificate_id": str(uuid.uuid4()),
        "device": info.get("device"),
        "device_kind": info.get("kind"),
        "device_model": info.get("model", ""),
        "device_serial": info.get("serial", ""),
        "method": info.get("method"),
        "methods_attempted": methods_attempted or [info.get("method")],
        "passes": info.get("passes"),
        "start_time": info.get("start_time") or datetime.datetime.utcnow().isoformat() + "Z",
        "end_time": info.get("end_time") or datetime.datetime.utcnow().isoformat() + "Z",
        "operator": info.get("operator", ""),
        "result": info.get("result", ""),
        "tamper_checklist": make_tamper_checklist(info.get("device"), info.get("kind"), methods_attempted or []),
        "notes": info.get("notes","")
    }
    json_path = os.path.join(CERT_DIR, f"{cert['certificate_id']}.json")
    with open(json_path, "w") as f:
        json.dump(cert, f, indent=2)
    sig_path = json_path.replace(".json", ".sig")
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", priv, "-out", sig_path, json_path], check=True)
    pdf_path = json_path.replace(".json", ".pdf")
    _render_pdf(cert, pdf_path)
    return {"json": json_path, "sig": sig_path, "pdf": pdf_path, "pubkey": pub}
