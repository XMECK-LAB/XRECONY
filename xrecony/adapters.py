from __future__ import annotations

import platform
from pathlib import Path


def native_binary() -> Path:
    name = "xrecony-native.exe" if platform.system() == "Windows" else "xrecony-native"
    return Path(__file__).resolve().parents[1] / "native" / "bin" / name


def adapter_status() -> dict:
    binary = native_binary()
    available = binary.is_file()
    return {
        "selected": "rust-native-jsonl-v3" if available else "python-optimized-scandir-v3",
        "native": {
            "available": available,
            "binary": str(binary),
            "contract": "read-only JSONL metadata enumeration helper",
            "verified_in_this_package": False,
        },
        "fallback": {
            "available": True,
            "adapter": "python-optimized-scandir-v3",
            "contract": "read-only portable metadata enumeration",
        },
        "claim_effect": "Native speed claims remain locked until the compiled helper is integrated and independently benchmarked.",
    }
