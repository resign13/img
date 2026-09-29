"""Write web provider credentials to the server's private systemd environment file."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path


PROVIDERS = {
    "WEB_APIYI_KEY": "SECRET_WEB_APIYI_KEY",
    "WEB_MEINIANDA_KEY": "SECRET_WEB_MEINIANDA_KEY",
    "WEB_G_AISC_KEY": "SECRET_WEB_G_AISC_KEY",
}
LEGACY_KEYS = {"LLM_KEY", "IMG_KEY", "IMG_KEY_LINE2", "APIYI_GPT_IMAGE_KEY"}
LEGACY_CONFIG_FIELDS = {"llm_key", "img_key", "img_key_primary", "img_key_line2", "api_keys"}
ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def write_provider_env(destination: Path, environment=None):
    environment = os.environ if environment is None else environment
    values = {name: (environment.get(source) or "").strip() for name, source in PROVIDERS.items()}
    if any(not value for value in values.values()):
        raise ValueError("All three web provider secrets must be configured before deployment.")
    if any("\n" in value or "\r" in value for value in values.values()):
        raise ValueError("Provider secrets cannot contain line breaks.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    existing = destination.read_text(encoding="utf-8") if destination.exists() else ""
    removed = set(values) | LEGACY_KEYS
    preserved = [
        line for line in existing.splitlines()
        if not ((match := ENV_LINE.match(line)) and match.group(1) in removed)
    ]
    new_content = "\n".join([*preserved, *(f"{name}={value}" for name, value in values.items())]) + "\n"

    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".env_", dir=destination.parent)
        os.chmod(temporary, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(new_content)
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)

    legacy_config = destination.parent / "desktop_app" / "data" / "config.json"
    if legacy_config.exists():
        payload = json.loads(legacy_config.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict) and LEGACY_CONFIG_FIELDS.intersection(payload):
            for field in LEGACY_CONFIG_FIELDS:
                payload.pop(field, None)
            temporary = None
            try:
                fd, temporary = tempfile.mkstemp(prefix=".config_", dir=legacy_config.parent)
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                os.replace(temporary, legacy_config)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)


if __name__ == "__main__":
    write_provider_env(Path(sys.argv[1]))
