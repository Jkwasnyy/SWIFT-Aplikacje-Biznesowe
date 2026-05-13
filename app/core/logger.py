from datetime import datetime

def log(message, level="INFO", uetr=None):
    timestamp = datetime.now().isoformat()

    prefix = f"{timestamp} [{level}]"
    if uetr:
        prefix += f" [UETR={uetr}]"

    with open("logs.txt", "a") as f:
        f.write(f"{prefix} - {message}\n")