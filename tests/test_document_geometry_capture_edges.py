"""Regression: acquisition-frame contact is not by itself evidence of a cut."""
import pytest
from PIL import Image, ImageDraw

from app.services.document_geometry_service import DocumentGeometryService as Geometry


DPI = 127  # Five source pixels per millimetre; detection still downsamples.
AREA = (230., 430.)


def capture(width, height, offset=(0., 0.), strips=False, area=AREA):
    image = Image.new('RGB', tuple(round(mm * 5) for mm in area), '#444444')
    draw = ImageDraw.Draw(image)
    x, y = offset
    draw.rectangle((round(x*5), round(y*5), round((x+width)*5), round((y+height)*5)), fill='#fcfcfc')
    if strips:
        for column in (60, 120, 170):
            draw.rectangle((round(column*5), round((y+height)*5), round(column*5)+8, image.height-1), fill='white')
    return image


def detect(image, **kwargs):
    return Geometry.detect(image, dpi=DPI, measurement_source='DEVICE_GEOMETRY',
                           physical_area_mm=AREA, **kwargs)


@pytest.mark.parametrize('offset', [(8., 0.), (0., 20.), (0., 0.)],
                         ids=['upper-limit', 'lateral-limit', 'two-coincident-edges'])
@pytest.mark.parametrize('dimensions,standard', [((210.,297.),'A4'), ((215.9,279.4),'LETTER')])
def test_standard_sheet_coincident_with_capture(dimensions, standard, offset):
    image = capture(*dimensions, offset=offset)
    original = image.tobytes()
    result = detect(image)
    assert result.detection_status == 'DETECTED', result.boundary_evidence
    assert result.boundary_status == 'COINCIDENT'
    assert not result.possible_clipping
    assert result.confidence >= .8
    assert result.standard_size == standard
    assert result.orientation == 'PORTRAIT'
    assert result.physical_width_mm == pytest.approx(dimensions[0], abs=1.)
    assert result.physical_height_mm == pytest.approx(dimensions[1], abs=1.)
    assert result.reliable_measurement
    assert image.tobytes() == original


def test_adf_strips_are_excluded_from_coincident_a4():
    image = capture(210.,297., strips=True)
    result = detect(image)
    assert result.standard_size == 'A4'
    assert result.detection_status == 'DETECTED'
    assert result.physical_height_mm == pytest.approx(297, abs=1.)
    assert result.pixel_height < image.height * .72


@pytest.mark.parametrize('dimensions', [(205.,290.),(209.3,303.6),(220.,310.),(215.,420.)])
def test_nearly_acquisition_size_does_not_force_a4(dimensions):
    result = detect(capture(*dimensions))
    assert result.standard_size == 'CUSTOM'
    assert result.detection_status == 'PARTIAL'
    assert result.possible_clipping
    assert result.confidence <= .55


def test_receipt_keeps_custom_portrait_and_does_not_use_scanner_format():
    result = detect(capture(80.,220.,offset=(30.,30.),strips=True))
    assert result.standard_size == 'CUSTOM'
    assert result.detection_status == 'DETECTED'
    assert result.orientation == 'PORTRAIT'
    assert result.physical_width_mm == pytest.approx(80, abs=1.)
    assert result.physical_height_mm == pytest.approx(220, abs=1.)


def test_actual_cut_does_not_become_coincident_even_near_standard_dimensions():
    image = Image.new('RGB',(1150,2150),'#444444')
    # Sloping physical top crosses the acquisition boundary. A visible segment
    # provides evidence of missing paper, unlike a whole edge aligned to frame.
    ImageDraw.Draw(image).polygon([(0,-40),(1050,35),(1030,1520),(-20,1480)],fill='white')
    result = detect(image)
    assert result.detection_status == 'PARTIAL'
    assert result.possible_clipping
    assert not result.reliable_measurement
    assert ('visible_edge_extrapolates_outside_capture' in result.boundary_evidence
            or 'truncated_or_sloping_corner' in result.boundary_evidence)


def test_a4_continues_beyond_capture_height():
    image = capture(210.,297.,area=(230.,280.))
    result = Geometry.detect(image,dpi=DPI,measurement_source='SCANNER_DPI')
    assert result.detection_status == 'PARTIAL'
    assert result.possible_clipping
    assert result.standard_size != 'A4'


@pytest.mark.parametrize('source,dpi', [('UNKNOWN',None),('ESTIMATED',127)])
def test_frame_contact_without_trusted_metrology_remains_partial(source,dpi):
    result = Geometry.detect(capture(210.,297.),dpi=dpi,measurement_source=source)
    assert result.detection_status == 'PARTIAL'
    assert not result.reliable_measurement


def test_conflicting_dpi_and_physical_area_do_not_raise_confidence():
    result = Geometry.detect(capture(210.,297.),dpi=150,measurement_source='DEVICE_GEOMETRY',physical_area_mm=AREA)
    assert result.detection_status == 'PARTIAL'
    assert 'dpi_and_acquisition_geometry_disagree' in result.boundary_evidence


def test_landscape_contact_preserves_orientation_and_size():
    area=(330.,400.)
    result=Geometry.detect(capture(297.,210.,offset=(0.,0.),area=area),dpi=DPI,
                           measurement_source='DEVICE_GEOMETRY',physical_area_mm=area)
    assert result.standard_size=='A4'
    assert result.orientation=='LANDSCAPE'
    assert result.detection_status=='DETECTED'


def test_contact_never_boosts_detection_confidence():
    interior=detect(capture(210.,297.,offset=(8.,20.)))
    contact=detect(capture(210.,297.))
    assert contact.detection_status=='DETECTED'
    assert contact.confidence <= interior.confidence + .02


def test_letter_touching_both_lateral_limits_has_two_visible_horizontal_edges():
    area=(215.9,430.)
    result=Geometry.detect(capture(215.9,279.4,offset=(0.,20.),area=area),dpi=DPI,
                           measurement_source='DEVICE_GEOMETRY',physical_area_mm=area)
    assert result.standard_size=='LETTER'
    assert result.detection_status=='DETECTED'
    assert not result.possible_clipping


def test_two_edge_custom_receipt_is_not_promoted_to_a_standard_format():
    result=detect(capture(80.,220.))
    assert result.standard_size=='CUSTOM'
    assert result.detection_status=='PARTIAL'
    assert result.possible_clipping
