import json, os, datetime, subprocess, uuid

CERT_DIR = "certs"
os.makedirs(CERT_DIR, exist_ok=True)

def make_certificate(info: dict):
    """Save JSON certificate and return path."""
    info["certificate_id"] = str(uuid.uuid4())
    info["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    json_path = os.path.join(CERT_DIR, f"{info['certificate_id']}.json")
    with open(json_path, "w") as f:
        json.dump(info, f, indent=2)
    return json_path

def sign_certificate(json_path, private_key="keys/private.pem"):
    """Sign JSON with openssl using RSA SHA256."""
    sig_path = json_path.replace(".json", ".sig")
    subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", private_key, "-out", sig_path, json_path],
        check=True
    )
    return sig_path
