from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Connector:
    connector_id: str
    name: str
    state: str
    transport: str
    evidence: str
    notes: str


def connector_registry() -> dict:
    connectors = [
        Connector("filesystem", "Local / mounted filesystem", "operational", "filesystem", "D0/D1", "Validated reference connector."),
        Connector("removable", "External HDD / SSD", "operational-via-mount", "filesystem", "D0/D1", "Uses Source Passport reconnect evidence."),
        Connector("smb", "SMB / NAS share", "operational-via-mount", "network-filesystem", "D0/D1", "Requires an OS-mounted readable share."),
        Connector("s3", "S3-compatible object storage", "contract-only", "object-api", "D0/D1", "Authentication and production adapter are not included."),
        Connector("gdrive", "Google Drive", "contract-only", "provider-api", "D0/D1", "OAuth adapter is not included."),
        Connector("onedrive", "Microsoft OneDrive", "contract-only", "provider-api", "D0/D1", "OAuth adapter is not included."),
        Connector("dropbox", "Dropbox", "contract-only", "provider-api", "D0/D1", "OAuth adapter is not included."),
    ]
    return {
        "format": "xrecony-connector-registry-v1",
        "sdk_contract": {
            "required_operations": ["probe", "enumerate", "checkpoint", "resume_token", "close"],
            "canonical_output": "XRECONY Canonical Data Object stream",
            "source_mutation_allowed": False,
        },
        "connectors": [asdict(item) for item in connectors],
    }
