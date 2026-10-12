import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.document_geometry_service import DocumentGeometryService as Geometry


def test_dense_contours_refine_real_straight_edges_instead_of_approximation_endpoints():
    mask=np.zeros((600,500),np.uint8)
    cv2.rectangle(mask,(50,40),(350,540),255,-1)
    initial=np.array([[54.,43.],[348.,39.],[349.,539.],[51.,541.]])
    sparse,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    dense,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    before,_=Geometry._refine_boundary(sparse[0],initial,(500,600))
    after,_=Geometry._refine_boundary(dense[0],initial,(500,600))
    real=np.array([[50.,40.],[350.,40.],[350.,540.],[50.,540.]])
    assert np.max(np.linalg.norm(before-real,axis=1))>3
    assert np.max(np.linalg.norm(after-real,axis=1))<.05


def adf_capture():
    image=Image.new('RGB',(2550,5100),'#444444')
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,2480,3508),fill='white')
    # Physical backing strips: unchanged source pixels as analysis scale varies.
    for x in (700,1450,2050):draw.rectangle((x,3508,x+59,5099),fill='white')
    return image


@pytest.mark.parametrize('max_edge',[1000,1500,2000])
def test_same_source_backing_strips_are_separated_at_all_analysis_scales(max_edge):
    class Probe(Geometry):MAX_EDGE=max_edge
    image=adf_capture();before=image.tobytes()
    result=Probe.detect(image,dpi=300,measurement_source='DEVICE_GEOMETRY',physical_area_mm=(215.9,431.8))
    assert result.standard_size=='A4'
    assert result.detection_status=='DETECTED',result.boundary_evidence
    assert result.physical_width_mm==pytest.approx(210,abs=1)
    assert result.physical_height_mm==pytest.approx(297,abs=1)
    assert result.pixel_height>3000
    assert image.tobytes()==before


def test_static_pixel_kernel_reproduces_backing_strip_selection_regression():
    class Legacy(Geometry):
        MAX_EDGE=2000
        CONTOUR_SAMPLING='SPARSE'
        @staticmethod
        def _analysis_opening_kernel(size):return 15
    result=Legacy.detect(adf_capture(),dpi=300,measurement_source='DEVICE_GEOMETRY',physical_area_mm=(215.9,431.8))
    assert result.standard_size!='A4'
    assert result.physical_width_mm<100


def test_default_preview_resolution_and_small_image_footprint_are_preserved():
    assert Geometry.MAX_EDGE==1000
    assert Geometry._analysis_opening_kernel((500,1000))==15
    assert Geometry._analysis_opening_kernel((300,600))==15


def test_diagnostic_geometry_does_not_call_format_classifier(tmp_path,monkeypatch):
    from scripts.diagnose_adf_geometry import diagnose_scale
    monkeypatch.setattr(Geometry,'classify',classmethod(lambda cls,*args,**kwargs:pytest.fail('classification during diagnostic')))
    metadata={'scan_metadata':{'physical_area_mm':(215.9,431.8),'effective_dpi':(300,300)}}
    report=diagnose_scale(adf_capture(),metadata,1000,tmp_path/'diagnostic')
    assert report['classification_disabled']
    assert 'standard_size' not in report['geometry']
    assert (tmp_path/'diagnostic'/'11-original-final-overlay.png').is_file()
    assert (tmp_path/'diagnostic'/'refinement.json').is_file()
