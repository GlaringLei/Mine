"""Build a compact browser dataset from FLAC3D high-stress zone output."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import tempfile
from datetime import datetime

from build_xieyaqian_glb import is_exterior, parse_faces


CURSOR_FORWARD = re.compile(r"\x1b\[(\d*)C")
ANSI_SEQUENCE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
RECORD = struct.Struct("<ffff")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "transcript",
        nargs="?",
        default=r".codex-tools\sav\high_stress_zones.out",
    )
    parser.add_argument(
        "--output-dir",
        default=r"public\models\xieyaqian",
    )
    parser.add_argument(
        "--surface-transcript",
        default=r".codex-tools\sav\surface_extract_full.out",
    )
    parser.add_argument(
        "--max-roadway-distance",
        type=float,
        default=5.0,
        help="Maximum cross-section distance from the roadway surface in metres.",
    )
    return parser.parse_args()


def clean_line(raw_line: str) -> str:
    line = CURSOR_FORWARD.sub(
        lambda match: " " * int(match.group(1) or "1"),
        raw_line,
    )
    return ANSI_SEQUENCE.sub("", line).replace("\x08", "").strip()


def load_roadway_outline(surface_transcript: str):
    faces, extraction = parse_faces(surface_transcript)
    roadway_faces = [
        face
        for face in faces.values()
        if not is_exterior(face.points, extraction["bounds"])
    ]
    if not roadway_faces:
        raise ValueError("No roadway faces found in surface transcript")
    return sorted(
        {
            (point[0], point[2])
            for face in roadway_faces
            for point in face.points
        }
    )


def build_volume(
    transcript: str,
    output_dir: str,
    surface_transcript: str,
    max_roadway_distance: float,
) -> None:
    if max_roadway_distance <= 0:
        raise ValueError("Maximum roadway distance must be greater than zero")

    roadway_outline = load_roadway_outline(surface_transcript)
    maximum_distance_squared = max_roadway_distance * max_roadway_distance
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "manifest.json")
    volume_path = os.path.join(output_dir, "high-stress-zones.bin")

    with open(manifest_path, "r", encoding="utf-8") as source:
        manifest = json.load(source)

    active_count = None
    average_pa = None
    threshold_pa = None
    declared_count = None
    candidate_count = 0
    count = 0
    stress_min_mpa = math.inf
    stress_max_mpa = -math.inf
    minimum = [math.inf, math.inf, math.inf]
    maximum = [-math.inf, -math.inf, -math.inf]
    coordinate_sum = [0.0, 0.0, 0.0]
    peak_position = [0.0, 0.0, 0.0]
    started = False

    descriptor, temporary_path = tempfile.mkstemp(
        prefix="high-stress-zones-",
        suffix=".bin",
        dir=output_dir,
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            with open(
                transcript,
                "r",
                encoding="utf-8",
                errors="replace",
                newline=None,
            ) as source:
                for raw_line in source:
                    line = clean_line(raw_line)
                    marker = line.find("CODEX_HIGH_STRESS_BEGIN")
                    if marker >= 0:
                        values = line[marker:].split()
                        if len(values) != 4:
                            raise ValueError("Malformed high-stress header: " + line)
                        active_count = int(values[1])
                        average_pa = float(values[2])
                        threshold_pa = float(values[3])
                        started = True
                        continue
                    if not started:
                        continue
                    if line.startswith("CODEX_HIGH_STRESS_END"):
                        values = line.split()
                        declared_count = int(values[1])
                        break
                    if not line.startswith("CZONE "):
                        continue

                    values = line.split()
                    if len(values) != 6:
                        raise ValueError("Malformed zone record: " + line)
                    coordinates = [float(value) for value in values[2:5]]
                    candidate_count += 1
                    distance_squared = min(
                        (coordinates[0] - outline_x) ** 2
                        + (coordinates[2] - outline_z) ** 2
                        for outline_x, outline_z in roadway_outline
                    )
                    if distance_squared > maximum_distance_squared:
                        continue
                    stress_mpa = float(values[5]) / 1_000_000.0
                    output.write(RECORD.pack(*coordinates, stress_mpa))
                    count += 1

                    for axis, coordinate in enumerate(coordinates):
                        minimum[axis] = min(minimum[axis], coordinate)
                        maximum[axis] = max(maximum[axis], coordinate)
                        coordinate_sum[axis] += coordinate
                    if stress_mpa > stress_max_mpa:
                        stress_max_mpa = stress_mpa
                        peak_position = coordinates
                    stress_min_mpa = min(stress_min_mpa, stress_mpa)

        if not started:
            raise ValueError("Transcript does not contain CODEX_HIGH_STRESS_BEGIN")
        if declared_count is None:
            raise ValueError("Transcript does not contain CODEX_HIGH_STRESS_END")
        if candidate_count != declared_count:
            raise ValueError(
                "Declared zone count {0} differs from parsed count {1}".format(
                    declared_count, candidate_count
                )
            )
        if count == 0:
            raise ValueError("No high-stress zones were exported")

        os.replace(temporary_path, volume_path)
        temporary_path = ""

        average_mpa = average_pa / 1_000_000.0
        threshold_mpa = threshold_pa / 1_000_000.0
        target = manifest.setdefault("targetIdentification", {})
        target.update(
            {
                "method": "active zone stress >= average active-zone stress * 1.2",
                "source": "FLAC3D active zone centers",
                "thresholdMultiplier": 1.2,
                "averageStressMpa": average_mpa,
                "thresholdStressMpa": threshold_mpa,
                "peakStressMpa": stress_max_mpa,
                "peakPosition": peak_position,
                "activeZoneCount": active_count,
                "candidateHighStressZoneCount": candidate_count,
                "highStressZoneCount": count,
                "activeZoneRatio": count / max(active_count, 1),
                "roadwayInfluenceDistanceM": max_roadway_distance,
                "selection": (
                    "stress threshold and cross-section distance "
                    "to roadway surface"
                ),
                "bounds": [minimum, maximum],
                "centroid": [
                    coordinate_sum[axis] / count for axis in range(3)
                ],
                "volumeUrl": "high-stress-zones.bin",
                "volumeEncoding": "float32-le: x,y,z,stressMpa",
                "volumeRecordBytes": RECORD.size,
                "volumeStressRangeMpa": [
                    stress_min_mpa,
                    stress_max_mpa,
                ],
            }
        )
        for obsolete_key in ("highStressFaceCount", "roadwayFaceRatio"):
            target.pop(obsolete_key, None)

        model = manifest.setdefault("model", {})
        model["activeZoneCount"] = active_count
        model["highStressZoneCount"] = count
        model.pop("highStressFaceCount", None)
        model.pop("highStressVertexCount", None)
        manifest["generatedAt"] = datetime.now().astimezone().isoformat()

        with open(manifest_path, "w", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)

        print(
            "Built {0:,} target zones from {1:,} high-stress candidates "
            "({2:.2f}% of {3:,} active zones)".format(
                count,
                candidate_count,
                count / max(active_count, 1) * 100.0,
                active_count,
            )
        )
        print(
            "Roadway influence distance: <= {0:.2f} m".format(
                max_roadway_distance
            )
        )
        print(
            "Stress: average {0:.3f} MPa, threshold {1:.3f} MPa, peak {2:.3f} MPa".format(
                average_mpa,
                threshold_mpa,
                stress_max_mpa,
            )
        )
        print("Volume:", volume_path, os.path.getsize(volume_path), "bytes")
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


if __name__ == "__main__":
    arguments = parse_args()
    build_volume(
        arguments.transcript,
        arguments.output_dir,
        arguments.surface_transcript,
        arguments.max_roadway_distance,
    )
