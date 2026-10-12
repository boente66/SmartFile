"""Local, bounded-resolution page detection. Never infers millimetres from aspect ratio."""
from dataclasses import replace
from math import atan2, degrees, hypot, isfinite
from time import perf_counter

import numpy as np

from app.models.document_geometry import DocumentGeometryResult


class DocumentGeometryService:
    MAX_EDGE = 1000
    CONTOUR_SAMPLING = "DENSE"
    SIZES = {"A4": (210, 297), "LETTER": (215.9, 279.4), "LEGAL": (215.9, 355.6),
             "A5": (148, 210), "A3": (297, 420)}
    FULL = ((0., 0.), (1., 0.), (1., 1.), (0., 1.))

    @classmethod
    def classify(cls, width, height, confidence=1., source="SCANNER_DPI"):
        if width is None or height is None or confidence < .8 or source == "UNKNOWN": return "CUSTOM"
        small, large = sorted((width, height))
        matches = []
        for name, (w, h) in cls.SIZES.items():
            # Require BOTH absolute and relative error; 205x290 must not become A4.
            tolerance = 1.8 if source == "ESTIMATED" else 2.5
            if abs(small-w) <= min(tolerance, w*.012) and abs(large-h) <= min(tolerance, h*.012):
                matches.append((abs(small-w)+abs(large-h), name))
        return min(matches)[1] if matches else "CUSTOM"

    @classmethod
    def from_corners(cls, image_size, normalized_corners, *, dpi=None, measurement_source="UNKNOWN",
                     physical_area_mm=None, confidence=.9, detection_status="MANUAL"):
        if len(image_size)!=2 or not all(isfinite(v) and v>0 for v in image_size):
            raise ValueError("Dimensões da imagem inválidas.")
        if not isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Confiança inválida.")
        points = np.asarray(normalized_corners, dtype=float)
        if points.shape != (4, 2) or not np.isfinite(points).all() or (points < 0).any() or (points > 1).any():
            raise ValueError("Os quatro cantos devem estar dentro da imagem.")
        edges_normalized = [points[(i+1)%4]-points[i] for i in range(4)]
        cross = [a[0]*b[1]-a[1]*b[0] for a,b in zip(edges_normalized, edges_normalized[1:]+edges_normalized[:1])]
        area = abs(sum(points[i,0]*points[(i+1)%4,1]-points[(i+1)%4,0]*points[i,1] for i in range(4)))/2
        if min(cross) <= 0 or area < .002:
            raise ValueError("Enquadramento cruzado, invertido ou pequeno demais.")
        w, h = image_size
        pixels = points*np.array([w, h])
        edges = [hypot(*(pixels[(i+1)%4]-pixels[i])) for i in range(4)]
        pw, ph = (edges[0]+edges[2])/2, (edges[1]+edges[3])/2
        mw = mh = None
        source = "UNKNOWN"
        if physical_area_mm and all(isfinite(v) and 0 < v <= 2000 for v in physical_area_mm):
            physical = points*np.array(physical_area_mm)
            physical_edges = [hypot(*(physical[(i+1)%4]-physical[i])) for i in range(4)]
            mw, mh = (physical_edges[0]+physical_edges[2])/2, (physical_edges[1]+physical_edges[3])/2
            source = measurement_source if measurement_source != "UNKNOWN" else "ESTIMATED"
        elif dpi is not None:
            pair = (dpi, dpi) if isinstance(dpi, (float, int)) else dpi
            if len(pair) == 2 and all(isfinite(v) and 25 <= v <= 9600 for v in pair):
                physical = pixels/np.array(pair)*25.4
                physical_edges = [hypot(*(physical[(i+1)%4]-physical[i])) for i in range(4)]
                mw, mh = (physical_edges[0]+physical_edges[2])/2, (physical_edges[1]+physical_edges[3])/2
                source = measurement_source if measurement_source != "UNKNOWN" else "ESTIMATED"
        orientation = "SQUARE_OR_UNDETERMINED" if abs(pw-ph)/max(pw,ph) < .025 else "PORTRAIT" if ph > pw else "LANDSCAPE"
        skew = degrees(atan2(pixels[1,1]-pixels[0,1],pixels[1,0]-pixels[0,0]))
        perspective = (abs(edges[0]-edges[2])/max(edges[0],edges[2]) > .04 or
                       abs(edges[1]-edges[3])/max(edges[1],edges[3]) > .04 or
                       abs(float(np.dot(pixels[1]-pixels[0],pixels[3]-pixels[0])))/(edges[0]*edges[3]) > .08)
        if perspective and source != "UNKNOWN": source = "ESTIMATED"
        clipping = any(x <= .003 or x >= .997 or y <= .003 or y >= .997 for x,y in points)
        return DocumentGeometryResult(tuple(map(tuple,pixels)),tuple(map(tuple,points)),pw,ph,mw,mh,
            cls.classify(mw,mh,confidence,source),orientation,skew,perspective,confidence,
            detection_status,source,clipping)

    @staticmethod
    def _refine_boundary(contour, points, size):
        """Fit visible sides, excluding frame pixels from sloping/clipped edges.

        A polygon approximation can connect a frame corner to a real edge and
        invent a slope/length. Preserve out-of-frame intersections as evidence,
        while returning only valid image coordinates to the overlay.
        """
        import cv2
        samples = contour[:, 0, :].astype(float)
        lines = []
        width, height = size
        for index in range(4):
            start, end = points[index], points[(index + 1) % 4]
            delta = end - start
            length = np.linalg.norm(delta)
            if length < 3: return points, False
            direction = delta / length
            projection = (samples - start) @ direction
            distance = np.abs((samples[:, 0] - start[0]) * direction[1]
                              - (samples[:, 1] - start[1]) * direction[0])
            selected = samples[(projection > length * .08) & (projection < length * .92)
                               & (distance < max(3., length * .025))]
            # A whole side coincident with the frame is not a visible paper edge.
            on_frame = (abs(start[0] - end[0]) < 2 and (max(start[0], end[0]) < 2 or min(start[0], end[0]) > width - 3)
                        or abs(start[1] - end[1]) < 2 and (max(start[1], end[1]) < 2 or min(start[1], end[1]) > height - 3))
            if not on_frame and len(selected):
                selected = selected[(selected[:, 0] > 1) & (selected[:, 0] < width - 2)
                                    & (selected[:, 1] > 1) & (selected[:, 1] < height - 2)]
            if len(selected) >= 4 and np.ptp(selected @ direction) > length * .35:
                vx, vy, x, y = cv2.fitLine(selected.astype(np.float32), cv2.DIST_HUBER, 0, .01, .01).ravel()
                lines.append((np.array([float(x), float(y)]), np.array([float(vx), float(vy)])))
            else:
                lines.append((start, direction))
        refined = []
        for index in range(4):
            a, u = lines[(index - 1) % 4]
            b, v = lines[index]
            matrix = np.column_stack((u, -v))
            if abs(np.linalg.det(matrix)) < .1: return points, False
            point = a + np.linalg.solve(matrix, b - a)[0] * u
            # Discard an unstable fit rather than replace the detected sheet.
            if np.linalg.norm(point - points[index]) > max(size) * .04: return points, False
            refined.append(point)
        refined = np.array(refined)
        outside = ((refined[:, 0] < -2) | (refined[:, 1] < -2)
                   | (refined[:, 0] > width + 1) | (refined[:, 1] > height + 1)).any()
        return np.clip(refined, [0., 0.], [width - 1., height - 1.]), bool(outside)

    @staticmethod
    def _visible_edge_support(gray, points, index):
        """Fraction of independent samples with a consistent contrast boundary."""
        start, end = points[index], points[(index + 1) % 4]
        delta = end - start
        normal = np.array([-delta[1], delta[0]]) / max(1., np.linalg.norm(delta))
        center = points.mean(axis=0)
        if np.dot(normal, center - (start + end) / 2) < 0: normal = -normal
        differences = []
        height, width = gray.shape
        for fraction in np.linspace(.12, .88, 21):
            point = start + delta * fraction
            inside, outside = point + normal * 3, point - normal * 3
            if not all(1 <= p[0] < width - 1 and 1 <= p[1] < height - 1 for p in (inside, outside)):
                continue
            samples = []
            for p in (inside, outside):
                x, y = np.rint(p).astype(int)
                samples.append(float(np.median(gray[y-1:y+2, x-1:x+2])))
            differences.append(samples[0] - samples[1])
        if len(differences) < 15: return 0.
        differences = np.array(differences)
        return float(max((differences >= 8).mean(), (differences <= -8).mean()))

    @classmethod
    def _resolve_boundary(cls, result, points, gray, *, outside_fit, dpi, physical_area_mm):
        if not result.possible_clipping:
            return replace(result, boundary_status="COMPLETE", boundary_evidence=("four_visible_edges",))
        height, width = gray.shape
        evidence = []
        coincident = []
        # Pixel-center limits, not screen coordinates. Every contacting vertex
        # must belong to a WHOLE aligned side; a truncated/sloping corner fails.
        contacts = np.array([(points[:, 0] <= 1.5), (points[:, 0] >= width - 2.5),
                             (points[:, 1] <= 1.5), (points[:, 1] >= height - 2.5)])
        for index in range(4):
            if any(mask[index] and mask[(index+1) % 4] for mask in contacts):
                coincident.append(index)
        unmatched_contact = False
        for mask in contacts:
            covered = {i for index in range(4) if mask[index] and mask[(index+1) % 4]
                       for i in (index, (index+1) % 4)}
            if not set(np.flatnonzero(mask)) <= covered: unmatched_contact = True
        if outside_fit: evidence.append("visible_edge_extrapolates_outside_capture")
        if unmatched_contact: evidence.append("truncated_or_sloping_corner")
        if not 1 <= len(coincident) <= 2: evidence.append("insufficient_visible_edges")
        if result.perspective_detected: evidence.append("perspective_requires_review")
        if result.measurement_source not in {"DEVICE_GEOMETRY", "SCANNER_DPI", "CALIBRATED"}:
            evidence.append("no_trusted_physical_measurement")
        if result.standard_size == "CUSTOM": evidence.append("no_unambiguous_physical_format")
        if result.confidence < .8: evidence.append("weak_initial_detection")
        # When BOTH metrologies are provided they must agree, independently of
        # the standard-size candidate. Capability/max area alone is no evidence.
        if physical_area_mm and dpi is not None:
            pair = (dpi, dpi) if isinstance(dpi, (int, float)) else dpi
            if len(pair) != 2 or not all(isfinite(v) and 25 <= v <= 9600 for v in pair):
                evidence.append("invalid_effective_dpi")
            else:
                original_points = np.asarray(result.corners)
                normalized = np.asarray(result.normalized_corners)
                for axis in (0, 1):
                    nonzero = normalized[:, axis] > .001
                    if nonzero.any():
                        pixels = float(np.median(original_points[nonzero, axis] / normalized[nonzero, axis]))
                        measured = pixels * 25.4 / pair[axis]
                        if abs(measured - physical_area_mm[axis]) / physical_area_mm[axis] > .012:
                            evidence.append("dpi_and_acquisition_geometry_disagree")
                            break
        visible = [index for index in range(4) if index not in coincident]
        supports = tuple(round(cls._visible_edge_support(gray, points, index), 3) for index in visible)
        if any(value < .8 for value in supports): evidence.append("unstable_visible_boundary")
        if not evidence:
            # No confidence floor/boost: keep the contrast-derived score.
            return replace(result, possible_clipping=False, boundary_status="COINCIDENT",
                           boundary_evidence=("aligned_capture_boundary", "trusted_physical_format",
                                              "visible_edge_support=" + str(supports)))
        return replace(result, confidence=min(.55, result.confidence), detection_status="PARTIAL",
                       measurement_source="ESTIMATED" if result.physical_width_mm is not None else "UNKNOWN",
                       standard_size="CUSTOM", boundary_status="INCOMPLETE", boundary_evidence=tuple(evidence))

    @staticmethod
    def _analysis_opening_kernel(size):
        # Preserve the established 15 px footprint at the normal analysis size.
        # Larger diagnostic previews need the same footprint in source space,
        # otherwise ADF strips reconnect to the sheet and win as candidates.
        value = max(15, round(15 * max(size) / 1000))
        return value if value % 2 else value + 1

    @classmethod
    def detect(cls, image, *, dpi=None, measurement_source="UNKNOWN", physical_area_mm=None, cancelled=lambda:False):
        start = perf_counter()
        preview = image.copy()
        preview.thumbnail((cls.MAX_EDGE, cls.MAX_EDGE))
        size = preview.size
        try:
            import cv2
            if cancelled(): raise InterruptedError
            gray = cv2.cvtColor(np.asarray(preview.convert("RGB")),cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray,(5,5),0)
            candidates = []
            edges = cv2.Canny(gray,25,80)
            edges = cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
            _, threshold = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
            # ADF backing strips can join the paper contour to the acquisition frame.
            # Opening separates thin backing strips without changing the original image.
            opening_size = cls._analysis_opening_kernel(size)
            opened = cv2.morphologyEx(threshold,cv2.MORPH_OPEN,np.ones((opening_size,opening_size),np.uint8))
            for mask in (edges,threshold,255-threshold,opened):
                if cancelled(): raise InterruptedError
                # The line fitter trims endpoints; SIMPLE can leave zero samples
                # on a straight edge. Dense boundary samples retain its support.
                sampling = cv2.CHAIN_APPROX_NONE if cls.CONTOUR_SAMPLING == "DENSE" else cv2.CHAIN_APPROX_SIMPLE
                contours,_ = cv2.findContours(mask,cv2.RETR_LIST,sampling)
                for contour in contours:
                    area = cv2.contourArea(contour)/(size[0]*size[1])
                    if not .015 <= area <= .995: continue
                    polygon = cv2.approxPolyDP(contour,.02*cv2.arcLength(contour,True),True)
                    if len(polygon)!=4 or not cv2.isContourConvex(polygon): continue
                    points = polygon[:,0,:].astype(float)
                    center = points.mean(axis=0)
                    points = points[np.argsort(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))]
                    points = np.roll(points,-np.argmin(points.sum(axis=1)),axis=0)
                    outside_fit = False
                    if ((points[:, 0] <= 1.5) | (points[:, 1] <= 1.5)
                            | (points[:, 0] >= size[0]-2.5) | (points[:, 1] >= size[1]-2.5)).any():
                        points, outside_fit = cls._refine_boundary(contour, points, size)
                    normalized = points/np.array(size)
                    # Reject frame/background candidates without a contrasting boundary.
                    inside = np.zeros_like(gray); cv2.fillConvexPoly(inside,points.astype(np.int32),255)
                    kernel = np.ones((9,9),np.uint8)
                    outer = cv2.dilate(inside,kernel)-inside
                    inner = inside-cv2.erode(inside,kernel)
                    if not np.any(outer) or not np.any(inner): continue
                    contrast = abs(float(gray[outer>0].mean())-float(gray[inner>0].mean()))
                    if contrast < 4: continue
                    confidence = min(.98,.72 + min(contrast/100,.18)+min(area,.8)*.1)
                    score = area + contrast/255*.15
                    candidates.append((score,normalized,confidence,points,outside_fit))
            if candidates:
                _,corners,confidence,points,outside_fit = max(candidates,key=lambda item:item[0])
                result = cls.from_corners(image.size,corners,dpi=dpi,measurement_source=measurement_source,
                                          physical_area_mm=physical_area_mm,confidence=confidence,detection_status="DETECTED")
                result = cls._resolve_boundary(result, points, gray, outside_fit=outside_fit,
                                               dpi=dpi, physical_area_mm=physical_area_mm)
            else:
                result = cls.from_corners(image.size,cls.FULL,confidence=0,detection_status="NOT_DETECTED")
        except InterruptedError:
            raise
        except Exception:
            result = cls.from_corners(image.size,cls.FULL,confidence=0,detection_status="NOT_DETECTED")
        finally:
            preview.close()
        return replace(result,analysis_resolution=size,detection_ms=(perf_counter()-start)*1000)

    @staticmethod
    def transform(image, geometry):
        """Always transform a copy of the original, never a previous result."""
        import cv2
        width,height = max(1,round(geometry.pixel_width)),max(1,round(geometry.pixel_height))
        matrix = cv2.getPerspectiveTransform(np.float32(geometry.corners),
                    np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]]))
        from PIL import Image
        return Image.fromarray(cv2.warpPerspective(np.asarray(image.convert("RGB")),matrix,(width,height)))
