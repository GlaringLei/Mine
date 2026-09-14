"""Build the compact Vtest4 annular-borehole dataset used by the Vue dashboard.

The script intentionally reuses the fitting implementation shipped in ``拟合.zip``
(Hampel -> Savitzky-Golay -> PCHIP) instead of inventing a browser-side smoother.
It joins those fitted model curves to the 11 raw Vtest4 borehole CSV files and
writes a depth-aligned JSON payload suitable for real-time Three.js playback.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


MODEL_IDS = {
    "advancedV1_multiscale_extratrees": "v1",
    "advancedV2_cnn_bilstm": "v2",
    "advancedV3_physics_fusion": "v3",
}

SECTION_44_METRICS = {
    "v1": {"damageAccuracy": 0.6973, "stressAccuracy": 0.8371, "stateAccuracy": None, "macroF1": 0.6236},
    "v2": {"damageAccuracy": 0.7300, "stressAccuracy": 0.8519, "stateAccuracy": None, "macroF1": 0.7156},
    "v3": {"damageAccuracy": 0.7997, "stressAccuracy": 0.8991, "stateAccuracy": None, "macroF1": 0.7894},
}

BOREHOLE_ORDER = [
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


def read_zip_csv(archive: zipfile.ZipFile, member: str) -> pd.DataFrame:
    with archive.open(member) as handle:
        return pd.read_csv(handle, low_memory=False)


def read_zip_dicts(archive: zipfile.ZipFile, member: str) -> list[dict[str, str]]:
    with archive.open(member) as handle:
        text = (line.decode("utf-8-sig") for line in handle)
        return list(csv.DictReader(text))


def nearest_rows(frame: pd.DataFrame, depths: np.ndarray) -> pd.DataFrame:
    frame = frame.sort_values("cumulative_depth_cm", kind="stable").drop_duplicates("cumulative_depth_cm")
    source_depths = frame["cumulative_depth_cm"].to_numpy(float)
    right = np.searchsorted(source_depths, depths, side="left")
    right = np.clip(right, 0, len(source_depths) - 1)
    left = np.clip(right - 1, 0, len(source_depths) - 1)
    choose_left = np.abs(depths - source_depths[left]) <= np.abs(source_depths[right] - depths)
    indices = np.where(choose_left, left, right)
    return frame.iloc[indices].reset_index(drop=True)


def interpolated_values(frame: pd.DataFrame, depths: np.ndarray, column: str) -> np.ndarray:
    frame = frame.sort_values("cumulative_depth_cm", kind="stable").drop_duplicates("cumulative_depth_cm")
    x = frame["cumulative_depth_cm"].to_numpy(float)
    y = frame[column].to_numpy(float)
    return np.interp(depths, x, y, left=y[0], right=y[-1])


def finite(value, digits=3):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if np.isfinite(number) else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed", default="processed_dataset_Vtest4.zip")
    parser.add_argument("--fitting", default="拟合.zip")
    parser.add_argument("--output", default="public/data/ring_cloud_v4.json")
    parser.add_argument("--step", type=float, default=0.5)
    args = parser.parse_args()

    root = Path.cwd()
    processed_zip = (root / args.processed).resolve()
    fitting_zip = (root / args.fitting).resolve()
    output_path = (root / args.output).resolve()

    with tempfile.TemporaryDirectory(prefix="data-v-ring-fit-") as temp_name:
        temp_root = Path(temp_name)
        with zipfile.ZipFile(fitting_zip) as archive:
            for member in archive.namelist():
                if (
                    member.startswith("拟合/.git")
                    or member.startswith("拟合/.agents")
                    or member == "拟合/all_model_predictions.csv"
                    or member.startswith("拟合/outputs/")
                ):
                    continue
                archive.extract(member, temp_root)

        # Vtest4 contains S99 while the fitting archive's bundled prediction input
        # belongs to an earlier borehole batch. Apply the fitting implementation to
        # the Vtest4 prediction report so every displayed borehole uses one method.
        prediction_input = temp_root / "vtest4_all_model_predictions.csv"
        with zipfile.ZipFile(processed_zip) as processed:
            with processed.open("reports/all_model_predictions.csv") as source, prediction_input.open("wb") as target:
                shutil.copyfileobj(source, target)

        fit_root = temp_root / "拟合"
        sys.path.insert(0, str(fit_root))
        run_fitting = importlib.import_module("run_fitting")
        with (fit_root / "config.yaml").open(encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        config["input_file"] = str(prediction_input)
        config["output_dir"] = str(temp_root / "fit-output")

        fitted_rows, fit_summary = run_fitting.process(
            config,
            make_plots=False,
            generate_dense=True,
        )
        dense_rows = pd.read_csv(temp_root / "fit-output" / "fitted_curve_dense.csv", low_memory=False)

        model_metrics = []
        with zipfile.ZipFile(processed_zip) as processed:
            overall = read_zip_csv(processed, "reports/overall_metrics.csv")
            inventory = json.loads(processed.read("reports/csv_inventory_summary.json"))
            with zipfile.ZipFile(fitting_zip) as fitting:
                comparison = read_zip_dicts(fitting, "拟合/outputs/fitting/algorithm_comparison_summary.csv")

            for row in overall.to_dict("records"):
                model_id = MODEL_IDS[row["model"]]
                section_metrics = SECTION_44_METRICS[model_id]
                model_metrics.append({
                    "id": model_id,
                    "name": {
                        "v1": "GBDT",
                        "v2": "CNN-LSTM",
                        "v3": "PF-CL-MTIM",
                    }[model_id],
                    "nameEn": {
                        "v1": "GBDT",
                        "v2": "CNN-LSTM",
                        "v3": "PF-CL-MTIM",
                    }[model_id],
                    "damageAccuracy": section_metrics["damageAccuracy"],
                    "stressAccuracy": section_metrics["stressAccuracy"],
                    "stateAccuracy": section_metrics["stateAccuracy"],
                    "macroF1": section_metrics["macroF1"],
                    "confidence": finite(row["mean_state_confidence"], 4),
                })

            depths = np.round(np.arange(0, 125 + args.step / 2, args.step), 3)
            boreholes = []

            for index, source_file in enumerate(BOREHOLE_ORDER):
                raw = read_zip_csv(processed, f"csv_by_stress/{source_file}")
                raw_at_depth = nearest_rows(raw, depths)
                samples = []
                fitted_by_model = {}
                nearest_prediction_by_model = {}

                for model_name, model_id in MODEL_IDS.items():
                    dense = dense_rows[(dense_rows.model == model_name) & (dense_rows.source_file == source_file)]
                    prediction = fitted_rows[(fitted_rows.model == model_name) & (fitted_rows.source_file == source_file)]
                    if dense.empty or prediction.empty:
                        continue
                    fitted_by_model[model_id] = {
                        "damage": interpolated_values(dense, depths, "continuous_damage"),
                        "stress": interpolated_values(dense, depths, "continuous_stress"),
                    }
                    nearest_prediction_by_model[model_id] = nearest_rows(prediction, depths)

                for depth_index, depth in enumerate(depths):
                    row = raw_at_depth.iloc[depth_index]
                    predictions = {}
                    for model_id, curves in fitted_by_model.items():
                        prediction = nearest_prediction_by_model[model_id].iloc[depth_index]
                        predictions[model_id] = {
                            "damage": finite(curves["damage"][depth_index], 2),
                            "stress": finite(curves["stress"][depth_index], 2),
                            "rawDamage": finite(prediction.get("raw_damage"), 0),
                            "rawStress": finite(prediction.get("raw_stress"), 0),
                            "confidence": finite(prediction.get("state_confidence"), 4),
                            "state": prediction.get("pred_state_label") or None,
                            "outlier": bool(prediction.get("damage_outlier", False) or prediction.get("stress_outlier", False)),
                        }
                    samples.append({
                        "depth": finite(depth, 2),
                        "sample": int(row.sample_index),
                        "torque": finite(row.torque_nm, 3),
                        "thrust": finite(row.thrust_kn, 4),
                        "actualDamage": finite(row.true_damage_level, 0),
                        "actualStress": finite(row.true_stress_mpa, 0),
                        "segment": int(row.segment_index),
                        "actualState": row.true_state_label,
                        "predictions": predictions,
                    })

                stress_values = sorted({int(value) for value in raw.true_stress_mpa.dropna().unique()})
                boreholes.append({
                    "id": f"BH-{index + 1:02d}",
                    "sourceFile": source_file,
                    "label": source_file.removeprefix("VTEST_").removesuffix(".csv"),
                    "angleDeg": round(90 - index * (360 / len(BOREHOLE_ORDER)), 3),
                    "role": "special-variable-stress" if source_file == "VTEST_S99.csv" else ("replicate" if "_1" in source_file else "primary"),
                    "stressValues": stress_values,
                    "samples": samples,
                })

    reductions = []
    for row in comparison:
        raw = finite(row.get("raw_roughness_mean"), 6)
        fitted = finite(row.get("fitted_roughness_mean"), 6)
        if raw and fitted is not None:
            reductions.append(1 - fitted / raw)

    fit_groups = fit_summary[fit_summary.source_file.isin(BOREHOLE_ORDER)]
    payload = {
        "meta": {
            "title": "Vtest4 环形钻孔动态反演云图数据",
            "sources": ["processed_dataset_Vtest4.zip", "拟合.zip"],
            "boreholeCount": len(BOREHOLE_ORDER),
            "rawRows": int(sum(item.get("rows", 0) for item in inventory["files"])),
            "depthRangeCm": [0, 125],
            "depthStepCm": args.step,
            "frameCount": int(125 / args.step) + 1,
            "fittingMethod": "Hampel + Savitzky–Golay + PCHIP",
            "fitGroupCount": int(len(fit_groups) / 2),
            "meanRoughnessReduction": finite(np.mean(reductions), 4),
            "coordinateConvention": {
                "tunnelAxis": "X",
                "boreholeAxis": "radial in the YZ cross-section, perpendicular to X",
                "drillingDepth": "from tunnel wall outward along the ring radius",
            },
            "reliefModel": {
                "available": False,
                "reason": "No file, field, or model metadata explicitly identifies pressure-relief/卸压/泄压 data.",
                "specialDataset": "VTEST_S99.csv",
                "specialMeaning": "Variable-stress composite borehole (10–40 MPa); visualized separately but not labelled as a relief model.",
            },
            "models": model_metrics,
        },
        "boreholes": boreholes,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {output_path} ({len(boreholes)} boreholes x {len(depths)} frames)")


if __name__ == "__main__":
    main()
