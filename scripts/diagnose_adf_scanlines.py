"""Independent original-resolution ADF scanline and controlled sampling experiments. Local only."""
import argparse,json,sys
from pathlib import Path
import numpy as np,cv2
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.diagnose_adf_geometry import GeometryOnly,draw_overlay,write_json
from app.services.document_geometry_service import DocumentGeometryService as G
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--capture',nargs=2,action='append',required=True,metavar=('IMAGE','METADATA'))
parser.add_argument('--output-root',type=Path,required=True,help='Existing diagnostic root with capture-N/edge-* subdirectories')
args=parser.parse_args()
root=args.output_root
all_reports=[]
for cap,(image_path,metadata_path) in enumerate(args.capture,1):
 with Image.open(image_path) as src:rgb=src.convert('RGB');full=np.asarray(rgb.convert('L'))
 meta=json.loads(Path(metadata_path).read_text());area=np.array(meta['scan_metadata']['physical_area_mm']);sy,sx=full.shape
 Image.fromarray(full).save(root/f'capture-{cap}'/'source-resolution-grayscale.png')
 records=[]
 # Source-resolution 1D leading/trailing and lateral edge probes, multiple thresholds.
 for threshold in (80,128,180,200,230,250):
  vertical=[];horizontal=[]
  for x in np.linspace(sx*.06,sx*.94,17).astype(int):
   line=np.median(full[:,x-6:x+7],axis=1).astype(np.uint8)
   line=cv2.medianBlur(line.reshape(-1,1),9).ravel();bright=line>threshold
   changes=np.diff(np.r_[False,bright,False].astype(int));starts=np.flatnonzero(changes==1);ends=np.flatnonzero(changes==-1)
   runs=[(a,b-1) for a,b in zip(starts,ends) if b-a>sy*.08]
   if runs:
    a,b=max(runs,key=lambda p:p[1]-p[0]);vertical.append({'x_mm':x*area[0]/sx,'leading_mm':a*area[1]/sy,'trailing_mm':b*area[1]/sy,'leading_px':int(a),'trailing_px':int(b)})
  for y in np.linspace(sy*.07,sy*.64,17).astype(int):
   line=np.median(full[y-6:y+7,:],axis=0).astype(np.uint8)
   bright=cv2.medianBlur(line.reshape(-1,1),9).ravel()>threshold
   changes=np.diff(np.r_[False,bright,False].astype(int));starts=np.flatnonzero(changes==1);ends=np.flatnonzero(changes==-1)
   runs=[(a,b-1) for a,b in zip(starts,ends) if b-a>sx*.3]
   if runs:
    a,b=max(runs,key=lambda p:p[1]-p[0]);horizontal.append({'y_mm':y*area[1]/sy,'left_mm':a*area[0]/sx,'right_mm':b*area[0]/sx,'width_mm':(b-a)*area[0]/sx})
  leading=[p['leading_mm'] for p in vertical];trailing=[p['trailing_mm'] for p in vertical]
  right=[p['right_mm'] for p in horizontal]
  visible=[p for p in vertical if p['leading_px']>2]
  top_fit=np.polyfit([p['x_mm'] for p in visible],[p['leading_mm'] for p in visible],1).tolist() if len(visible)>4 else None
  tail_fit=np.polyfit([p['x_mm'] for p in vertical],[p['trailing_mm'] for p in vertical],1).tolist() if len(vertical)>4 else None
  records.append({'threshold':threshold,'vertical_probes':vertical,'horizontal_probes':horizontal,
    'median_trailing_mm':float(np.median(trailing)) if trailing else None,
    'leading_extrapolated_y_at_x0_mm':top_fit[1] if top_fit else None,
    'leading_angle_degrees':float(np.degrees(np.arctan(top_fit[0]))) if top_fit else None,
    'trailing_angle_degrees':float(np.degrees(np.arctan(tail_fit[0]))) if tail_fit else None,
    'right_edge_range_mm': [min(right),max(right)] if right else None})
 saturation=[]
 for fraction in (.06,.34,.66,.94):
  x=round(sx*fraction);strip=full[:,max(0,x-6):min(sx,x+7)]
  bright=np.flatnonzero(np.median(strip,axis=1)>200)
  bright=bright[bright<sy*.8]
  if not len(bright):continue
  tail=int(bright[-1]);flat=strip.min(axis=1)>=254
  starts=[y for y in range(max(0,tail-250),tail+1) if flat[y:y+25].mean()>.95]
  saturation.append({'x_mm':x*area[0]/sx,'trailing_mm':tail*area[1]/sy,
                     'saturated_segment_start_mm':starts[0]*area[1]/sy if starts else None,
                     'interpretation':'photometric transition only; not a proven physical paper boundary'})
 write_json(root/f'capture-{cap}'/'saturation-probes.json',saturation)
 write_json(root/f'capture-{cap}'/'full-resolution-scanlines.json',records)
 print('CAPTURE',cap,'source scanlines:',[(p['threshold'],round(p['median_trailing_mm'],3) if p['median_trailing_mm'] else None,round(p['leading_extrapolated_y_at_x0_mm'],3) if p['leading_extrapolated_y_at_x0_mm'] else None,round(p['leading_angle_degrees'],3) if p['leading_angle_degrees'] else None,round(p['trailing_angle_degrees'],3) if p['trailing_angle_degrees'] else None) for p in records],flush=True)
 experiments=[]
 for edge in (1000,1500,2000):
  preview=rgb.copy();preview.thumbnail((edge,edge));gray=cv2.GaussianBlur(np.asarray(preview.convert('L')),(5,5),0)
  _,mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
  k=round(15*edge/1000);k=k if k%2 else k+1
  opened=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((k,k),np.uint8))
  Image.fromarray(opened).save(root/f'capture-{cap}'/f'edge-{edge}'/'experimental-scale-invariant-opening.png')
  for name,method in (('SPARSE',cv2.CHAIN_APPROX_SIMPLE),('DENSE',cv2.CHAIN_APPROX_NONE)):
   contours,_=cv2.findContours(opened,cv2.RETR_LIST,method)
   contour=max(contours,key=cv2.contourArea);polygon=cv2.approxPolyDP(contour,.02*cv2.arcLength(contour,True),True)
   item={'scale':edge,'kernel':k,'sampling':name,'contour_points':len(contour),'vertices':len(polygon),'relative_area':cv2.contourArea(contour)/(preview.width*preview.height)}
   if len(polygon)==4:
    points=polygon[:,0,:].astype(float);center=points.mean(axis=0);points=points[np.argsort(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))];points=np.roll(points,-np.argmin(points.sum(axis=1)),axis=0)
    final,outside=G._refine_boundary(contour,points,preview.size)
    measurement=GeometryOnly.from_corners(rgb.size,final/np.array(preview.size),dpi=meta['scan_metadata']['effective_dpi'],measurement_source='DEVICE_GEOMETRY',physical_area_mm=area.tolist())
    item.update(width_mm=measurement.physical_width_mm,height_mm=measurement.physical_height_mm,skew=measurement.skew_degrees,outside=outside,corners=final.tolist())
    draw_overlay(preview,final,title=f'EXPERIMENT ONLY: scaled opening {k}, {name} contour').save(root/f'capture-{cap}'/f'edge-{edge}'/f'experimental-{name.lower()}-overlay.png')
   experiments.append(item)
  preview.close()
 print('CAPTURE',cap,'controlled experiments:',[(p['scale'],p['sampling'],p['vertices'],p.get('width_mm'),p.get('height_mm')) for p in experiments],flush=True)
 write_json(root/f'capture-{cap}'/'controlled-experiments.json',experiments)
 all_reports.append({'capture':cap,'full_resolution':records,'experiments':experiments})
 rgb.close()
write_json(root/'additional-comparison.json',all_reports)
