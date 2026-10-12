from dataclasses import replace
from time import perf_counter

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from app.services.document_geometry_service import DocumentGeometryService as Geometry
from app.services.capture_pdf_service import CapturePdfService
from app.models.capture_pdf_workspace import CapturePdfPage


@pytest.mark.parametrize('dimensions,name,orientation',[
    ((210,297),'A4','PORTRAIT'),((297,210),'A4','LANDSCAPE'),
    ((215.9,279.4),'LETTER','PORTRAIT'),((279.4,215.9),'LETTER','LANDSCAPE'),
    ((148,210),'A5','PORTRAIT'),((215.9,355.6),'LEGAL','PORTRAIT'),
    ((80,220),'CUSTOM','PORTRAIT'),((150,150),'CUSTOM','SQUARE_OR_UNDETERMINED'),
    ((209.5,296.4),'A4','PORTRAIT'),((205,290),'CUSTOM','PORTRAIT')])
def test_dimensions(dimensions,name,orientation):
    w,h=dimensions
    result=Geometry.from_corners((w*300/25.4,h*300/25.4),Geometry.FULL,dpi=300,measurement_source='SCANNER_DPI')
    assert result.standard_size==name
    assert result.orientation==orientation
    assert result.physical_width_mm==pytest.approx(w)


@pytest.mark.parametrize('dpi',[None,0,-3,float('nan'),1,20000])
def test_no_fabricated_physical_measurements(dpi):
    result=Geometry.from_corners((2480,3508),Geometry.FULL,dpi=dpi)
    assert result.physical_width_mm is None
    assert result.standard_size=='CUSTOM'
    assert 'mm' not in result.description()


def test_pixel_to_mm():
    result=Geometry.from_corners((2480,3508),Geometry.FULL,dpi=300,measurement_source='SCANNER_DPI')
    assert result.standard_size=='A4'
    assert result.physical_height_mm==pytest.approx(297,abs=.1)


@pytest.mark.parametrize('shape',[(210,297),(297,210),(216,279),(279,216),(148,210),(80,220),(150,150)])
@pytest.mark.parametrize('background,paper',[(20,245),(235,255),(255,210)])
def test_real_sheet_on_background(shape,background,paper):
    w,h=shape
    image=Image.new('RGB',(w+80,h+80),(background,)*3)
    ImageDraw.Draw(image).rectangle((40,40,w+40,h+40),fill=(paper,)*3)
    result=Geometry.detect(image,dpi=25.4,measurement_source='SCANNER_DPI')
    assert result.detection_status=='DETECTED'
    assert result.pixel_width==pytest.approx(w,abs=5)
    assert result.pixel_height==pytest.approx(h,abs=5)
    assert result.confidence>=.8


def test_inclined_and_perspective():
    image=Image.new('RGB',(500,600),'#202020')
    ImageDraw.Draw(image).polygon([(100,60),(400,95),(340,540),(70,500)],fill='white')
    result=Geometry.detect(image)
    assert result.detection_status=='DETECTED'
    assert result.skew_degrees>3
    assert result.perspective_detected
    assert result.normalized_corners[0][0]==pytest.approx(.2,abs=.02)
    transformed=Geometry.transform(image,result)
    assert transformed.height>transformed.width
    assert image.size==(500,600)


@pytest.mark.parametrize('color',['white','black','#cccccc'])
def test_no_sheet(color):
    result=Geometry.detect(Image.new('RGB',(500,600),color))
    assert result.detection_status=='NOT_DETECTED'
    assert result.confidence==0


def test_almost_full_and_cut_warning():
    image=Image.new('RGB',(500,600),'black')
    ImageDraw.Draw(image).rectangle((4,4,495,595),fill='white')
    result=Geometry.detect(image)
    assert result.detection_status=='DETECTED'
    full=Geometry.from_corners(image.size,Geometry.FULL)
    assert full.possible_clipping
    assert not full.reliable_measurement


@pytest.mark.parametrize('corners',[
    ((0,0),(1,1),(1,0),(0,1)),((0,0),(0,1),(1,1),(1,0)),
    ((0,0),(2,0),(1,1),(0,1)),((0,0),(.01,0),(.01,.01),(0,.01))])
def test_invalid_quadrilateral(corners):
    with pytest.raises(ValueError):Geometry.from_corners((500,500),corners)


def test_preview_is_bounded_and_source_preserved():
    image=Image.new('RGB',(2480,3508),'black')
    ImageDraw.Draw(image).rectangle((200,150,2200,3300),fill='white')
    result=Geometry.detect(image,dpi=300,measurement_source='SCANNER_DPI')
    assert max(result.analysis_resolution)<=1000
    assert image.size==(2480,3508)
    assert result.detection_ms>0


def test_pdf_a4_and_detected_media_box(tmp_path):
    image=Image.new('RGB',(400,500),'white')
    geometry=Geometry.from_corners(image.size,((.05,.05),(.95,.05),(.95,.95),(.05,.95)),
                                  physical_area_mm=(240,310),measurement_source='DEVICE_GEOMETRY')
    page=CapturePdfPage(image=image,geometry=geometry)
    output=CapturePdfService.materialize([page],tmp_path/'a4.pdf')
    box=PdfReader(output).pages[0].mediabox
    assert float(box.width)*25.4/72==pytest.approx(210,abs=.01)
    assert float(box.height)*25.4/72==pytest.approx(297,abs=.01)
    page.output_format='DETECTED'
    output=CapturePdfService.materialize([page],tmp_path/'real.pdf')
    box=PdfReader(output).pages[0].mediabox
    assert float(box.width)*25.4/72==pytest.approx(216,abs=.01)
    page.geometry=replace(geometry,measurement_source='ESTIMATED')
    output=CapturePdfService.materialize([page],tmp_path/'fallback.pdf')
    assert float(PdfReader(output).pages[0].mediabox.width)*25.4/72==pytest.approx(210,abs=.01)


def test_adf_backing_strips_do_not_become_a_high_confidence_document():
    image=Image.new('RGB',(500,1000),'#444444')
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,488,712),fill='#fcfcfc')
    for x in (140,245,370):draw.rectangle((x,713,x+9,999),fill='white')
    result=Geometry.detect(image,dpi=300,measurement_source='SCANNER_DPI')
    assert result.pixel_height < 800
    assert result.possible_clipping
    assert result.confidence < .8
    assert result.detection_status=='PARTIAL'
    assert not result.reliable_measurement


def test_perspective_distances_are_estimates_not_reliable_pdf_size():
    result=Geometry.from_corners((500,600),((.2,.1),(.8,.15),(.68,.9),(.14,.83)),
                                dpi=300,measurement_source='SCANNER_DPI')
    assert result.perspective_detected
    assert result.measurement_source=='ESTIMATED'
    assert not result.reliable_measurement
