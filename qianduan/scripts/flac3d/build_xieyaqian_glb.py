"""Build the browser GLB from a captured FLAC3D FISH surface transcript."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Tuple

from export_xieyaqian_glb import (
    TARGET_COLOR,
    VertexStream,
    _build_gltf,
    _stress_color,
    _triangles,
    _write_glb,
)


Point = Tuple[float, float, float]
FaceKey = Tuple[int, ...]
CURSOR_FORWARD = re.compile(r"\x1b\[(\d*)C")
ANSI_SEQUENCE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class Face:
    points: Tuple[Point, ...]
    compression_mpa: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "transcript",
        nargs="?",
        default=r".codex-tools\sav\surface_extract_full.out",
    )
    parser.add_argument(
        "--output-dir",
        default=r"public\models\xieyaqian",
    )
    parser.add_argument("--source-name", default="xieyaqian.f3sav")
    parser.add_argument("--source-size-bytes", type=int, default=3872549718)
    parser.add_argument("--source-sha256")
    parser.add_argument(
        "--source-title",
        default="Deep roadway variable-diameter pressure-relief base model",
    )
    return parser.parse_args()


def iter_record_lines(path: str) -> Iterable[str]:
    started = False
    with open(path, "r", encoding="utf-8", errors="replace", newline=None) as source:
        for raw_line in source:
            line = CURSOR_FORWARD.sub(
                lambda match: " " * int(match.group(1) or "1"),
                raw_line,
            )
            line = ANSI_SEQUENCE.sub("", line).strip()
            if not started:
                marker = line.find("CODEX_SURFACE_BEGIN")
                if marker >= 0:
                    started = True
                continue
            if line.startswith("CODEX_SURFACE_END"):
                yield line
                return
            if line.startswith("CFACE ") or line.startswith("CVERT "):
                yield line
    raise ValueError("Transcript does not contain CODEX_SURFACE_END")


def parse_faces(path: str):
    faces: Dict[FaceKey, Face] = {}
    raw_face_count = 0
    duplicate_count = 0
    coordinate_min = [math.inf, math.inf, math.inf]
    coordinate_max = [-math.inf, -math.inf, -math.inf]
    records = iter(iter_record_lines(path))

    for line in records:
        if line.startswith("CODEX_SURFACE_END"):
            declared_count = int(line.split()[1])
            if declared_count != raw_face_count:
                raise ValueError(
                    "Declared face count {0} differs from parsed count {1}".format(
                        declared_count, raw_face_count
                    )
                )
            return (
                faces,
                {
                    "rawFaceCount": raw_face_count,
                    "duplicateFaceCount": duplicate_count,
                    "uniqueFaceCount": len(faces),
                    "bounds": [coordinate_min, coordinate_max],
                },
            )

        header = line.split()
        if len(header) != 5 or header[0] != "CFACE":
            raise ValueError("Malformed face header: " + line)
        vertex_count = int(header[3])
        compression_mpa = float(header[4]) / 1_000_000.0
        gridpoint_ids = []
        points = []

        for _ in range(vertex_count):
            try:
                vertex_line = next(records)
            except StopIteration as error:
                raise ValueError("Transcript ended inside a face") from error
            values = vertex_line.split()
            if len(values) != 5 or values[0] != "CVERT":
                raise ValueError("Malformed vertex record: " + vertex_line)
            gridpoint_ids.append(int(values[1]))
            point = (float(values[2]), float(values[3]), float(values[4]))
            points.append(point)
            for axis, coordinate in enumerate(point):
                coordinate_min[axis] = min(coordinate_min[axis], coordinate)
                coordinate_max[axis] = max(coordinate_max[axis], coordinate)

        raw_face_count += 1
        key = tuple(sorted(gridpoint_ids))
        candidate = Face(tuple(points), compression_mpa)
        existing = faces.get(key)
        if existing is None:
            faces[key] = candidate
        else:
            duplicate_count += 1
            if candidate.compression_mpa > existing.compression_mpa:
                faces[key] = candidate

    raise ValueError("Transcript ended without a surface count")


def is_exterior(points: Tuple[Point, ...], bounds, tolerance=1e-6) -> bool:
    minimum, maximum = bounds
    for axis in range(3):
        for plane in (minimum[axis], maximum[axis]):
            if all(abs(point[axis] - plane) <= tolerance for point in points):
                return True
    return False


def write_assets(
    transcript: str,
    output_dir: str,
    source_name: str,
    source_size_bytes: int,
    source_sha256: str | None,
    source_title: str,
) -> None:
    faces, extraction = parse_faces(transcript)
    bounds = extraction["bounds"]
    roadway = []
    exterior = []
    for face in faces.values():
        target = exterior if is_exterior(face.points, bounds) else roadway
        target.append(face)

    if not roadway:
        raise ValueError("No roadway free surfaces were identified")

    stress_min = min(face.compression_mpa for face in roadway)
    stress_max = max(face.compression_mpa for face in roadway)
    stress_average = sum(
        face.compression_mpa for face in roadway
    ) / len(roadway)
    threshold_multiplier = 1.2
    stress_threshold = stress_average * threshold_multiplier
    high_stress = [
        face for face in roadway
        if face.compression_mpa >= stress_threshold
    ]
    peak_face = max(roadway, key=lambda face: face.compression_mpa)
    if stress_max <= stress_min:
        stress_max = stress_min + 1.0

    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    streams = {
        "roadway": VertexStream("roadway"),
        "exterior": VertexStream("exterior"),
        "high_stress": VertexStream("high_stress"),
    }
    try:
        for kind, face_list in (("roadway", roadway), ("exterior", exterior)):
            stream = streams[kind]
            for face in face_list:
                color = _stress_color(
                    face.compression_mpa, stress_min, stress_max
                )
                for triangle in _triangles(face.points):
                    stream.write_triangle(triangle, color)
            stream.close()
        for face in high_stress:
            for triangle in _triangles(face.points):
                streams["high_stress"].write_triangle(
                    triangle, TARGET_COLOR
                )
        streams["high_stress"].close()

        document = _build_gltf(streams, stress_min, stress_max)
        glb_path = os.path.join(output_dir, "model.glb")
        _write_glb(glb_path, document, streams)

        source = {
            "name": source_name,
            "type": "ITASCA SAVE FILE",
            "product": "FLAC3D",
            "version": "6.0",
            "title": source_title,
            "sizeBytes": source_size_bytes,
        }
        if source_sha256:
            source["sha256"] = source_sha256.upper()

        manifest = {
            "ready": True,
            "source": source,
            "model": {
                "url": "model.glb",
                "coordinateUnit": "m",
                "bounds": bounds,
                "roadwayFaceCount": len(roadway),
                "exteriorFaceCount": len(exterior),
                "roadwayVertexCount": streams["roadway"].count,
                "exteriorVertexCount": streams["exterior"].count,
                "highStressFaceCount": len(high_stress),
                "highStressVertexCount": streams["high_stress"].count,
            },
            "field": {
                "name": "minimum principal stress magnitude",
                "unit": "MPa",
                "range": [stress_min, stress_max],
            },
            "targetIdentification": {
                "method": "roadway face stress >= average stress * 1.2",
                "thresholdMultiplier": threshold_multiplier,
                "averageStressMpa": stress_average,
                "thresholdStressMpa": stress_threshold,
                "peakStressMpa": peak_face.compression_mpa,
                "peakPosition": [
                    sum(point[axis] for point in peak_face.points)
                    / len(peak_face.points)
                    for axis in range(3)
                ],
                "highStressFaceCount": len(high_stress),
                "roadwayFaceRatio": len(high_stress) / len(roadway),
                "bounds": [
                    [
                        min(
                            point[axis]
                            for face in high_stress
                            for point in face.points
                        )
                        for axis in range(3)
                    ],
                    [
                        max(
                            point[axis]
                            for face in high_stress
                            for point in face.points
                        )
                        for axis in range(3)
                    ],
                ],
                "centroid": [
                    sum(
                        point[axis]
                        for face in high_stress
                        for point in face.points
                    ) / sum(len(face.points) for face in high_stress)
                    for axis in range(3)
                ],
            },
            "extraction": extraction,
            "generatedAt": datetime.now().astimezone().isoformat(),
        }
        with open(
            os.path.join(output_dir, "manifest.json"),
            "w",
            encoding="utf-8",
        ) as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)

        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        print("GLB:", glb_path, os.path.getsize(glb_path), "bytes")
    finally:
        for stream in streams.values():
            try:
                stream.close()
            except Exception:
                pass
            stream.remove()


if __name__ == "__main__":
    arguments = parse_args()
    write_assets(
        arguments.transcript,
        arguments.output_dir,
        arguments.source_name,
        arguments.source_size_bytes,
        arguments.source_sha256,
        arguments.source_title,
    )
