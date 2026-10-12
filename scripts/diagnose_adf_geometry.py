"""Offline instrumentation of the unchanged detector. Never acquires or uploads.

All images remain in a new local output directory. Classification is disabled;
A4 is only a post-measurement reference in the report, never a geometry input.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import html
import json
from math import atan2, degrees, hypot
from pathlib import Path
import shutil
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from PIL import Image, ImageDraw
from app.services.document_geometry_service import DocumentGeometryService

SIDES = ('TOP', 'RIGHT', 'BOTTOM', 'LEFT')
COLORS = ('#e63946', '#2a9d8f', '#0057b8', '#d98c00')


class GeometryOnly(DocumentGeometryService):
    @classmethod
    def classify(cls, *args, **kwargs):
        return 'DIAGNOSTIC_UNCLASSIFIED'


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False,
        default=lambda v: v.tolist() if hasattr(v, 'tolist') else float(v)))


def draw_overlay(image, points=None, contours=(), title='', lines=(), marked=()):
    result = image.convert('RGB').copy()
    draw = ImageDraw.Draw(result)
    for number, contour in contours:
        xy = contour[:, 0, :].astype(float)
        draw.line(list(map(tuple,xy))+[tuple(xy[0])],fill=COLORS[(number-1)%4],width=2)
        draw.text(tuple(xy[0]),str(number),fill='red',stroke_width=1,stroke_fill='white')
    for origin,direction in lines:
        origin,direction = np.array(origin),np.array(direction)
        length = max(image.size)*2
        draw.line([tuple(origin-direction*length),tuple(origin+direction*length)],fill='#00aaff',width=2)
    for point,kind in marked:
        x,y=point; color='#ff00ff' if kind=='discarded' else '#ff5500'
        draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
    if points is not None:
        for index in range(4):
            a,b=points[index],points[(index+1)%4]
            draw.line([tuple(a),tuple(b)],fill=COLORS[index],width=max(2,round(max(image.size)/500)))
            x,y=a
            draw.ellipse((x-5,y-5,x+5,y+5),outline='white',width=2)
            draw.text((x+7,y+7),str(index+1),fill=COLORS[index],stroke_width=1,stroke_fill='white')
    if title:
        draw.rectangle((0,0,min(result.width,600),17),fill='white')
        draw.text((3,3),title,fill='black')
    return result


def refinement_trace(contour, points, size):
    """Replicate existing line fit, exposing samples/intersections/fallback.
    Numeric agreement with the production function is asserted by the caller.
    """
    samples=contour[:,0,:].astype(float)
    width,height=size;lines=[];sides=[]
    for index in range(4):
        start,end=points[index],points[(index+1)%4]
        delta=end-start;length=np.linalg.norm(delta);direction=delta/length
        projection=(samples-start)@direction
        distance=np.abs((samples[:,0]-start[0])*direction[1]-(samples[:,1]-start[1])*direction[0])
        near=(projection>length*.08)&(projection<length*.92)&(distance<max(3.,length*.025))
        selected=samples[near]
        on_frame=(abs(start[0]-end[0])<2 and (max(start[0],end[0])<2 or min(start[0],end[0])>width-3)
                  or abs(start[1]-end[1])<2 and (max(start[1],end[1])<2 or min(start[1],end[1])>height-3))
        discarded=np.empty((0,2))
        if not on_frame and len(selected):
            interior=(selected[:,0]>1)&(selected[:,0]<width-2)&(selected[:,1]>1)&(selected[:,1]<height-2)
            discarded=selected[~interior];selected=selected[interior]
        fitted=len(selected)>=4 and np.ptp(selected@direction)>length*.35
        if fitted:
            vx,vy,x,y=cv2.fitLine(selected.astype(np.float32),cv2.DIST_HUBER,0,.01,.01).ravel()
            line=(np.array([float(x),float(y)]),np.array([float(vx),float(vy)]))
        else:line=(start,direction)
        lines.append(line)
        sides.append({'side':SIDES[index],'initial_edge': [start,end], 'on_frame':bool(on_frame),
                      'fit_used':bool(fitted),'selected_points':selected,
                      'discarded_frame_points':discarded,'discarded_non_edge_points':samples[~near],
                      'fitted_origin':line[0],'fitted_direction':line[1],
                      'fit_reason':'huber_fit' if fitted else 'insufficient_samples_or_span_use_polygon_edge'})
    intersections=[];reason=None
    for index in range(4):
        a,u=lines[(index-1)%4];b,v=lines[index];matrix=np.column_stack((u,-v))
        if abs(np.linalg.det(matrix))<.1:
            reason='near_parallel_lines_fallback_to_polygon';break
        point=a+np.linalg.solve(matrix,b-a)[0]*u;intersections.append(point)
        if np.linalg.norm(point-points[index])>max(size)*.04:
            reason='intersection_moves_over_4_percent_fallback_to_polygon';break
    if reason:returned=points;outside=False
    else:
        raw=np.array(intersections)
        outside=bool(((raw[:,0]<-2)|(raw[:,1]<-2)|(raw[:,0]>width+1)|(raw[:,1]>height+1)).any())
        returned=np.clip(raw,[0.,0.],[width-1.,height-1.])
    return {'sides':sides,'intersections_before_clamp':intersections,
            'returned_points':returned,'extrapolates':outside,'fallback_reason':reason},lines


def edge_metrics(gray, initial, final, trace, image_size, area):
    h,w=gray.shape;scale=np.array(image_size)/np.array([w,h]);mm_per_preview=np.array(area)/np.array([w,h])
    rows=[];center=final.mean(axis=0)
    for index in range(4):
        a,b=final[index],final[(index+1)%4];delta=b-a
        normal=np.array([-delta[1],delta[0]])/np.linalg.norm(delta)
        if np.dot(normal,center-(a+b)/2)<0:normal=-normal
        contrast=[]
        for f in np.linspace(.12,.88,21):
            point=a+delta*f;inside,outside=point+normal*3,point-normal*3
            if all(1<=p[0]<w-1 and 1<=p[1]<h-1 for p in (inside,outside)):
                medians=[]
                for p in (inside,outside):
                    x,y=np.rint(p).astype(int);medians.append(float(np.median(gray[y-1:y+2,x-1:x+2])))
                contrast.append(medians[0]-medians[1])
        raw=trace['intersections_before_clamp']
        raw_a=np.array(raw[index]) if len(raw)==4 else a
        raw_b=np.array(raw[(index+1)%4]) if len(raw)==4 else b
        ok,start,end=cv2.clipLine((0,0,w,h),tuple(np.rint(raw_a).astype(int)),tuple(np.rint(raw_b).astype(int)))
        axis_angle=degrees(atan2(delta[1],delta[0]));ideal=(0,90,180,-90)[index]
        deviation=(axis_angle-ideal+180)%360-180
        near_border={'TOP':float(min(a[1],b[1])), 'RIGHT':float(w-1-max(a[0],b[0])),
                     'BOTTOM':float(h-1-max(a[1],b[1])), 'LEFT':float(min(a[0],b[0]))}[SIDES[index]]
        rows.append({'side':SIDES[index],'initial_preview_endpoints':[initial[index],initial[(index+1)%4]],
            'final_preview_endpoints':[a,b],'final_original_endpoints':[a*scale,b*scale],
            'final_physical_endpoints_mm':[a*mm_per_preview,b*mm_per_preview],
            'edge_length_source_px':float(np.linalg.norm(delta*scale)),
            'edge_length_mm':float(np.linalg.norm(delta*mm_per_preview)),
            'visible_length_preview_px':hypot(end[0]-start[0],end[1]-start[1]) if ok else 0.,
            'valid_contrast_samples':len(contrast),'mean_signed_contrast':float(np.mean(contrast)) if contrast else None,
            'mean_absolute_contrast':float(np.mean(np.abs(contrast))) if contrast else None,
            'contrast_support':DocumentGeometryService._visible_edge_support(gray,final,index),
            'axis_deviation_degrees':deviation,'distance_to_corresponding_frame_px':near_border,
            'distance_to_corresponding_frame_mm':near_border*mm_per_preview[1 if index in (0,2) else 0],
            'raw_intersection_endpoints':[raw_a,raw_b],
            'raw_extrapolation':bool((raw_a<0).any() or (raw_b<0).any() or raw_a[0]>w-1 or raw_b[0]>w-1 or raw_a[1]>h-1 or raw_b[1]>h-1),
            'line_fit_used':trace['sides'][index]['fit_used'],
            'line_samples_kept':len(trace['sides'][index]['selected_points']),
            'frame_samples_discarded':len(trace['sides'][index]['discarded_frame_points'])})
    return rows


def profile_artifacts(gray, area, output):
    """Independent 1D measurements, with no expected-size input."""
    h,w=gray.shape
    row=np.median(gray,axis=1);col=np.median(gray,axis=0)
    row_mean=gray.mean(axis=1);col_mean=gray.mean(axis=0)
    bright_rows=(gray>200).mean(axis=1);bright_cols=(gray>200).mean(axis=0)
    np.savetxt(output/'row-projection.csv',np.column_stack((np.arange(h),np.arange(h)*area[1]/h,row,row_mean,bright_rows)),delimiter=',',header='preview_y,y_mm,median_luminance,mean_luminance,bright_fraction',comments='')
    np.savetxt(output/'column-projection.csv',np.column_stack((np.arange(w),np.arange(w)*area[0]/w,col,col_mean,bright_cols)),delimiter=',',header='preview_x,x_mm,median_luminance,mean_luminance,bright_fraction',comments='')
    probes=[]
    for x in np.linspace(w*.06,w*.94,17).astype(int):
        line=np.median(gray[:,max(0,x-3):min(w,x+4)],axis=1)
        smooth=cv2.medianBlur(line.astype(np.uint8).reshape(-1,1),9).ravel()
        mask=smooth>200
        changes=np.diff(np.r_[False,mask,False].astype(int));starts=np.flatnonzero(changes==1);ends=np.flatnonzero(changes==-1)
        runs=[(int(a),int(b-1)) for a,b in zip(starts,ends) if b-a>=h*.08]
        if not runs:continue
        leading,trailing=max(runs,key=lambda p:p[1]-p[0])
        probes.append({'x':int(x),'x_mm':x*area[0]/w,'leading_y':leading,'trailing_y':trailing,
                       'leading_mm':leading*area[1]/h,'trailing_mm':trailing*area[1]/h,
                       'span_mm':(trailing-leading)*area[1]/h,'touches_top':leading==0,'touches_bottom':trailing==h-1})
    # Vector charts use only numerical profiles and no external libraries/network.
    panels=[]
    for label,values,length in (('Horizontal projection: row median',row,area[1]),('Horizontal: bright occupancy',bright_rows*255,area[1]),('Vertical projection: column median',col,area[0])):
        positions=np.linspace(0,800,len(values));xy=' '.join(f'{x:.2f},{260-v/255*220:.2f}' for x,v in zip(positions,values))
        panels.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="310" viewBox="-40 -30 880 310"><text x="0" y="-10">{label}</text><path d="M0 30 V260 H800" fill="none" stroke="black"/><polyline points="{xy}" fill="none" stroke="#1269bd" stroke-width="1"/><text x="0" y="280">0 mm</text><text x="720" y="280">{length:.1f} mm</text></svg>')
    (output/'projections.html').write_text('<html><meta charset="utf-8"><title>Numerical scanline projections</title>'+''.join(panels)+'</html>')
    write_json(output/'scanlines.json',probes)
    return probes


def diagnose_scale(image, metadata, max_edge, output, pipeline="production"):
    output.mkdir()
    t0=perf_counter();preview=image.copy();preview.thumbnail((max_edge,max_edge));size=preview.size
    preview.save(output/'01-preview.png')
    grayscale=cv2.cvtColor(np.asarray(preview.convert('RGB')),cv2.COLOR_RGB2GRAY)
    gray=cv2.GaussianBlur(grayscale,(5,5),0)
    Image.fromarray(grayscale).save(output/'02-grayscale.png');Image.fromarray(gray).save(output/'03-denoised.png')
    canny=cv2.Canny(gray,25,80);closed=cv2.morphologyEx(canny,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    otsu,threshold=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    opening_size=15 if pipeline=="baseline" else DocumentGeometryService._analysis_opening_kernel(size)
    opened=cv2.morphologyEx(threshold,cv2.MORPH_OPEN,np.ones((opening_size,opening_size),np.uint8))
    for name,mask in (('04-otsu',threshold),('05-canny',canny),('06-morph-close',closed),('07-morph-open',opened)):
        Image.fromarray(mask).save(output/(name+'.png'))
    stages=(('CANNY_CLOSE',closed),('OTSU',threshold),('OTSU_INVERSE',255-threshold),('OTSU_OPEN',opened))
    candidates=[];principal=[];counter=0
    for stage,mask in stages:
        contours,_=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE if pipeline=="baseline" else cv2.CHAIN_APPROX_NONE)
        main_contours=[]
        for contour in sorted(contours,key=cv2.contourArea,reverse=True):
            area=cv2.contourArea(contour)/(size[0]*size[1])
            if area<.015:continue
            counter+=1;number=counter
            polygon=cv2.approxPolyDP(contour,.02*cv2.arcLength(contour,True),True)
            record={'id':number,'stage':stage,'relative_area':area,'vertices':len(polygon),
                    'bounds':cv2.boundingRect(contour),'accepted':False}
            main_contours.append((number,contour));principal.append(record)
            if not area<=.995 or len(polygon)!=4 or not cv2.isContourConvex(polygon):
                record['rejection']='area_or_nonconvex_or_not_quadrilateral';continue
            initial=polygon[:,0,:].astype(float);center=initial.mean(axis=0)
            initial=initial[np.argsort(np.arctan2(initial[:,1]-center[1],initial[:,0]-center[0]))]
            initial=np.roll(initial,-np.argmin(initial.sum(axis=1)),axis=0)
            should_refine=((initial[:,0]<=1.5)|(initial[:,1]<=1.5)|(initial[:,0]>=size[0]-2.5)|(initial[:,1]>=size[1]-2.5)).any()
            trace,lines=refinement_trace(contour,initial,size)
            if should_refine:
                final,outside=DocumentGeometryService._refine_boundary(contour,initial,size)
                assert np.allclose(final,trace['returned_points']) and outside==trace['extrapolates']
            else:final,outside=initial,False
            inside=np.zeros_like(gray);cv2.fillConvexPoly(inside,final.astype(np.int32),255)
            kernel=np.ones((9,9),np.uint8);outer=cv2.dilate(inside,kernel)-inside;inner=inside-cv2.erode(inside,kernel)
            if not np.any(outer) or not np.any(inner):record['rejection']='no_inside_outside_ring';continue
            contrast=abs(float(gray[outer>0].mean())-float(gray[inner>0].mean()))
            if contrast<4:record['rejection']='contrast_under_4';continue
            confidence=min(.98,.72+min(contrast/100,.18)+min(area,.8)*.1);score=area+contrast/255*.15
            record.update(accepted=True,score=score,contrast=contrast,confidence=confidence,initial=initial,
                          final=final,outside_fit=outside,refinement_requested=bool(should_refine))
            candidates.append((record,contour,trace,lines))
            draw_overlay(preview,initial,title=f'Candidate {number} {stage}: initial polygon').save(output/f'candidate-{number:03d}.png')
        draw_overlay(preview,contours=main_contours,title=f'{stage}: principal contours, numbered').save(output/f'contours-{stage.lower()}.png')
    if not candidates:raise RuntimeError('No accepted candidate in diagnostic input')
    selected,contour,trace,lines=max(candidates,key=lambda item:item[0]['score'])
    initial,final=np.asarray(selected['initial']),np.asarray(selected['final'])
    # Classification-free replay; selection must reproduce production coordinates.
    Probe=type('Probe',(GeometryOnly,),{'MAX_EDGE':max_edge, 'CONTOUR_SAMPLING':'SPARSE' if pipeline=='baseline' else 'DENSE',
        '_analysis_opening_kernel':staticmethod(lambda size: 15) if pipeline=='baseline' else staticmethod(DocumentGeometryService._analysis_opening_kernel)})
    scan=metadata['scan_metadata'];area=scan['physical_area_mm'];dpi=scan['effective_dpi']
    start=perf_counter();result=Probe.detect(image,dpi=dpi,measurement_source='DEVICE_GEOMETRY',physical_area_mm=area)
    replay_ms=(perf_counter()-start)*1000
    assert np.allclose(result.normalized_corners,final/np.array(size),atol=1e-10), 'diagnostic differs from detector'
    draw_overlay(preview,initial,title=f'Selected candidate #{selected["id"]}: initial').save(output/'08-initial-quadrilateral.png')
    marks=[(p,'discarded') for side in trace['sides'] for p in side['discarded_frame_points']]
    marks += [(p,'intersection') for p in trace['intersections_before_clamp']]
    draw_overlay(preview,initial,lines=lines,marked=marks,title='Fits: blue; discarded: magenta; intersections: orange').save(output/'09-refined-lines-and-discarded.png')
    draw_overlay(preview,final,title='Final geometry, classification disabled').save(output/'10-final-quadrilateral.png')
    original_overlay=draw_overlay(image,np.asarray(result.corners),title='Final source-coordinate overlay; original not modified')
    original_overlay.save(output/'11-original-final-overlay.png');original_overlay.close()
    write_json(output/'refinement.json',trace)
    edges=edge_metrics(gray,initial,final,trace,image.size,area)
    # Geometric reasons only; do not call format classification to determine boundaries.
    for edge in edges:
        axis={'TOP':1,'RIGHT':0,'BOTTOM':1,'LEFT':0}[edge['side']]
        endpoints=np.asarray(edge['final_preview_endpoints'])
        values=endpoints[:,axis]
        limit=0 if edge['side'] in ('TOP','LEFT') else (size[axis]-1)
        contacts=abs(values-limit)<=1.5
        edge['geometric_boundary_reason']=('isolated_frame_contact' if contacts.sum()==1 else
            'whole_edge_at_frame_unobserved' if contacts.sum()==2 else
            'visible_contrast_edge' if edge['contrast_support']>=.8 else 'insufficient_contrast_samples_or_support')
    probes=profile_artifacts(gray,area,output)
    summary={'max_edge':max_edge,'preview_size':size,'selected_candidate_id':selected['id'],
             'selected_stage':selected['stage'],'otsu_threshold':otsu,'geometry':{key:value for key,value in asdict(result).items() if key != 'standard_size'},
             'edges':edges,'refinement_fallback':trace['fallback_reason'],
             'observed_corner_intersections':trace['intersections_before_clamp'],
             'scanlines':probes,'replay_ms':replay_ms,'diagnostic_total_ms':(perf_counter()-t0)*1000,
             'pipeline':pipeline,'morph_open_kernel_pixels':opening_size,
             'morph_open_kernel_mm':[opening_size*area[0]/size[0],opening_size*area[1]/size[1]],
             'classification_disabled':True,'boundary_decision_note':'No format-based promotion during diagnostic; reasons assessed geometrically.'}
    write_json(output/'candidates.json',principal);write_json(output/'summary.json',summary)
    images=['01-preview.png','02-grayscale.png','03-denoised.png','04-otsu.png','05-canny.png','06-morph-close.png','07-morph-open.png']
    images += [f'contours-{stage.lower()}.png' for stage,_ in stages]
    images += [f'candidate-{item[0]["id"]:03d}.png' for item in candidates]
    images += ['08-initial-quadrilateral.png','09-refined-lines-and-discarded.png','10-final-quadrilateral.png','11-original-final-overlay.png']
    gallery='<html><meta charset="utf-8"><title>Local detector stages</title><style>body{font-family:sans-serif}img{max-width:900px;max-height:1000px}figure{display:inline-block;vertical-align:top}pre{white-space:pre-wrap}</style><h1>Local diagnostic: no classification</h1><p>Selected candidate '+str(selected['id'])+'</p><a href="projections.html">1D projections</a>'
    gallery+=''.join(f'<figure><figcaption>{html.escape(name)}</figcaption><a href="{name}"><img src="{name}" loading="lazy"></a></figure>' for name in images)
    gallery+='<pre>'+html.escape(json.dumps(summary,default=lambda v:v.tolist() if hasattr(v,'tolist') else float(v),indent=2))+'</pre></html>'
    (output/'index.html').write_text(gallery);preview.close()
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',nargs=2,action='append',required=True,metavar=('IMAGE','METADATA'))
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--scales',nargs='+',type=int,default=[1000,1500,2000])
    parser.add_argument('--pipeline',choices=('baseline','production'),default='production')
    args=parser.parse_args(argv);args.output_root.mkdir(parents=True,exist_ok=False)
    summaries=[]
    for number,(source_path,metadata_path) in enumerate(args.capture,1):
        source=Path(source_path);metadata=json.loads(Path(metadata_path).read_text());capture_dir=args.output_root/f'capture-{number}';capture_dir.mkdir()
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        shutil.copy2(source,capture_dir/'original.png')
        with Image.open(source) as original:
            image=original.convert('RGB')
        rows=[]
        for scale in args.scales:
            row=diagnose_scale(image,metadata,scale,capture_dir/f'edge-{scale}',args.pipeline)
            rows.append(row)
            print(json.dumps({'capture':number,'scale':scale,'size':row['preview_size'],'candidate':row['selected_candidate_id'],
                              'stage':row['selected_stage'],'width_mm':row['geometry']['physical_width_mm'],
                              'height_mm':row['geometry']['physical_height_mm'],'replay_ms':row['replay_ms']},default=float),flush=True)
        image.close()
        assert before==hashlib.sha256(source.read_bytes()).hexdigest(), 'original changed'
        summaries.append({'capture':number,'source_sha256':before,'original_resolution':metadata['image_resolution'],
                          'published_baseline':metadata.get('geometry'), 'scales':rows})
    write_json(args.output_root/'comparison.json',summaries)
    (args.output_root/'index.html').write_text('<html><meta charset="utf-8"><h1>Offline ADF diagnostic</h1><p>No acquisition, classification, upload or original modification.</p>'+''.join(f'<h2>Capture {r["capture"]}</h2><a href="capture-{r["capture"]}/original.png">Original (local copy)</a>'+''.join(f'<p><a href="capture-{r["capture"]}/edge-{s["max_edge"]}/index.html">{s["preview_size"]}: all stages</a></p>' for s in r['scales']) for r in summaries)+'</html>')


if __name__=='__main__':main()
