"""Bounded vector preparation. No URLs, remote sources, or implicit source rights."""
from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

MAX_FILE = 4_000_000
MAX_FEATURES = 2000


def _members(archive: zipfile.ZipFile):
    infos = archive.infolist()
    if len(infos) > 100 or sum(i.file_size for i in infos) > 40_000_000:
        raise ValueError("Archive exceeds the 100-file / 40 MB expanded limit.")
    for item in infos:
        path = PurePosixPath(item.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts) or (item.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Unsafe archive path or symbolic link.")
    return infos


def _xml(data: bytes, suffix: str) -> dict:
    if re.search(br"<!DOCTYPE|<!ENTITY", data, re.I) or b"\x00" in data:
        raise ValueError("Use UTF-8 XML without DTDs or entities.")
    root = ET.fromstring(data)
    tag = lambda element: element.tag.rsplit("}", 1)[-1]
    features = []
    if suffix == ".gpx":
        for element in root.iter():
            if tag(element) in {"wpt", "rtept"}:
                coords = [float(element.attrib["lon"]), float(element.attrib["lat"])]
                name = next((e.text for e in element if tag(e) == "name"), "GPX point")
                features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": coords}, "properties": {"name": name}})
            if tag(element) == "trkseg":
                coords = [[float(e.attrib["lon"]), float(e.attrib["lat"])] for e in element if tag(e) == "trkpt"]
                features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": {"name": "GPX track"}})
    else:
        for placemark in (e for e in root.iter() if tag(e) == "Placemark"):
            name = next((e.text for e in placemark if tag(e) == "name"), "KML feature")
            for geom in placemark.iter():
                kind = tag(geom)
                if kind not in {"Point", "LineString", "Polygon"}:
                    continue
                arrays = [[[float(v) for v in pair.split(",")] for pair in (e.text or "").split()] for e in geom.iter() if tag(e) == "coordinates"]
                if not arrays:
                    continue
                coords = arrays[0][0] if kind == "Point" else arrays[0] if kind == "LineString" else arrays
                features.append({"type": "Feature", "geometry": {"type": kind, "coordinates": coords}, "properties": {"name": name}})
    return {"type": "FeatureCollection", "features": features}


def prepare_vector(payload: dict) -> dict:
    import geopandas as gpd
    import numpy as np
    import pandas as pd
    import pyogrio
    import pyproj
    import shapely
    from shapely.geometry import shape

    pyproj.network.set_network_enabled(False)
    filename = Path(str(payload.get("filename", ""))).name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".geojson", ".json", ".csv", ".zip", ".gpkg", ".kml", ".kmz", ".gpx"}:
        raise ValueError("Supported formats: GeoJSON, coordinate CSV, zipped Shapefile, GeoPackage, KML/KMZ, GPX.")
    data = base64.b64decode(payload.get("content_base64", ""), validate=True)
    if not data or len(data) > MAX_FILE:
        raise ValueError("Private preparation accepts files up to 4 MB.")
    source = payload.get("source_crs")
    if source is not None and not re.fullmatch(r"EPSG:[1-9][0-9]{2,6}", str(source)):
        raise ValueError("Source CRS must be an EPSG code; PROJ strings and URLs are not accepted.")
    repair = payload.get("repair", False)
    drop = payload.get("drop_invalid", False)
    if type(repair) is not bool or type(drop) is not bool:
        raise ValueError("Repair and drop-invalid must be explicit booleans.")
    diagnostics = []
    def input_features(features):
        if not isinstance(features, list) or not 1 <= len(features) <= MAX_FEATURES:
            raise ValueError("Input must contain 1–2,000 features.")
        closed = 0
        for feature in features:
            geom = feature.get("geometry") if isinstance(feature, dict) else None
            if not isinstance(geom, dict):
                continue  # Null handling below requires explicit drop.
            rings = geom.get("coordinates", []) if geom.get("type") == "Polygon" else [r for p in geom.get("coordinates", []) for r in p] if geom.get("type") == "MultiPolygon" else []
            for ring in rings:
                if isinstance(ring, list) and ring and ring[0] != ring[-1]:
                    if not repair:
                        raise ValueError("Unclosed polygon rings require explicit geometry repair.")
                    ring.append(ring[0]); closed += 1
        diagnostics.append(f"Explicitly closed {closed} polygon rings.")
        return features
    with tempfile.TemporaryDirectory(prefix="observatory-prep-") as directory:
        root = Path(directory)
        if suffix in {".zip", ".kmz"}:
            archive = zipfile.ZipFile(io.BytesIO(data))
            infos = _members(archive)
            if suffix == ".kmz":
                kmls = [i for i in infos if Path(i.filename).suffix.lower() == ".kml"]
                if len(kmls) != 1:
                    raise ValueError("KMZ must contain exactly one KML document.")
                data = archive.read(kmls[0]); suffix = ".kml"
            else:
                shps = [i for i in infos if Path(i.filename).suffix.lower() == ".shp"]
                if len(shps) != 1:
                    raise ValueError("ZIP must contain exactly one Shapefile dataset.")
                allowed = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix"}
                stem = str(PurePosixPath(shps[0].filename).with_suffix(""))
                paths = []
                for item in infos:
                    path = PurePosixPath(item.filename)
                    if str(path.with_suffix("")) == stem and path.suffix.lower() in allowed:
                        destination = root / ("input" + path.suffix.lower())
                        destination.write_bytes(archive.read(item)); paths.append(destination.suffix)
                if not {".shp", ".shx", ".dbf"}.issubset(paths):
                    raise ValueError("Shapefile requires .shp, .shx, and .dbf companions.")
                frame = pyogrio.read_dataframe(root / "input.shp", max_features=MAX_FEATURES + 1)
        if suffix in {".kml", ".gpx"}:
            if source and source != "EPSG:4326":
                raise ValueError("KML and GPX use WGS84 longitude/latitude; select EPSG:4326.")
            frame = gpd.GeoDataFrame.from_features(input_features(_xml(data, suffix)["features"]), crs="EPSG:4326")
        elif suffix in {".geojson", ".json"}:
            raw = json.loads(data, parse_constant=lambda v: (_ for _ in ()).throw(ValueError("Nonfinite JSON.")))
            if not isinstance(raw, dict) or "crs" in raw:
                raise ValueError("Use RFC 7946-shaped GeoJSON without a legacy CRS member, then select source CRS explicitly.")
            features = raw.get("features") if raw.get("type") == "FeatureCollection" else [raw] if raw.get("type") == "Feature" else None
            if not isinstance(features, list) or len(features) > MAX_FEATURES:
                raise ValueError("Expected at most 2,000 GeoJSON features.")
            frame = gpd.GeoDataFrame.from_features(input_features(features), crs=source)
        elif suffix == ".csv":
            table = pd.read_csv(io.BytesIO(data), nrows=MAX_FEATURES + 1)
            if len(table) > MAX_FEATURES:
                raise ValueError("CSV exceeds 2,000 input rows; split the source instead of truncating it.")
            lat = [c for c in table.columns if c.lower().strip() in {"latitude", "lat", "y"}]
            lon = [c for c in table.columns if c.lower().strip() in {"longitude", "lon", "lng", "x"}]
            if len(lat) != 1 or len(lon) != 1:
                raise ValueError("CSV requires exactly one x/longitude and one y/latitude column.")
            x = pd.to_numeric(table[lon[0]], errors="coerce"); y = pd.to_numeric(table[lat[0]], errors="coerce")
            good = np.isfinite(x) & np.isfinite(y)
            if not good.all() and not drop:
                raise ValueError("CSV has missing or nonnumeric coordinates; enable explicit drop-invalid to retain the valid subset.")
            diagnostics.append(f"Dropped {int((~good).sum())} rows with invalid coordinates.")
            table = table[good]
            frame = gpd.GeoDataFrame(table, geometry=gpd.points_from_xy(x[good], y[good]), crs=source)
        elif suffix == ".gpkg":
            path = root / "input.gpkg"; path.write_bytes(data)
            layers = pyogrio.list_layers(path)
            requested = payload.get("layer")
            if len(layers) > 1 and not requested:
                return {"layers": [str(row[0]) for row in layers], "diagnostics": ["Choose one GeoPackage layer explicitly."]}
            if requested and requested not in {str(row[0]) for row in layers}:
                raise ValueError("Requested GeoPackage layer does not exist.")
            frame = pyogrio.read_dataframe(path, layer=requested, max_features=MAX_FEATURES + 1)
        if len(frame) > MAX_FEATURES or len(frame) == 0:
            raise ValueError("Input must contain 1–2,000 features; no silent truncation is performed.")
        if frame.crs is None:
            if not source:
                raise ValueError("Missing source CRS. Specify an EPSG code; it will not be guessed.")
            frame = frame.set_crs(source)
        elif source and frame.crs != pyproj.CRS(source):
            raise ValueError(f"Declared CRS {frame.crs} conflicts with selected {source}.")
        source_crs = frame.crs.to_string()
        missing = frame.geometry.isna() | frame.geometry.is_empty
        if missing.any() and not drop:
            raise ValueError("Null/empty geometries require explicit drop-invalid confirmation.")
        frame = frame[~missing].copy()
        if len(frame) == 0:
            raise ValueError("No nonempty features remain after preparation.")
        invalid = ~frame.geometry.is_valid
        if invalid.any() and not repair:
            raise ValueError(f"{int(invalid.sum())} invalid geometries. Preview again with explicit repair enabled.")
        repaired = int(invalid.sum())
        if repair:
            frame.geometry = frame.geometry.map(shapely.make_valid)
        if frame.geometry.geom_type.isin(["GeometryCollection"]).any():
            raise ValueError("Repair produced a GeometryCollection. Review and separate its parts outside this bounded workspace; no part was silently discarded.")
        frame = frame.to_crs("EPSG:4326")
        coordinates = shapely.get_coordinates(frame.geometry)
        if len(coordinates) > 40000 or not np.isfinite(coordinates).all() or (np.abs(coordinates[:, 0]) > 180).any() or (np.abs(coordinates[:, 1]) > 90).any():
            raise ValueError("Output exceeds coordinate limits or is outside WGS84 bounds.")
        raw = json.loads(frame.to_json(na="null", drop_id=True))
        for i, feature in enumerate(raw["features"]):
            feature["id"] = f"feature-{i + 1}"
        diagnostics.extend([f"Validated {len(frame)} geometries with GEOS; repaired {repaired}.", "Output feature IDs are generated sequentially; format conversion may flatten schemas and does not preserve file styling.", f"Transformed {source_crs} to EPSG:4326. Source accuracy and rights are not established by conversion."])
        return {"collection": raw, "diagnostics": diagnostics, "source_crs": source_crs, "output_crs": "EPSG:4326", "publication_authorized": False}


def export_gpkg(layer: dict, target: str = "EPSG:4326") -> dict:
    import geopandas as gpd
    import pyogrio
    import pyproj
    pyproj.network.set_network_enabled(False)
    if not re.fullmatch(r"EPSG:[1-9][0-9]{2,6}", target):
        raise ValueError("Export CRS must be an EPSG code.")
    frame = gpd.GeoDataFrame.from_features(layer["features"], crs="EPSG:4326").to_crs(target)
    with tempfile.TemporaryDirectory(prefix="observatory-export-") as directory:
        path = Path(directory) / "observatory-draft.gpkg"
        pyogrio.write_dataframe(frame, path, driver="GPKG", layer="draft", dataset_metadata={"publication_authorized": "false", "source": json.dumps(layer["source"]), "methods": json.dumps(layer["steps"])})
        return {"filename": path.name, "mime": "application/geopackage+sqlite3", "content_base64": base64.b64encode(path.read_bytes()).decode(), "publication_authorized": False}
