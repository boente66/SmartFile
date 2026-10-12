"""Local-only scanner check/replay. Expected format is an acceptance criterion,
never an input to the detector. Each run preserves its original in a new folder.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from app.models.scan_config_model import ScanConfigModel
from app.services.scan_service import ScanService
from app.services.capture_pdf_service import CapturePdfService
from app.services.document_geometry_service import DocumentGeometryService


def acceptance(geometry, expected_size=None, expected_orientation=None):
    if expected_size is None and expected_orientation is None:
        return {"status": "NOT_REQUESTED", "checks": {}}
    checks = {
        "detected": geometry.detection_status == "DETECTED",
        "confidence_sufficient": geometry.confidence >= .8,
        "no_cut_evidence": not geometry.possible_clipping,
        "reliable_measurement": geometry.reliable_measurement,
    }
    if expected_size:
        checks["expected_format"] = geometry.standard_size == expected_size
    if expected_orientation:
        checks["expected_orientation"] = geometry.orientation == expected_orientation
    return {"status": "PASS" if all(checks.values()) else "REVIEW", "checks": checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    acquisition = parser.add_mutually_exclusive_group(required=True)
    acquisition.add_argument('--device', help='SANE/TWAIN device identifier; acquires one sheet')
    acquisition.add_argument('--replay-image', type=Path, help='Existing local source image; does not access scanner/network')
    parser.add_argument('--metadata', type=Path, help='Original measurement.json for offline replay')
    parser.add_argument('--dpi', type=int, default=300, help='Requested scanner DPI; does not override replay metrology')
    parser.add_argument('--source', default=None)
    parser.add_argument('--output-directory', type=Path, required=True, help='New directory; existing directories are never overwritten')
    parser.add_argument('--expected-size', choices=tuple(DocumentGeometryService.SIZES))
    parser.add_argument('--expected-orientation', choices=('PORTRAIT', 'LANDSCAPE'))
    args = parser.parse_args(argv)
    if args.metadata and not args.replay_image:
        parser.error('--metadata requires --replay-image')
    directory = args.output_directory
    directory.mkdir(parents=True, exist_ok=False)
    image = page = None
    try:
        if args.replay_image:
            metadata = json.loads(args.metadata.read_text()) if args.metadata else {}
            with Image.open(args.replay_image) as original:
                image = original.convert('RGB')
            # A replay without acquisition metadata remains UNKNOWN: CLI DPI
            # and the expected A4 label cannot manufacture a physical measure.
            image.info.clear()
            image.info.update(metadata.get('scan_metadata', {}))
            capabilities = metadata.get('capabilities', {})
            scan_ms = None
            mode = 'OFFLINE_REPLAY'
        else:
            capabilities = asdict(ScanService.capabilities(args.device))
            config = ScanConfigModel(args.device, dpi=args.dpi, color_mode='color', source_name=args.source)
            start = perf_counter()
            image = ScanService.scan_page(config)
            scan_ms = (perf_counter()-start)*1000
            mode = 'PHYSICAL_CAPTURE'
        page = CapturePdfService.page_from_scan(image)
        geometry = DocumentGeometryService.detect(page.image, dpi=page.scan_dpi,
            measurement_source=page.measurement_source, physical_area_mm=page.physical_area_mm)
        page.geometry = geometry
        image.save(directory/'source.png')
        original_hash = hashlib.sha256((directory/'source.png').read_bytes()).hexdigest()
        start = perf_counter()
        CapturePdfService.materialize([page], directory/'a4.pdf')
        application_ms = (perf_counter()-start)*1000
        from pypdf import PdfReader
        box = PdfReader(directory/'a4.pdf').pages[0].mediabox
        report = {
            'mode': mode, 'capabilities': capabilities, 'image_resolution': image.size,
            'scan_metadata': image.info, 'scan_ms': scan_ms, 'source_sha256': original_hash,
            'geometry': asdict(geometry), 'pdf_application_ms': application_ms,
            'pdf_media_box_mm': [float(box.width)*25.4/72, float(box.height)*25.4/72],
            'expected': {'size': args.expected_size, 'orientation': args.expected_orientation},
            'homologation': acceptance(geometry, args.expected_size, args.expected_orientation),
        }
        # Neither --expected-* value above is passed to DocumentGeometryService.
        text = json.dumps(report, ensure_ascii=False, indent=2, default=float)
        (directory/'measurement.json').write_text(text)
        print(text)
        return 0
    finally:
        if image is not None: image.close()
        if page is not None: CapturePdfService.close_pages([page])


if __name__ == '__main__':
    raise SystemExit(main())
