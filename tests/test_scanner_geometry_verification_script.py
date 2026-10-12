import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from scripts.verify_scanner_geometry import main
from app.services.scan_service import ScanService


def original_capture(tmp_path):
    source=tmp_path/'original.png'
    image=Image.new('RGB',(230*5,430*5),'#444444')
    ImageDraw.Draw(image).rectangle((0,0,210*5,297*5),fill='white')
    image.save(source)
    metadata=tmp_path/'acquisition.json'
    metadata.write_text(json.dumps({'scan_metadata':{'effective_dpi':[127,127],'physical_area_mm':[230,430]}}))
    return source,metadata


def test_expected_label_is_only_acceptance_and_replay_never_uses_network(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(ScanService,'capabilities',lambda *_:pytest.fail('offline replay must not query scanner'))
    monkeypatch.setattr(ScanService,'scan_page',lambda *_:pytest.fail('offline replay must not scan'))
    source,metadata=original_capture(tmp_path)
    before=source.read_bytes()
    for label in ('A4','LETTER'):
        output=tmp_path/label
        assert main(['--replay-image',str(source),'--metadata',str(metadata),
                     '--output-directory',str(output),'--expected-size',label,'--expected-orientation','PORTRAIT'])==0
        report=json.loads((output/'measurement.json').read_text())
        assert report['geometry']['standard_size']=='A4'
        assert report['homologation']['status']==('PASS' if label=='A4' else 'REVIEW')
        assert report['pdf_media_box_mm']==pytest.approx([210,297],abs=.01)
        assert len(report['source_sha256'])==64
        with Image.open(source) as old, Image.open(output/'source.png') as new:
            assert old.tobytes()==new.tobytes()
    assert source.read_bytes()==before


def test_replay_without_acquisition_metadata_cannot_manufacture_dpi(tmp_path,capsys):
    source,_=original_capture(tmp_path)
    output=tmp_path/'unknown'
    main(['--replay-image',str(source),'--dpi','300','--expected-size','A4','--output-directory',str(output)])
    report=json.loads((output/'measurement.json').read_text())
    assert report['geometry']['measurement_source']=='UNKNOWN'
    assert report['geometry']['physical_width_mm'] is None
    assert report['homologation']['status']=='REVIEW'


def test_homologation_run_never_overwrites_existing_directory(tmp_path):
    output=tmp_path/'preserved';output.mkdir()
    existing=output/'source.png';existing.write_bytes(b'preserve original')
    source,_=original_capture(tmp_path)
    with pytest.raises(FileExistsError):
        main(['--replay-image',str(source),'--output-directory',str(output)])
    assert existing.read_bytes()==b'preserve original'
