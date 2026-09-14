"""Condense the three inversion archives into three measured roadway sections."""

from __future__ import annotations

import csv
import json
import os
import zipfile
from collections import defaultdict


ARCHIVES = [
    ("A", "ablation_2runs_20260821.zip", -8.0),
    ("B", "ablation_2runs_20260821_b.zip", 0.0),
    ("C", "ablation_2runs_20260821_c.zip", 8.0),
]
SOURCE_ORDER = [
    "VTEST_S00.csv",
    "VTEST_S10.csv",
    "VTEST_S20.csv",
    "VTEST_S30.csv",
    "VTEST_S40.csv",
    "VTEST_S99.csv",
    "VTEST_S40_1.csv",
    "VTEST_S30_1.csv",
    "VTEST_S20_1.csv",
    "VTEST_S10_1.csv",
    "VTEST_S00_1.csv",
]
MODEL_NAME = "V3-Full"
DEPTH_STEP_CM = 2.5


def prediction_entry(archive: zipfile.ZipFile) -> str:
    matches = [
        name
        for name in archive.namelist()
        if name.endswith("inversion/v4/reports/all_model_predictions.csv")
    ]
    if len(matches) != 1:
        raise ValueError("Expected one V4 prediction table")
    return matches[0]


def overall_metrics_entry(archive: zipfile.ZipFile) -> str:
    matches = [
        name
        for name in archive.namelist()
        if name.endswith("inversion/v4/reports/overall_metrics.csv")
    ]
    if len(matches) != 1:
        raise ValueError("Expected one V4 overall metrics table")
    return matches[0]


def rounded(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def build_group(group_id: str, archive_path: str, longitudinal_m: float) -> dict:
    buckets = defaultdict(lambda: defaultdict(lambda: {
        "count": 0,
        "stress": 0.0,
        "damage": 0.0,
        "confidence": 0.0,
        "confidenceCount": 0,
        "trueStress": 0.0,
        "trueDamage": 0.0,
    }))
    metrics = None
    with zipfile.ZipFile(archive_path) as archive:
        entry = prediction_entry(archive)
        rows = (
            line.decode("utf-8-sig")
            for line in archive.open(entry)
        )
        for row in csv.DictReader(rows):
            if row["model"] != MODEL_NAME:
                continue
            source_file = row["source_file"]
            if source_file not in SOURCE_ORDER:
                continue
            depth = float(row["cumulative_depth_cm"])
            depth_bin = int(round(depth / DEPTH_STEP_CM))
            item = buckets[source_file][depth_bin]
            item["count"] += 1
            item["stress"] += float(row["pred_stress_mpa"])
            item["damage"] += float(row["pred_damage_level"])
            if row["state_confidence"]:
                item["confidence"] += float(row["state_confidence"])
                item["confidenceCount"] += 1
            item["trueStress"] += float(row["true_stress_mpa"])
            item["trueDamage"] += float(row["true_damage_level"])

        metric_rows = (
            line.decode("utf-8-sig")
            for line in archive.open(overall_metrics_entry(archive))
        )
        metric_row = next(
            (row for row in csv.DictReader(metric_rows) if row["model"] == MODEL_NAME),
            None,
        )
        if metric_row:
            metrics = {
                "damageAccuracy": rounded(metric_row["damage_accuracy"], 4),
                "stressAccuracy": rounded(metric_row["stress_accuracy"], 4),
                "stateMacroF1": rounded(metric_row["state_head_macro_f1"], 4),
                "stateAccuracy": rounded(metric_row["state_head_accuracy"], 4),
                "meanConfidence": rounded(metric_row["mean_state_confidence"], 4),
            }

    boreholes = []
    for index, source_file in enumerate(SOURCE_ORDER):
        samples = []
        for depth_bin, values in sorted(buckets[source_file].items()):
            count = values["count"]
            samples.append({
                "depthCm": rounded(depth_bin * DEPTH_STEP_CM, 1),
                "stressMpa": rounded(values["stress"] / count),
                "damagePct": rounded(values["damage"] / count),
                "confidence": rounded(
                    values["confidence"] / max(values["confidenceCount"], 1), 4
                ),
                "trueStressMpa": rounded(values["trueStress"] / count),
                "trueDamagePct": rounded(values["trueDamage"] / count),
            })
        boreholes.append({
            "id": f"{group_id}-BH-{index + 1:02d}",
            "sourceFile": source_file,
            "surfaceIndex": index,
            "samples": samples,
        })

    return {
        "id": group_id,
        "label": f"{group_id} 组",
        "archive": os.path.basename(archive_path),
        "model": MODEL_NAME,
        "metrics": metrics,
        "longitudinalM": longitudinal_m,
        "boreholeCount": len(boreholes),
        "boreholes": boreholes,
    }


def main() -> None:
    groups = [
        build_group(group_id, archive_path, longitudinal_m)
        for group_id, archive_path, longitudinal_m in ARCHIVES
    ]
    payload = {
        "meta": {
            "title": "三断面十一孔巷道空间反演场",
            "geometry": "arched roadway extruded along longitudinal X axis",
            "interpretation": (
                "A/B/C are independent measured inversion sections; "
                "intermediate sections are spatial interpolation, not time slices."
            ),
            "groupCount": len(groups),
            "boreholesPerGroup": 11,
            "longitudinalRangeM": [-8.0, 8.0],
            "depthRangeCm": [0.0, 125.0],
            "depthStepCm": DEPTH_STEP_CM,
            "model": MODEL_NAME,
            "inversionVersion": "V4",
        },
        "groups": groups,
    }
    output_path = os.path.join("public", "data", "roadway_spatial_v4.json")
    with open(output_path, "w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))
    print(output_path, os.path.getsize(output_path), "bytes")


if __name__ == "__main__":
    main()
