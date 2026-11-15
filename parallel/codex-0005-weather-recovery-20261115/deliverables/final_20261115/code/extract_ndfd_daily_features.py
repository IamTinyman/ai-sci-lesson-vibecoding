from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


PROJECT = Path("/root/autodl-tmp/ai-sci")
TASK = PROJECT / "parallel/codex-0005-weather-recovery-20261115"
RAW = PROJECT / "data/raw/ndfd/residual_snow_study/grib2"
MANIFEST = TASK / "results/final_20261115/ndfd_forecast_manifest.csv"
OUT = TASK / "data/final_20261115/ndfd_daily_forecasts.csv"
SUMMARY = TASK / "results/final_20261115/ndfd_feature_summary.json"
ORD_LAT = 41.9952
ORD_LON = -87.9331
LOCAL_TZ = "America/Chicago"


def grib_values(target_date: str, product: str) -> tuple[np.ndarray, np.ndarray, tuple[float, float], dict]:
    path = RAW / target_date.replace("-", "") / f"{product}.grib2"
    dataset = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    variable = next(iter(dataset.data_vars))
    latitude = np.asarray(dataset.latitude.values)
    longitude = ((np.asarray(dataset.longitude.values) + 180) % 360) - 180
    distance = (latitude - ORD_LAT) ** 2 + (np.cos(np.deg2rad(ORD_LAT)) * (longitude - ORD_LON)) ** 2
    y_index, x_index = np.unravel_index(np.nanargmin(distance), distance.shape)
    field = np.asarray(dataset[variable].values)
    point_values = np.asarray(field[..., y_index, x_index], dtype=float).reshape(-1)
    valid_times = pd.to_datetime(np.asarray(dataset.valid_time.values).reshape(-1), utc=True)
    metadata = {
        "path": str(path),
        "source_time_utc": str(dataset.time.values),
        "variable": variable,
        "attributes": dataset[variable].attrs,
        "nearest_grid_point": [float(latitude[y_index, x_index]), float(longitude[y_index, x_index])],
        "shape": list(field.shape),
    }
    dataset.close()
    return point_values, valid_times, (float(latitude[y_index, x_index]), float(longitude[y_index, x_index])), metadata


def daily_target_bounds(target_date: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_local = pd.Timestamp(target_date, tz=LOCAL_TZ)
    end_local = start_local + pd.Timedelta(days=1)
    return start_local.tz_convert("UTC"), end_local.tz_convert("UTC")


def main() -> None:
    manifest = pd.read_csv(MANIFEST).fillna("")
    rows = []
    audit = {}
    usable = manifest[manifest["status"].eq("downloaded_or_cached")].copy()
    for index, (target_date, group) in enumerate(usable.groupby("target_date", sort=True), start=1):
        start_utc, end_utc = daily_target_bounds(target_date)
        record = {"date": target_date}
        for product, expected_code in [("temp", "YEUZ88"), ("qpf", "YIUZ88"), ("snow", "YSUZ88")]:
            entries = group[group["product"].eq(product)]
            if entries.empty:
                continue
            entry = entries.iloc[0]
            values, valid_times, grid, metadata = grib_values(target_date, product)
            if target_date not in audit:
                audit[target_date] = {}
            audit[target_date][product] = {
                "key": entry["key"],
                "issue_utc": entry["issue_utc"],
                "sha256": entry["sha256"],
                "grib": metadata,
            }
            if product == "temp":
                mask = (valid_times >= start_utc) & (valid_times < end_utc)
                valid = values[mask]
                valid = valid[np.isfinite(valid) & (valid >= 230) & (valid <= 330)]
                if len(valid):
                    record["forecast_tmean_c"] = float(np.mean(valid) - 273.15)
                    record["forecast_tmin_c"] = float(np.min(valid) - 273.15)
                    record["forecast_tmax_c"] = float(np.max(valid) - 273.15)
                    record["forecast_temp_steps"] = int(len(valid))
            elif product == "qpf":
                mask = (valid_times > start_utc) & (valid_times <= end_utc)
                valid = values[mask]
                valid = valid[np.isfinite(valid) & (valid >= 0) & (valid <= 500)]
                if len(valid):
                    # The NDFD local GRIB table stores QPF as kg m-2, numerically equal to mm water.
                    record["forecast_qpf_mm"] = float(np.sum(valid))
                    record["forecast_qpf_periods"] = int(len(valid))
            else:
                mask = (valid_times > start_utc) & (valid_times <= end_utc)
                valid = values[mask]
                valid = valid[np.isfinite(valid) & (valid >= 0) & (valid <= 2)]
                if len(valid):
                    # The NDFD local GRIB table stores snowfall amount in meters.
                    record["forecast_snow_cm"] = float(np.sum(valid) * 100)
                    record["forecast_snow_periods"] = int(len(valid))
                record["forecast_grid_lat"] = grid[0]
                record["forecast_grid_lon"] = grid[1]
        rows.append(record)
        if index % 25 == 0:
            print(f"Extracted forecast fields for {index}/{usable['target_date'].nunique()} target dates", flush=True)

    frame = pd.DataFrame(rows).sort_values("date")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)
    complete = frame.dropna(subset=["forecast_tmean_c", "forecast_qpf_mm", "forecast_snow_cm"])
    summary = {
        "manifest_rows": len(manifest),
        "usable_product_files": len(usable),
        "dates_with_any_forecast": len(frame),
        "dates_with_all_three_daily_products": len(complete),
        "daily_forecast_csv": str(OUT),
        "feature_units": {
            "forecast_tmean_c": "degrees Celsius, converted from GRIB 2-m air temperature in kelvin",
            "forecast_qpf_mm": "mm liquid equivalent, NDFD six-hour QPF values in kg m-2 summed over local calendar day",
            "forecast_snow_cm": "cm snowfall amount, NDFD six-hour snow-amount values in meters summed over local calendar day",
        },
        "target_day_definition": "00:00 through 23:59 America/Chicago; forecast issue is no later than noon local time on the prior day",
        "valid_step_counts": {
            "temperature": frame.get("forecast_temp_steps", pd.Series(dtype=float)).value_counts(dropna=False).to_dict(),
            "qpf": frame.get("forecast_qpf_periods", pd.Series(dtype=float)).value_counts(dropna=False).to_dict(),
            "snow": frame.get("forecast_snow_periods", pd.Series(dtype=float)).value_counts(dropna=False).to_dict(),
        },
        "audit_examples": {key: value for key, value in list(audit.items())[:3]},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "audit_examples"}, ensure_ascii=False, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
