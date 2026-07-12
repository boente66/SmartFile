from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HandwrittenSignatureResult:
    output_path: Path
    page_number: int
    had_digital_signatures: bool
    signer_name: str | None
