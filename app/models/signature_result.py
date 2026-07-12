from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SignatureResult:
    output_path: Path
    field_name: str
    requested_profile: str
    produced_profile: str
    visible: bool
