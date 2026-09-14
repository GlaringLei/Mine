"""Export the current FLAC3D model boundary surfaces to a web-ready GLB.

Run this file from FLAC3D after restoring xieyaqian.f3sav. The exporter keeps
only faces between active zones and null zones (excavations), plus the model
exterior. It does not copy the full volume mesh into the browser asset.
"""

from __future__ import print_function

import json
import io
import math
import os
import shutil
import struct
import tempfile
from datetime import datetime

try:
    import itasca as it
except ImportError:
    it = None


VERTEX_STRUCT = struct.Struct("<6f4B")
VERTEX_STRIDE = VERTEX_STRUCT.size
DEFAULT_SOURCE_NAME = "xieyaqian.f3sav"
WORKSPACE_DIR = r"G:\Save\Grogramming\Vue3\data-v"
DEFAULT_OUTPUT_DIR = os.path.join(
    WORKSPACE_DIR, "public", "models", "xieyaqian"
)
DEFAULT_TEMP_DIR = os.path.join(
    WORKSPACE_DIR, ".codex-tools", "sav", "tmp"
)

PALETTE = (
    (0.00, (0, 11, 56)),
    (0.16, (0, 55, 168)),
    (0.34, (0, 127, 196)),
    (0.52, (0, 168, 107)),
    (0.68, (156, 185, 0)),
    (0.82, (228, 119, 0)),
    (0.93, (230, 43, 0)),
    (1.00, (157, 0, 31)),
)
STREAM_KINDS = ("roadway", "exterior", "high_stress")
TARGET_COLOR = (255, 70, 45, 255)


def _model_name(zone):
    if zone is None:
        return ""
    try:
        return str(zone.model()).strip().lower()
    except Exception:
        return ""


def _is_active(zone):
    return _model_name(zone) not in ("", "null")


def _position(gridpoint):
    value = gridpoint.pos()
    try:
        return float(value[0]), float(value[1]), float(value[2])
    except Exception:
        return float(value.x()), float(value.y()), float(value.z())


def _stress_mpa(zone):
    try:
        return abs(float(zone.stress_min())) / 1000000.0
    except Exception:
        return 0.0


def _face_kind(neighbor):
    if neighbor is None:
        return "exterior"
    if _model_name(neighbor) == "null":
        return "roadway"
    return None


def _iter_boundary_faces():
    for zone in it.zone.list():
        if not _is_active(zone):
            continue
        faces = zone.faces()
        neighbors = zone.adjacent_zones()
        stress = _stress_mpa(zone)
        for index, face in enumerate(faces):
            if face is None:
                continue
            kind = _face_kind(neighbors[index])
            if kind:
                yield kind, tuple(_position(point) for point in face), stress


def _scan_boundaries():
    stats = {
        "roadway_faces": 0,
        "exterior_faces": 0,
        "roadway_stress_sum": 0.0,
        "stress_min": float("inf"),
        "stress_max": float("-inf"),
        "peak_stress": float("-inf"),
        "peak_position": [0.0, 0.0, 0.0],
    }
    for kind, points, stress in _iter_boundary_faces():
        if len(points) < 3:
            continue
        stats[kind + "_faces"] += 1
        if kind == "roadway":
            stats["roadway_stress_sum"] += stress
            stats["stress_min"] = min(stats["stress_min"], stress)
            stats["stress_max"] = max(stats["stress_max"], stress)
            if stress > stats["peak_stress"]:
                stats["peak_stress"] = stress
                stats["peak_position"] = [
                    sum(point[axis] for point in points) / len(points)
                    for axis in range(3)
                ]

    if (
        math.isinf(stats["stress_min"])
        or math.isnan(stats["stress_min"])
    ):
        stats["stress_min"] = 0.0
        stats["stress_max"] = 1.0
    if stats["stress_max"] <= stats["stress_min"]:
        stats["stress_max"] = stats["stress_min"] + 1.0
    stats["stress_average"] = (
        stats["roadway_stress_sum"] / max(stats["roadway_faces"], 1)
    )
    stats["stress_threshold"] = stats["stress_average"] * 1.2
    return stats


def _normalize(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length <= 1e-12:
        return 0.0, 0.0, 1.0
    return tuple(component / length for component in vector)


def _normal(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return _normalize((
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    ))


def _triangles(points):
    for index in range(1, len(points) - 1):
        yield points[0], points[index], points[index + 1]


def _stress_color(stress, stress_min, stress_max):
    ratio = max(0.0, min(1.0, (stress - stress_min) / (stress_max - stress_min)))
    for index in range(1, len(PALETTE)):
        left_position, left_color = PALETTE[index - 1]
        right_position, right_color = PALETTE[index]
        if ratio <= right_position:
            span = max(1e-9, right_position - left_position)
            local = (ratio - left_position) / span
            return tuple(
                int(round(left_color[channel] + (
                    right_color[channel] - left_color[channel]
                ) * local))
                for channel in range(3)
            ) + (255,)
    return PALETTE[-1][1] + (255,)


class VertexStream(object):
    def __init__(self, name):
        if not os.path.isdir(DEFAULT_TEMP_DIR):
            os.makedirs(DEFAULT_TEMP_DIR)
        handle = tempfile.NamedTemporaryFile(
            prefix="flac3d_" + name + "_",
            suffix=".bin",
            dir=DEFAULT_TEMP_DIR,
            delete=False,
        )
        self.path = handle.name
        self.handle = handle
        self.count = 0
        self.byte_length = 0
        self.minimum = [float("inf")] * 3
        self.maximum = [float("-inf")] * 3

    def write_triangle(self, triangle, color):
        normal = _normal(*triangle)
        for point in triangle:
            self.handle.write(VERTEX_STRUCT.pack(
                point[0], point[1], point[2],
                normal[0], normal[1], normal[2],
                color[0], color[1], color[2], color[3],
            ))
            self.count += 1
            self.byte_length += VERTEX_STRIDE
            for axis in range(3):
                self.minimum[axis] = min(self.minimum[axis], point[axis])
                self.maximum[axis] = max(self.maximum[axis], point[axis])

    def close(self):
        self.handle.close()
        if self.count == 0:
            self.minimum = [0.0, 0.0, 0.0]
            self.maximum = [0.0, 0.0, 0.0]

    def remove(self):
        try:
            os.remove(self.path)
        except OSError:
            pass


def _pad4(value):
    return (value + 3) & ~3


def _build_gltf(streams, stress_min, stress_max):
    buffer_views = []
    accessors = []
    meshes = []
    nodes = []
    offset = 0

    material_names = {
        "roadway": "RoadwayStressSurface",
        "exterior": "ModelExterior",
        "high_stress": "HighStressTarget",
    }
    material_indexes = {
        "roadway": 0,
        "exterior": 1,
        "high_stress": 2,
    }

    for kind in STREAM_KINDS:
        stream = streams[kind]
        if stream.count == 0:
            continue
        offset = _pad4(offset)
        view_index = len(buffer_views)
        buffer_views.append({
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": stream.byte_length,
            "byteStride": VERTEX_STRIDE,
            "target": 34962,
        })
        position_index = len(accessors)
        accessors.extend([
            {
                "bufferView": view_index,
                "byteOffset": 0,
                "componentType": 5126,
                "count": stream.count,
                "type": "VEC3",
                "min": stream.minimum,
                "max": stream.maximum,
            },
            {
                "bufferView": view_index,
                "byteOffset": 12,
                "componentType": 5126,
                "count": stream.count,
                "type": "VEC3",
            },
            {
                "bufferView": view_index,
                "byteOffset": 24,
                "componentType": 5121,
                "normalized": True,
                "count": stream.count,
                "type": "VEC4",
            },
        ])
        mesh_index = len(meshes)
        meshes.append({
            "name": material_names[kind],
            "primitives": [{
                "attributes": {
                    "POSITION": position_index,
                    "NORMAL": position_index + 1,
                    "COLOR_0": position_index + 2,
                },
                "material": material_indexes[kind],
                "mode": 4,
            }],
        })
        nodes.append({"name": material_names[kind], "mesh": mesh_index})
        offset += stream.byte_length

    return {
        "asset": {
            "version": "2.0",
            "generator": "SZIC FLAC3D boundary exporter",
        },
        "scene": 0,
        "scenes": [{"name": "xieyaqian", "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": [
            {
                "name": "RoadwayStressVertexColor",
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.78,
                },
            },
            {
                "name": "ExteriorContext",
                "doubleSided": True,
                "alphaMode": "BLEND",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.42, 0.56, 0.61, 0.16],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.9,
                },
            },
            {
                "name": "HighStressTargetOverlay",
                "doubleSided": True,
                "alphaMode": "BLEND",
                "emissiveFactor": [1.0, 0.04, 0.01],
                "pbrMetallicRoughness": {
                    "baseColorFactor": [1.0, 0.12, 0.04, 0.9],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.36,
                },
            },
        ],
        "buffers": [{"byteLength": _pad4(offset)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "extras": {
            "stressField": "minimum principal stress magnitude",
            "stressUnit": "MPa",
            "stressRange": [stress_min, stress_max],
        },
    }


def _write_glb(path, document, streams):
    json_bytes = json.dumps(
        document, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    json_length = _pad4(len(json_bytes))
    binary_length = document["buffers"][0]["byteLength"]
    total_length = 12 + 8 + json_length + 8 + binary_length

    with open(path, "wb") as output:
        output.write(struct.pack("<4sII", b"glTF", 2, total_length))
        output.write(struct.pack("<I4s", json_length, b"JSON"))
        output.write(json_bytes)
        output.write(b" " * (json_length - len(json_bytes)))
        output.write(struct.pack("<I4s", binary_length, b"BIN\x00"))

        written = 0
        for kind in STREAM_KINDS:
            stream = streams[kind]
            if stream.count == 0:
                continue
            aligned = _pad4(written)
            output.write(b"\x00" * (aligned - written))
            written = aligned
            with open(stream.path, "rb") as source:
                shutil.copyfileobj(source, output, 8 * 1024 * 1024)
            written += stream.byte_length
        output.write(b"\x00" * (binary_length - written))


def export_current_model(output_dir=DEFAULT_OUTPUT_DIR,
                         source_name=DEFAULT_SOURCE_NAME):
    if it is None:
        raise RuntimeError(
            "The 'itasca' module is unavailable. Run this script inside FLAC3D."
        )

    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    print("[1/3] Scanning FLAC3D boundary faces...")
    stats = _scan_boundaries()
    print(
        "      roadway faces: {0}, exterior faces: {1}".format(
            stats["roadway_faces"], stats["exterior_faces"]
        )
    )
    print(
        "      stress range: {0:.3f} - {1:.3f} MPa".format(
            stats["stress_min"], stats["stress_max"]
        )
    )

    streams = {
        "roadway": VertexStream("roadway"),
        "exterior": VertexStream("exterior"),
        "high_stress": VertexStream("high_stress"),
    }
    try:
        print("[2/3] Writing surface triangles...")
        target_face_count = 0
        target_point_sum = [0.0, 0.0, 0.0]
        target_point_count = 0
        target_minimum = [float("inf")] * 3
        target_maximum = [float("-inf")] * 3
        for kind, points, stress in _iter_boundary_faces():
            if len(points) < 3:
                continue
            color = _stress_color(
                stress, stats["stress_min"], stats["stress_max"]
            )
            for triangle in _triangles(points):
                streams[kind].write_triangle(triangle, color)
                if kind == "roadway" and stress >= stats["stress_threshold"]:
                    streams["high_stress"].write_triangle(
                        triangle, TARGET_COLOR
                    )
            if kind == "roadway" and stress >= stats["stress_threshold"]:
                target_face_count += 1
                for point in points:
                    target_point_count += 1
                    for axis in range(3):
                        target_point_sum[axis] += point[axis]
                        target_minimum[axis] = min(
                            target_minimum[axis], point[axis]
                        )
                        target_maximum[axis] = max(
                            target_maximum[axis], point[axis]
                        )
        for stream in streams.values():
            stream.close()

        document = _build_gltf(
            streams, stats["stress_min"], stats["stress_max"]
        )
        glb_path = os.path.join(output_dir, "model.glb")
        _write_glb(glb_path, document, streams)

        manifest = {
            "ready": True,
            "source": {
                "name": source_name,
                "type": "ITASCA SAVE FILE",
                "product": "FLAC3D",
                "version": "6.0",
                "title": (
                    "Deep roadway variable-diameter pressure-relief base model"
                ),
            },
            "model": {
                "url": "model.glb",
                "coordinateUnit": "m",
                "roadwayFaceCount": stats["roadway_faces"],
                "exteriorFaceCount": stats["exterior_faces"],
                "roadwayVertexCount": streams["roadway"].count,
                "exteriorVertexCount": streams["exterior"].count,
                "highStressFaceCount": target_face_count,
                "highStressVertexCount": streams["high_stress"].count,
            },
            "field": {
                "name": "minimum principal stress magnitude",
                "unit": "MPa",
                "range": [stats["stress_min"], stats["stress_max"]],
            },
            "targetIdentification": {
                "method": "roadway face stress >= average stress * 1.2",
                "thresholdMultiplier": 1.2,
                "averageStressMpa": stats["stress_average"],
                "thresholdStressMpa": stats["stress_threshold"],
                "peakStressMpa": stats["peak_stress"],
                "peakPosition": stats["peak_position"],
                "highStressFaceCount": target_face_count,
                "roadwayFaceRatio": (
                    float(target_face_count)
                    / max(stats["roadway_faces"], 1)
                ),
                "bounds": [target_minimum, target_maximum],
                "centroid": [
                    value / max(target_point_count, 1)
                    for value in target_point_sum
                ],
            },
            "generatedAt": datetime.now().isoformat(),
        }
        with io.open(
            os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8"
        ) as manifest_file:
            json.dump(
                manifest, manifest_file, ensure_ascii=False, indent=2
            )

        print("[3/3] Export complete: " + glb_path)
        return glb_path
    finally:
        for stream in streams.values():
            try:
                stream.close()
            except Exception:
                pass
            stream.remove()


if __name__ == "__main__":
    export_current_model()
