from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler


PROJECT = Path("/root/autodl-tmp/ai-sci")
TASK = PROJECT / "parallel/codex-0005-weather-recovery-20261115"
RAW = PROJECT / "data/raw"
OUT = TASK / "results/final_20261115"
FIG = TASK / "figures/final_20261115"
PROC = TASK / "data/final_20261115"
TRIP_ROOT = RAW / "divvy"
NOAA_ROOT = RAW / "noaa"
WINTERS = [2022, 2023, 2024, 2025]
MONTHS = {
    "202112", "202201", "202202", "202203",
    "202212", "202301", "202302", "202303",
    "202312", "202401", "202402", "202403",
    "202412", "202501", "202502", "202503",
}
WEATHER_COLUMNS = ["PRCP", "SNOW", "SNWD", "AWND", "TMAX", "TMIN"]
TARGETS = ["rides", "member", "casual"]
SEED = 20261115

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.labelcolor": "#34423d",
    "text.color": "#1c2e29",
    "xtick.color": "#4f5d58",
    "ytick.color": "#4f5d58",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def season_dates() -> pd.DatetimeIndex:
    dates = []
    for winter in WINTERS:
        dates.extend(pd.date_range(f"{winter - 1}-12-01", f"{winter}-03-31", freq="D"))
    return pd.DatetimeIndex(dates, name="date")


def read_trips() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    daily_parts = []
    station_parts = []
    coordinate_parts = []
    manifest = []
    cleaning = Counter()
    files = sorted(path for path in TRIP_ROOT.rglob("*.zip") if path.name[:6] in MONTHS)
    if len(files) != len(MONTHS):
        found = {path.name[:6] for path in files}
        raise RuntimeError(f"Expected {len(MONTHS)} monthly Divvy files, found {len(files)}: {sorted(found)}")

    for path in files:
        file_rows = 0
        file_kept = 0
        file_duplicates = 0
        min_date = None
        max_date = None
        seen_ride_ids: set[str] = set()
        with zipfile.ZipFile(path) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv") and not name.startswith("__MACOSX")]
            if len(csv_names) != 1:
                raise RuntimeError(f"Expected one CSV in {path.name}, found {csv_names}")
            with archive.open(csv_names[0]) as stream:
                header = pd.read_csv(stream, nrows=0).columns.tolist()
            required = [
                "ride_id", "started_at", "start_station_id", "start_station_name",
                "member_casual", "start_lat", "start_lng",
            ]
            usecols = [column for column in required if column in header]
            with archive.open(csv_names[0]) as stream:
                for chunk in pd.read_csv(stream, usecols=usecols, chunksize=150_000, low_memory=False,
                                         dtype={"start_station_id": "string", "start_station_name": "string", "member_casual": "string"}):
                    file_rows += len(chunk)
                    cleaning["input_rows"] += len(chunk)
                    chunk["date"] = pd.to_datetime(chunk["started_at"], errors="coerce").dt.tz_localize(None).dt.floor("D")
                    invalid_date = chunk["date"].isna()
                    cleaning["invalid_start_time"] += int(invalid_date.sum())
                    in_window = chunk["date"].isin(season_dates())
                    cleaning["rows_outside_winter_window"] += int((~invalid_date & ~in_window).sum())
                    chunk = chunk[~invalid_date & in_window].copy()
                    chunk["user"] = chunk.get("member_casual", pd.Series("unknown", index=chunk.index)).astype("string").str.strip().str.lower()
                    chunk.loc[~chunk["user"].isin(["member", "casual"]), "user"] = "unknown"
                    if "ride_id" in chunk.columns:
                        ride_ids = chunk["ride_id"].astype("string")
                        duplicate = ride_ids.notna() & (ride_ids.duplicated(keep="first") | ride_ids.isin(seen_ride_ids))
                        file_duplicates += int(duplicate.sum())
                        seen_ride_ids.update(ride_ids.loc[ride_ids.notna() & ~duplicate].astype(str).tolist())
                        chunk = chunk[~duplicate].copy()
                    file_kept += len(chunk)
                    if not chunk.empty:
                        lo, hi = chunk["date"].min(), chunk["date"].max()
                        min_date = lo if min_date is None else min(min_date, lo)
                        max_date = hi if max_date is None else max(max_date, hi)

                    city = chunk.groupby(["date", "user"], observed=True).size().unstack(fill_value=0)
                    daily_parts.append(city)

                    if "start_station_id" not in chunk.columns:
                        chunk["start_station_id"] = pd.NA
                    if "start_station_name" not in chunk.columns:
                        chunk["start_station_name"] = pd.NA
                    sid = chunk["start_station_id"].astype("string").str.strip()
                    sname = chunk["start_station_name"].astype("string").str.strip()
                    has_id = sid.notna() & sid.ne("")
                    has_name = sname.notna() & sname.ne("")
                    chunk["station_id"] = np.where(has_id, "id:" + sid.fillna(""), "name:" + sname.fillna(""))
                    chunk.loc[~has_id & ~has_name, "station_id"] = pd.NA
                    chunk["station_name"] = sname
                    valid_station = chunk["station_id"].notna()
                    cleaning["rows_without_station"] += int((~valid_station).sum())
                    station_chunk = chunk[valid_station].copy()
                    station = station_chunk.groupby(["date", "station_id", "user"], observed=True).size().unstack(fill_value=0)
                    station_parts.append(station)
                    if {"start_lat", "start_lng"}.issubset(station_chunk.columns):
                        station_chunk["lat"] = pd.to_numeric(station_chunk["start_lat"], errors="coerce")
                        station_chunk["lon"] = pd.to_numeric(station_chunk["start_lng"], errors="coerce")
                        coordinates = station_chunk.dropna(subset=["lat", "lon"]).groupby("station_id", observed=True).agg(
                            lat_sum=("lat", "sum"), lon_sum=("lon", "sum"), coordinate_n=("lat", "size")
                        )
                        coordinate_parts.append(coordinates)
                    if not station_chunk.empty:
                        names = station_chunk.groupby(["station_id", "station_name"], dropna=True).size().rename("n").reset_index()
                        coordinate_parts.append(names.set_index(["station_id", "station_name"]))
        cleaning["duplicate_ride_ids_removed"] += file_duplicates
        cleaning["clean_rows"] += file_kept
        manifest.append({
            "file": str(path), "bytes": path.stat().st_size, "sha256": sha256(path),
            "input_rows": file_rows, "clean_rows": file_kept, "duplicate_ride_ids_removed": file_duplicates,
            "first_trip_date": min_date, "last_trip_date": max_date,
        })
        print(f"Read {path.name}: {file_kept:,} seasonal rides", flush=True)

    city = pd.concat(daily_parts).groupby(level=0).sum().reindex(columns=["member", "casual", "unknown"], fill_value=0)
    city = city.reindex(season_dates(), fill_value=0).rename_axis("date").reset_index()
    city["rides"] = city[["member", "casual", "unknown"]].sum(axis=1)
    city["winter"] = np.where(city["date"].dt.month == 12, city["date"].dt.year + 1, city["date"].dt.year)

    station = pd.concat(station_parts).groupby(level=[0, 1]).sum().reindex(columns=["member", "casual", "unknown"], fill_value=0)
    station = station.rename_axis(index=["date", "station_id"]).reset_index()
    station["rides"] = station[["member", "casual", "unknown"]].sum(axis=1)
    station["winter"] = np.where(station["date"].dt.month == 12, station["date"].dt.year + 1, station["date"].dt.year)

    coords = pd.concat([part for part in coordinate_parts if "lat_sum" in part.columns], axis=0).groupby(level=0).sum()
    coords["lat"] = coords["lat_sum"] / coords["coordinate_n"]
    coords["lon"] = coords["lon_sum"] / coords["coordinate_n"]
    coords = coords[["lat", "lon"]]
    if any("station_name" in part.index.names for part in coordinate_parts):
        name_parts = [part for part in coordinate_parts if "station_name" in part.index.names]
        name_counts = pd.concat(name_parts).groupby(level=[0, 1]).sum(numeric_only=True).reset_index()
        idx = name_counts.groupby("station_id")["n"].idxmax()
        names = name_counts.loc[idx, ["station_id", "station_name"]].set_index("station_id")
        coords = coords.join(names, how="outer")
    coords = coords.reset_index()
    write_json(OUT / "trip_cleaning_summary.json", dict(cleaning))
    pd.DataFrame(manifest).to_csv(OUT / "trip_file_manifest.csv", index=False)
    return city, station, coords, dict(cleaning)


def load_weather() -> tuple[pd.DataFrame, dict]:
    files = sorted(NOAA_ROOT.glob("USW00094846*.csv"))
    if not files:
        raise FileNotFoundError(f"No O'Hare Daily Summaries found under {NOAA_ROOT}")
    frames = []
    for path in files:
        frame = pd.read_csv(path, low_memory=False)
        if "DATE" not in frame:
            continue
        keep = [name for name in ["DATE", "STATION", *WEATHER_COLUMNS, *[f"{x}_ATTRIBUTES" for x in WEATHER_COLUMNS]] if name in frame]
        frame = frame[keep].copy()
        frame["date"] = pd.to_datetime(frame["DATE"], errors="coerce").dt.floor("D")
        for field in WEATHER_COLUMNS:
            if field not in frame:
                frame[field] = np.nan
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
            frame.loc[frame[field].isin([-9999, -999, 9999]), field] = np.nan
        frame["source_file"] = path.name
        frame["source_sha256"] = sha256(path)
        frames.append(frame)
    weather_all = pd.concat(frames, ignore_index=True)
    seasonal_dates = set(season_dates())
    weather_all = weather_all[weather_all["date"].isin(seasonal_dates)].copy()
    weather_all["nonnull_fields"] = weather_all[WEATHER_COLUMNS].notna().sum(axis=1)
    weather = weather_all.sort_values(["date", "nonnull_fields", "source_file"]).drop_duplicates("date", keep="last")
    weather = weather.set_index("date").reindex(season_dates()).rename_axis("date").reset_index()
    missing_days = weather[WEATHER_COLUMNS].isna().all(axis=1)
    if missing_days.any():
        dates = weather.loc[missing_days, "date"].dt.strftime("%Y-%m-%d").tolist()
        raise RuntimeError(f"Missing NOAA records on {len(dates)} study dates: {dates[:12]}")
    summary = {
        "files": [{"name": p.name, "sha256": sha256(p), "bytes": p.stat().st_size} for p in files],
        "study_days": len(weather),
        "duplicate_date_rows": int(len(weather_all) - weather_all["date"].nunique()),
        "missing_by_field": weather[WEATHER_COLUMNS].isna().sum().astype(int).to_dict(),
        "coverage_start": weather["date"].min().date().isoformat(),
        "coverage_end": weather["date"].max().date().isoformat(),
    }
    return weather, summary


def build_panel() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    import holidays

    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)
    city, station, metadata, cleaning = read_trips()
    weather, weather_summary = load_weather()
    city["date"] = pd.to_datetime(city["date"])
    station["date"] = pd.to_datetime(station["date"])
    city = city.merge(weather[["date", *WEATHER_COLUMNS]], on="date", how="left", validate="one_to_one")
    city["tmean_c"] = (city["TMAX"] + city["TMIN"]) / 2
    city["dow"] = city["date"].dt.day_of_week
    city["month"] = city["date"].dt.month
    city["winter"] = np.where(city["month"] == 12, city["date"].dt.year + 1, city["date"].dt.year)
    us_holidays = holidays.US(years=range(2021, 2026))
    city["is_holiday"] = city["date"].dt.date.map(lambda day: day in us_holidays)
    city["new_snow_day"] = city["SNOW"].ge(1.0)
    city["residual_snow_cm"] = city["SNWD"] / 10.0
    city["dry_clear"] = city[["PRCP", "SNOW", "SNWD"]].notna().all(axis=1) & city["PRCP"].lt(1.0) & city["SNOW"].lt(1.0) & city["SNWD"].eq(0.0)
    city.to_csv(PROC / "city_daily.csv", index=False)
    station.to_csv(PROC / "station_daily.csv", index=False)
    metadata.to_csv(PROC / "station_metadata.csv", index=False)
    weather.to_csv(PROC / "noaa_daily_winter.csv", index=False)
    write_json(OUT / "weather_coverage_summary.json", weather_summary)
    write_json(OUT / "data_cleaning_summary.json", {
        **cleaning,
        "daily_records": len(city),
        "station_day_records": len(station),
        "stations_with_trip_records": int(station["station_id"].nunique()),
        "study_dates": len(season_dates()),
        "winter_day_counts": city.groupby("winter").size().astype(int).to_dict(),
        "month_files_expected": len(MONTHS),
        "month_files_used": len(MONTHS),
        "analysis_month_files": len(MONTHS),
        "analysis_window": "December 1 through March 31, winters 2021-22 to 2024-25",
        "dropped_2025_26_boundary_file": "202601-divvy-tripdata.zip",
    })
    return city, station, metadata


def snow_events(city: pd.DataFrame, minimum_snow_mm: float = 10.0) -> pd.DataFrame:
    days = city[city["SNOW"].notna() & city["SNOW"].ge(1.0)].sort_values("date")
    if days.empty:
        return pd.DataFrame()
    gaps = days["date"].diff().dt.days.fillna(1)
    groups = gaps.gt(2).cumsum()
    rows = []
    for idx, block in days.groupby(groups):
        start, end = block["date"].min(), block["date"].max()
        if float(block["SNOW"].sum()) < minimum_snow_mm:
            continue
        rows.append({
            "event_id": f"snow_{end:%Y%m%d}",
            "winter": int(block["winter"].iloc[0]),
            "start": start,
            "end": end,
            "duration_snow_days": int(len(block)),
            "snow_total_mm": float(block["SNOW"].sum()),
            "snow_peak_mm": float(block["SNOW"].max()),
            "depth_peak_cm": float(block["SNWD"].max() / 10) if block["SNWD"].notna().any() else np.nan,
            "depth_end_cm": float(block["SNWD"].iloc[-1] / 10) if pd.notna(block["SNWD"].iloc[-1]) else np.nan,
        })
    return pd.DataFrame(rows)


def event_control_dates(city: pd.DataFrame, event_day: pd.Series, event_windows: list[tuple[pd.Timestamp, pd.Timestamp]]) -> tuple[list[pd.Timestamp], int, float]:
    candidate = city[
        city["winter"].eq(event_day["winter"])
        & city["dow"].eq(event_day["dow"])
        & city["is_holiday"].eq(event_day["is_holiday"])
        & city["dry_clear"]
        & city["tmean_c"].notna()
    ].copy()
    date_blocked = pd.Series(False, index=candidate.index)
    for start, end in event_windows:
        date_blocked |= candidate["date"].between(start - pd.Timedelta(days=7), end + pd.Timedelta(days=7))
    candidate = candidate[~date_blocked]
    temp_gap = (candidate["tmean_c"] - float(event_day["tmean_c"])).abs()
    radius = 5.0
    close = candidate[temp_gap.le(radius)]
    if len(close) < 3:
        radius = 8.0
        close = candidate[temp_gap.le(radius)]
    if len(close) < 3:
        return [], 0, radius
    close = close.assign(_temp_gap=(close["tmean_c"] - float(event_day["tmean_c"])).abs())
    close = close.sort_values(["_temp_gap", "date"]).head(5)
    return close["date"].tolist(), len(close), radius


def matched_recovery(city: pd.DataFrame, station: pd.DataFrame, metadata: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if events.empty:
        raise RuntimeError("No snow event passed the pre-registered 10 mm event threshold")
    event_windows = [(row.start, row.end) for row in events.itertuples(index=False)]
    city_by_date = city.set_index("date")
    station_index = station.set_index(["date", "station_id"])
    winter_activity = station.groupby(["station_id", "winter"])["rides"].sum().unstack(fill_value=0)
    active_years = winter_activity.gt(0).sum(axis=1)
    all_season_rides = winter_activity.sum(axis=1)
    eligible_stations = active_years[active_years.ge(2) & all_season_rides.ge(250)].index
    eligible_stations = pd.Index(eligible_stations, name="station_id")
    city_rows = []
    station_rows = []
    match_rows = []
    for event in events.itertuples(index=False):
        next_start = events.loc[events["start"].gt(event.end), "start"].min()
        max_h = 7 if pd.isna(next_start) else min(7, int((next_start - event.end).days) - 1)
        if max_h < 1:
            continue
        for h in range(1, max_h + 1):
            day_date = event.end + pd.Timedelta(days=h)
            day = city_by_date.loc[day_date]
            if bool(day["new_snow_day"]):
                continue
            controls, control_n, radius = event_control_dates(city, day, event_windows)
            if control_n < 3:
                continue
            control_rows = city_by_date.loc[controls]
            city_record = {
                "event_id": event.event_id,
                "winter": event.winter,
                "date": day_date,
                "h": h,
                "residual_snow_cm": day["residual_snow_cm"],
                "snowpack_state": "present" if day["residual_snow_cm"] > 0 else "absent",
                "tmean_c": day["tmean_c"],
                "PRCP": day["PRCP"],
                "AWND": day["AWND"],
                "is_holiday": day["is_holiday"],
                "dow": day["dow"],
                "control_n": control_n,
                "control_radius_c": radius,
                "control_dates": ";".join(pd.Timestamp(x).date().isoformat() for x in controls),
            }
            for target in TARGETS:
                baseline = float(control_rows[target].median())
                observed = float(day[target])
                city_record[f"{target}_gt"] = observed
                city_record[f"{target}_control"] = baseline
                city_record[f"{target}_ratio"] = (observed + 0.5) / (baseline + 0.5)
                city_record[f"{target}_signed_gap"] = (observed - baseline) / (baseline + 0.5)
            city_record["snow_total_mm"] = event.snow_total_mm
            city_record["event_peak_depth_cm"] = event.depth_peak_cm
            city_rows.append(city_record)
            match_rows.append({
                "event_id": event.event_id, "winter": event.winter, "h": h,
                "recovery_date": day_date, "control_n": control_n,
                "control_radius_c": radius, "control_dates": city_record["control_dates"],
            })

            for station_id in eligible_stations:
                try:
                    actual = station_index.loc[(day_date, station_id)]
                except KeyError:
                    actual = pd.Series({target: 0.0 for target in ["rides", "member", "casual", "unknown"]})
                try:
                    control_keys = pd.MultiIndex.from_product([controls, [station_id]], names=["date", "station_id"])
                    control_station_rows = station_index.reindex(control_keys, fill_value=0)
                    baselines = control_station_rows.reindex(columns=TARGETS, fill_value=0).median(axis=0)
                except (KeyError, ValueError):
                    baselines = pd.Series(0.0, index=TARGETS)
                station_record = {
                    "event_id": event.event_id,
                    "winter": event.winter,
                    "date": day_date,
                    "station_id": station_id,
                    "h": h,
                    "residual_snow_cm": day["residual_snow_cm"],
                    "snowpack_state": "present" if day["residual_snow_cm"] > 0 else "absent",
                    "tmean_c": day["tmean_c"],
                    "PRCP": day["PRCP"],
                    "AWND": day["AWND"],
                    "is_holiday": day["is_holiday"],
                    "control_n": control_n,
                }
                for target in TARGETS:
                    observed = float(actual.get(target, 0.0))
                    baseline = float(baselines[target])
                    station_record[f"{target}_gt"] = observed
                    station_record[f"{target}_control"] = baseline
                    station_record[f"{target}_ratio"] = (observed + 0.5) / (baseline + 0.5)
                station_rows.append(station_record)
    city_panel = pd.DataFrame(city_rows)
    station_panel = pd.DataFrame(station_rows)
    matches = pd.DataFrame(match_rows)
    return city_panel, station_panel, matches


EVENT_FEATURES = [f"{target}_ratio_h{h}" for target in ["rides", "member", "casual"] for h in range(1, 5)]


def event_cluster_validation(city_panel: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event_features = city_panel.pivot_table(index="event_id", columns="h", values=["rides_ratio", "member_ratio", "casual_ratio"], aggfunc="mean")
    event_features.columns = [f"{name}_h{h}" for name, h in event_features.columns]
    event_features = event_features.reindex(columns=EVENT_FEATURES)
    event_features = event_features.join(events.set_index("event_id")[["winter", "snow_total_mm", "depth_peak_cm"]], how="inner")
    event_features["matched_recovery_days"] = city_panel.groupby("event_id").size()
    eligible = event_features[event_features["matched_recovery_days"].ge(3)].copy()
    if len(eligible) < 5:
        raise RuntimeError(f"Only {len(eligible)} events have at least three matched recovery days; 2-cluster checks need at least five")
    feature_matrix = eligible[EVENT_FEATURES]
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    x = scaler.fit_transform(imputer.fit_transform(feature_matrix))
    full = KMeans(n_clusters=2, n_init=50, random_state=SEED).fit(x)
    eligible["cluster"] = full.labels_
    eligible.reset_index().to_csv(OUT / "event_clusters.csv", index=False)
    full_silhouette = float(silhouette_score(x, full.labels_)) if len(eligible) > 2 else np.nan

    loyo_rows = []
    for held_winter in sorted(eligible["winter"].unique()):
        train = eligible[eligible["winter"].ne(held_winter)]
        test = eligible[eligible["winter"].eq(held_winter)]
        if len(train) < 4 or test.empty:
            continue
        fold_imputer = SimpleImputer(strategy="median")
        fold_scaler = StandardScaler()
        x_train = fold_scaler.fit_transform(fold_imputer.fit_transform(train[EVENT_FEATURES]))
        x_test = fold_scaler.transform(fold_imputer.transform(test[EVENT_FEATURES]))
        model = KMeans(n_clusters=2, n_init=50, random_state=SEED).fit(x_train)
        labels = model.predict(x_test)
        train_sil = float(silhouette_score(x_train, model.labels_))
        for (event_id, row), label in zip(test.iterrows(), labels):
            loyo_rows.append({
                "held_winter": held_winter,
                "event_id": event_id,
                "assigned_cluster": int(label),
                "train_events": len(train),
                "held_events": len(test),
                "both_event_types_in_held_winter": len(set(labels)) == 2,
                "train_silhouette": train_sil,
                "full_cluster": int(row["cluster"]),
            })
    loyo = pd.DataFrame(loyo_rows)

    loeo_rows = []
    for event_id, held in eligible.iterrows():
        train = eligible.drop(index=event_id)
        fold_imputer = SimpleImputer(strategy="median")
        fold_scaler = StandardScaler()
        x_train = fold_scaler.fit_transform(fold_imputer.fit_transform(train[EVENT_FEATURES]))
        x_test = fold_scaler.transform(fold_imputer.transform(held[EVENT_FEATURES].to_frame().T))
        model = KMeans(n_clusters=2, n_init=50, random_state=SEED).fit(x_train)
        label = int(model.predict(x_test)[0])
        distance = float(np.linalg.norm(x_test[0] - model.cluster_centers_[label]))
        train_radius = float(np.quantile(np.linalg.norm(x_train - model.cluster_centers_[model.labels_], axis=1), 0.95))
        loeo_rows.append({
            "event_id": event_id,
            "winter": int(held["winter"]),
            "assigned_cluster": label,
            "full_cluster": int(held["cluster"]),
            "distance_to_assigned_center": distance,
            "train_95pct_distance": train_radius,
            "held_event_within_train_95pct_radius": distance <= train_radius,
        })
    loeo = pd.DataFrame(loeo_rows)
    loeo_ari = float(adjusted_rand_score(loeo["full_cluster"], loeo["assigned_cluster"])) if len(loeo) > 1 else np.nan
    cluster_profile = eligible.groupby("cluster")[EVENT_FEATURES + ["snow_total_mm", "depth_peak_cm"]].mean().reset_index()
    cluster_profile.to_csv(OUT / "event_cluster_profiles.csv", index=False)
    write_json(OUT / "event_cluster_validation_summary.json", {
        "eligible_events": len(eligible),
        "clusters": 2,
        "full_fit_silhouette": full_silhouette,
        "loyo_event_assignments": len(loyo),
        "loyo_winter_folds": int(loyo["held_winter"].nunique()) if not loyo.empty else 0,
        "loyo_winter_types_both_present_folds": int(loyo.groupby("held_winter")["both_event_types_in_held_winter"].first().sum()) if not loyo.empty else 0,
        "loeo_event_assignments": len(loeo),
        "loeo_agreement_ari": loeo_ari,
        "loeo_events_within_training_95pct_radius": int(loeo["held_event_within_train_95pct_radius"].sum()) if not loeo.empty else 0,
    })
    loyo.to_csv(OUT / "event_cluster_leave_winter_out.csv", index=False)
    loeo.to_csv(OUT / "event_cluster_leave_event_out.csv", index=False)
    return eligible, loyo, loeo


STATION_FEATURES = ["rides_ratio_mean", "member_ratio_mean", "casual_ratio_mean", "casual_member_gap", "casual_recovery_slope", "baseline_log"]
STATION_RATIO_FEATURES = ["rides_ratio_mean", "member_ratio_mean", "casual_ratio_mean"]
STATION_RECOVERY_FEATURES = ["rides_ratio_mean", "member_ratio_mean", "casual_ratio_mean", "casual_member_gap", "casual_recovery_slope"]


def station_features(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame(columns=STATION_FEATURES)
    summary = panel.groupby("station_id").agg(
        n_rows=("event_id", "size"),
        rides_ratio_mean=("rides_ratio", "mean"),
        member_ratio_mean=("member_ratio", "mean"),
        casual_ratio_mean=("casual_ratio", "mean"),
        baseline_mean=("rides_control", "mean"),
        h1_2_casual=("casual_ratio", lambda values: float(values[panel.loc[values.index, "h"].le(2)].mean())),
        h5_7_casual=("casual_ratio", lambda values: float(values[panel.loc[values.index, "h"].ge(5)].mean())),
    )
    summary["casual_member_gap"] = np.log(summary["casual_ratio_mean"].clip(lower=0.05)) - np.log(summary["member_ratio_mean"].clip(lower=0.05))
    summary["casual_recovery_slope"] = summary["h5_7_casual"] - summary["h1_2_casual"]
    summary["baseline_log"] = np.log1p(summary["baseline_mean"])
    return summary[summary["n_rows"].ge(4)]


def station_cluster_inputs(features: pd.DataFrame, log_ratios: bool, include_baseline: bool) -> pd.DataFrame:
    columns = STATION_FEATURES if include_baseline else STATION_RECOVERY_FEATURES
    inputs = features[columns].copy()
    if log_ratios:
        inputs[STATION_RATIO_FEATURES] = np.log(inputs[STATION_RATIO_FEATURES].clip(lower=0.05))
    return inputs


def station_cluster_validation(station_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    full_features = station_features(station_panel)
    if len(full_features) < 20:
        raise RuntimeError(f"Only {len(full_features)} stations have enough matched recovery observations for clustering")
    transform_summaries = {}
    primary_labels = None
    primary_folds = []
    methods = [
        ("raw_ratios_plus_baseline", False, True),
        ("log_ratios_plus_baseline", True, True),
        ("log_ratios_recovery_only", True, False),
    ]
    for method, log_ratios, include_baseline in methods:
        all_inputs = station_cluster_inputs(full_features, log_ratios, include_baseline)
        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        x = scaler.fit_transform(imputer.fit_transform(all_inputs))
        full_model = KMeans(n_clusters=3, n_init=50, random_state=SEED).fit(x)
        fold_results = []
        for held_winter in sorted(station_panel["winter"].unique()):
            train = station_features(station_panel[station_panel["winter"].ne(held_winter)])
            test = station_features(station_panel[station_panel["winter"].eq(held_winter)])
            if len(train) < 20 or test.empty:
                continue
            train_inputs = station_cluster_inputs(train, log_ratios, include_baseline)
            test_inputs = station_cluster_inputs(test, log_ratios, include_baseline)
            fold_imputer = SimpleImputer(strategy="median")
            fold_scaler = StandardScaler()
            x_train = fold_scaler.fit_transform(fold_imputer.fit_transform(train_inputs))
            x_test = fold_scaler.transform(fold_imputer.transform(test_inputs))
            fold_model = KMeans(n_clusters=3, n_init=50, random_state=SEED).fit(x_train)
            assigned = fold_model.predict(x_test)
            held_winter_model = KMeans(n_clusters=3, n_init=50, random_state=SEED).fit(x_test) if len(test) >= 3 else None
            ari = float(adjusted_rand_score(held_winter_model.labels_, assigned)) if held_winter_model is not None else np.nan
            fold_results.append({
                "held_winter": int(held_winter),
                "held_stations": len(test),
                "represented_types": int(np.unique(assigned).size),
                "all_three_types_present": bool(np.unique(assigned).size == 3),
                "cluster_coverage_ari": ari,
            })
            if method == "log_ratios_recovery_only":
                for station_id, cluster in zip(test.index, assigned):
                    primary_folds.append({
                        "held_winter": int(held_winter),
                        "station_id": station_id,
                        "assigned_cluster": int(cluster),
                        "train_stations": len(train),
                        "held_stations": len(test),
                        "held_winter_cluster_coverage_ari": ari,
                    })
        transform_summaries[method] = {
            "full_fit_cluster_sizes": np.bincount(full_model.labels_, minlength=3).astype(int).tolist(),
            "winter_folds": fold_results,
            "all_three_types_present_every_fold": all(row["all_three_types_present"] for row in fold_results),
            "mean_held_winter_partition_ari": float(np.nanmean([row["cluster_coverage_ari"] for row in fold_results])),
        }
        if method == "log_ratios_recovery_only":
            primary_labels = full_model.labels_

    full_features["cluster"] = primary_labels
    full_features.reset_index().to_csv(OUT / "station_recovery_clusters.csv", index=False)
    summaries = full_features.groupby("cluster").agg(
        stations=("n_rows", "size"),
        rides_ratio=("rides_ratio_mean", "mean"),
        member_ratio=("member_ratio_mean", "mean"),
        casual_ratio=("casual_ratio_mean", "mean"),
        casual_member_gap=("casual_member_gap", "mean"),
        baseline_mean=("baseline_mean", "mean"),
    ).reset_index()
    summaries.to_csv(OUT / "station_cluster_summary.csv", index=False)

    loyo = pd.DataFrame(primary_folds)
    fold_summary = loyo.groupby("held_winter").agg(
        held_stations=("station_id", "size"),
        represented_types=("assigned_cluster", "nunique"),
        all_three_types_present=("assigned_cluster", lambda values: values.nunique() == 3),
        cluster_coverage_ari=("held_winter_cluster_coverage_ari", "first"),
    ).reset_index() if not loyo.empty else pd.DataFrame()
    loyo.to_csv(OUT / "station_cluster_leave_winter_out.csv", index=False)
    fold_summary.to_csv(OUT / "station_cluster_leave_winter_summary.csv", index=False)
    write_json(OUT / "station_cluster_validation_summary.json", {
        "cluster_count": 3,
        "stations_in_full_fit": len(full_features),
        "primary_feature_transform": "natural log of total, member, and casual recovery ratios before standardization; baseline ride volume is excluded from clustering; cluster profiles remain in the original ratio scale",
        "winter_folds": fold_summary.to_dict(orient="records") if not fold_summary.empty else [],
        "all_three_types_present_every_fold": bool(fold_summary["all_three_types_present"].all()) if not fold_summary.empty else False,
        "mean_held_winter_partition_ari": float(fold_summary["cluster_coverage_ari"].mean()) if not fold_summary.empty else None,
        "transform_sensitivity": transform_summaries,
    })
    return full_features.reset_index(), loyo


def fit_hierarchical_model(city_panel: pd.DataFrame) -> pd.DataFrame:
    if city_panel.empty:
        write_json(OUT / "hierarchical_model_status.json", {"status": "no_matched_city_days"})
        return pd.DataFrame()
    wide = pd.concat([
        city_panel.assign(user_type=user_type, ratio=city_panel[f"{user_type}_ratio"])
        for user_type in ["casual", "member"]
    ], ignore_index=True)
    wide["log_ratio"] = np.log(wide["ratio"].clip(lower=0.01))
    wide["user_type"] = pd.Categorical(wide["user_type"], categories=["casual", "member"], ordered=True)
    wide["h"] = wide["h"].astype(int).astype("category")
    wide["winter"] = wide["winter"].astype(str).astype("category")
    if wide["event_id"].nunique() < 3:
        write_json(OUT / "hierarchical_model_status.json", {"status": "insufficient_events", "events": int(wide["event_id"].nunique()), "rows": len(wide)})
        return pd.DataFrame()
    formula = "log_ratio ~ residual_snow_cm * C(user_type) + C(h) + C(winter) + tmean_c + PRCP + AWND"
    try:
        model = smf.mixedlm(formula, data=wide, groups=wide["event_id"], re_formula="1")
        result = model.fit(reml=True, method="lbfgs", maxiter=500, disp=False)
        ci = result.conf_int()
        summary = pd.DataFrame({
            "term": result.params.index,
            "coefficient": result.params.values,
            "standard_error": result.bse.values,
            "p_value": result.pvalues.values,
            "ci_low": ci.iloc[:, 0].values,
            "ci_high": ci.iloc[:, 1].values,
        })
        summary["n_rows"] = len(wide)
        summary["n_events"] = int(wide["event_id"].nunique())
        summary.to_csv(OUT / "hierarchical_model_coefficients.csv", index=False)
        robust_result = smf.ols(formula, data=wide).fit(
            cov_type="cluster",
            cov_kwds={"groups": wide["event_id"], "use_correction": True},
        )
        robust_ci = robust_result.conf_int()
        robust_summary = pd.DataFrame({
            "term": robust_result.params.index,
            "coefficient": robust_result.params.values,
            "standard_error_event_clustered": robust_result.bse.values,
            "p_value": robust_result.pvalues.values,
            "ci_low": robust_ci.iloc[:, 0].values,
            "ci_high": robust_ci.iloc[:, 1].values,
            "n_rows": len(wide),
            "n_events": int(wide["event_id"].nunique()),
        })
        robust_summary.to_csv(OUT / "event_cluster_robust_regression.csv", index=False)
        snow_term = "residual_snow_cm"
        interaction_term = "residual_snow_cm:C(user_type)[T.member]"
        primary_member_contrast = np.zeros((1, len(result.fe_params)))
        primary_member_contrast[0, result.fe_params.index.get_loc(snow_term)] = 1.0
        primary_member_contrast[0, result.fe_params.index.get_loc(interaction_term)] = 1.0
        primary_member_test = result.t_test(primary_member_contrast)
        robust_member_test = robust_result.t_test(
            f"{snow_term} + {interaction_term} = 0"
        )
        primary_member_ci = primary_member_test.conf_int()[0]
        robust_member_ci = robust_member_test.conf_int()[0]
        write_json(OUT / "hierarchical_model_status.json", {
            "status": "converged" if result.converged else "not_converged",
            "formula": formula,
            "rows": len(wide),
            "events": int(wide["event_id"].nunique()),
            "log_likelihood": float(result.llf),
            "converged": bool(result.converged),
            "random_effect_variance_event": float(result.cov_re.iloc[0, 0]) if result.cov_re.size else None,
            "reference_user_type": "casual",
            "outcome": "log(observed city rides / same-winter event-matched control median)",
            "matching_controls": "same winter, weekday, federal-holiday status, and mean temperature within 5 C (8 C when fewer than three controls were available)",
            "holiday_recovery_days": int(wide["is_holiday"].sum()),
            "holiday_model_note": "Holiday status was not included as a model term because all matched recovery days were non-holidays; holiday status was enforced when selecting control days.",
            "estimation_method": "REML mixed-effects regression with a random intercept for snow event",
            "sensitivity_method": "ordinary least squares with the same fixed effects and standard errors clustered by snow event",
            "primary_snow_depth_member_coefficient": float(result.fe_params[snow_term] + result.fe_params[interaction_term]),
            "primary_snow_depth_member_ci_low": float(primary_member_ci[0]),
            "primary_snow_depth_member_ci_high": float(primary_member_ci[1]),
            "primary_snow_depth_member_p_value": float(np.asarray(primary_member_test.pvalue).item()),
            "primary_snow_depth_user_interaction_p_value": float(result.pvalues[interaction_term]),
            "sensitivity_snow_depth_casual_coefficient": float(robust_result.params["residual_snow_cm"]),
            "sensitivity_snow_depth_member_coefficient": float(robust_result.params["residual_snow_cm"] + robust_result.params["residual_snow_cm:C(user_type)[T.member]"]),
            "sensitivity_snow_depth_member_ci_low": float(robust_member_ci[0]),
            "sensitivity_snow_depth_member_ci_high": float(robust_member_ci[1]),
            "sensitivity_snow_depth_member_p_value": float(np.asarray(robust_member_test.pvalue).item()),
            "sensitivity_snow_depth_user_interaction_p_value": float(robust_result.pvalues["residual_snow_cm:C(user_type)[T.member]"]),
        })
        return summary
    except Exception as error:
        write_json(OUT / "hierarchical_model_status.json", {
            "status": "fit_failed", "formula": formula, "rows": len(wide),
            "events": int(wide["event_id"].nunique()),
            "error": str(error),
        })
        return pd.DataFrame()


def analyze() -> None:
    city, station, metadata = build_panel()
    events = snow_events(city)
    events.to_csv(OUT / "snow_events.csv", index=False)
    city_panel, station_panel, matches = matched_recovery(city, station, metadata, events)
    city_panel.to_csv(OUT / "event_matched_city_recovery.csv", index=False)
    station_panel.to_csv(OUT / "event_matched_station_recovery.csv", index=False)
    matches.to_csv(OUT / "event_control_matches.csv", index=False)
    event_cluster_validation(city_panel, events)
    station_clusters, _ = station_cluster_validation(station_panel)
    fit_hierarchical_model(city_panel)
    spatial_features(metadata, station_clusters, city_panel, station_panel)
    make_figures(city_panel, station_clusters)
    write_json(OUT / "stage_a_summary.json", {
        "events_at_10mm_threshold": len(events),
        "events_with_matched_recovery": int(city_panel["event_id"].nunique()),
        "matched_city_event_days": len(city_panel),
        "matched_station_event_days": len(station_panel),
        "recovery_days_with_controls": int(matches["recovery_date"].nunique()) if not matches.empty else 0,
        "snowpack_present_days": int(city_panel["snowpack_state"].eq("present").sum()) if not city_panel.empty else 0,
        "snowpack_absent_days": int(city_panel["snowpack_state"].eq("absent").sum()) if not city_panel.empty else 0,
        "strict_match_days_5c": int(matches["control_radius_c"].eq(5.0).sum()) if not matches.empty else 0,
        "widened_match_days_8c": int(matches["control_radius_c"].eq(8.0).sum()) if not matches.empty else 0,
    })
    print(json.dumps(json.loads((OUT / "stage_a_summary.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=2), flush=True)


def spatial_features(metadata: pd.DataFrame, station_clusters: pd.DataFrame, city_panel: pd.DataFrame, station_panel: pd.DataFrame) -> None:
    spatial_root = RAW / "chicago_spatial"
    spatial_root.mkdir(parents=True, exist_ok=True)
    sources = {
        "community_areas": "https://data.cityofchicago.org/api/geospatial/igwz-8jzy?method=export&format=GeoJSON",
        "cta_rail_stations": "https://data.cityofchicago.org/api/geospatial/3tzw-cg4m?method=export&format=GeoJSON",
        "parks": "https://data.cityofchicago.org/api/geospatial/ejsh-fztr?method=export&format=GeoJSON",
    }
    filenames = {
        "community_areas": "community_areas.geojson",
        "cta_rail_stations": "cta_rail_stations.geojson",
        "parks": "parks_ejsh-fztr.geojson",
    }
    local_paths = {}
    for name, url in sources.items():
        path = spatial_root / filenames[name]
        if not path.exists() or path.stat().st_size < 1000:
            from urllib.request import urlretrieve
            urlretrieve(url, path)
        local_paths[name] = path
    import geopandas as gpd

    active = metadata.dropna(subset=["lat", "lon"]).copy()
    points = gpd.GeoDataFrame(active, geometry=gpd.points_from_xy(active["lon"], active["lat"]), crs="EPSG:4326")
    points = points.to_crs("EPSG:26916")
    areas = gpd.read_file(local_paths["community_areas"])
    rail = gpd.read_file(local_paths["cta_rail_stations"])
    parks = gpd.read_file(local_paths["parks"])
    for layer in [areas, rail, parks]:
        if layer.crs is None:
            layer.set_crs("EPSG:4326", inplace=True)
    areas = areas.to_crs(points.crs)
    rail = rail.to_crs(points.crs)
    parks = parks.to_crs(points.crs)
    community_field = next((name for name in ["community", "community_area", "name", "COMMUNITY"] if name in areas.columns), None)
    if community_field:
        joined = gpd.sjoin(points, areas[[community_field, "geometry"]], how="left", predicate="within")
        active["community_area"] = joined[community_field].to_numpy()
    else:
        active["community_area"] = None
    station_geom = points[["station_id", "geometry"]].copy()
    rail_dist = gpd.sjoin_nearest(station_geom, rail[["geometry"]], how="left", distance_col="cta_distance_m").groupby("station_id")["cta_distance_m"].min()
    park_dist = gpd.sjoin_nearest(station_geom, parks[["geometry"]], how="left", distance_col="park_distance_m").groupby("station_id")["park_distance_m"].min()
    active = active.set_index("station_id")
    active["cta_distance_m"] = rail_dist
    active["park_distance_m"] = park_dist
    active = active.reset_index()
    features = active.merge(station_clusters[["station_id", "cluster", "casual_ratio_mean", "member_ratio_mean", "baseline_mean"]], on="station_id", how="inner")
    station_event = station_panel.groupby("station_id").agg(
        casual_ratio_event_mean=("casual_ratio", "mean"),
        member_ratio_event_mean=("member_ratio", "mean"),
        event_days=("event_id", "size"),
    ).reset_index()
    features = features.merge(station_event, on="station_id", how="left")
    features.to_csv(OUT / "station_spatial_features.csv", index=False)
    complete = features.dropna(subset=["cta_distance_m", "park_distance_m", "casual_ratio_event_mean", "baseline_mean"])
    if len(complete) >= 30:
        complete = complete.copy()
        complete["log_baseline"] = np.log1p(complete["baseline_mean"])
        import statsmodels.api as sm
        X = sm.add_constant(complete[["cta_distance_m", "park_distance_m", "log_baseline"]] / [1000, 1000, 1])
        model = sm.OLS(complete["casual_ratio_event_mean"], X).fit(cov_type="HC3")
        ci = model.conf_int()
        result = pd.DataFrame({
            "term": model.params.index,
            "coefficient": model.params.values,
            "standard_error_hc3": model.bse.values,
            "p_value": model.pvalues.values,
            "ci_low": ci.iloc[:, 0].values,
            "ci_high": ci.iloc[:, 1].values,
            "n_stations": len(complete),
        })
        result.to_csv(OUT / "station_spatial_model.csv", index=False)
        write_json(OUT / "station_spatial_model_status.json", {
            "status": "fit", "n_stations": len(complete), "r_squared": float(model.rsquared),
            "outcome": "mean casual-user post-snow recovery ratio across matched event days",
            "predictors": "nearest CTA rail station distance (km), nearest park boundary distance (km), log(1 + control-day station rides)",
            "interpretation": "association only; cross-sectional station features do not establish causality",
        })
    else:
        write_json(OUT / "station_spatial_model_status.json", {"status": "insufficient_complete_stations", "n_stations": len(complete)})

    area_complete = complete.dropna(subset=["community_area"]).copy()
    if len(area_complete) >= 30 and area_complete["community_area"].nunique() >= 2:
        area_complete["log_baseline"] = np.log1p(area_complete["baseline_mean"])
        area_complete["cta_distance_km"] = area_complete["cta_distance_m"] / 1000
        area_complete["park_distance_km"] = area_complete["park_distance_m"] / 1000
        base_model = smf.ols(
            "casual_ratio_event_mean ~ cta_distance_km + park_distance_km + log_baseline",
            data=area_complete,
        ).fit()
        area_model = smf.ols(
            "casual_ratio_event_mean ~ cta_distance_km + park_distance_km + log_baseline + C(community_area)",
            data=area_complete,
        ).fit(cov_type="HC3")
        area_ci = area_model.conf_int()
        pd.DataFrame({
            "term": area_model.params.index,
            "coefficient": area_model.params.values,
            "standard_error_hc3": area_model.bse.values,
            "p_value": area_model.pvalues.values,
            "ci_low": area_ci.iloc[:, 0].values,
            "ci_high": area_ci.iloc[:, 1].values,
            "n_stations": len(area_complete),
        }).to_csv(OUT / "station_community_area_model.csv", index=False)
        write_json(OUT / "station_community_area_model_status.json", {
            "status": "fit",
            "n_stations": len(area_complete),
            "n_community_areas": int(area_complete["community_area"].nunique()),
            "base_model_r_squared_same_sample": float(base_model.rsquared),
            "area_fixed_effect_model_r_squared": float(area_model.rsquared),
            "area_fixed_effect_model_adjusted_r_squared": float(area_model.rsquared_adj),
            "interpretation": "in-sample area differences are descriptive associations and have not been validated on unseen community areas",
        })
    else:
        write_json(OUT / "station_community_area_model_status.json", {
            "status": "insufficient_community_area_data",
            "n_stations": len(area_complete),
            "n_community_areas": int(area_complete["community_area"].nunique()),
        })


def make_figures(city_panel: pd.DataFrame, station_clusters: pd.DataFrame) -> None:
    if not city_panel.empty:
        fig, ax = plt.subplots(figsize=(9.2, 5.0))
        colors = {"present": "#d9822b", "absent": "#287a71"}
        labels = {"rides_ratio": "All rides", "member_ratio": "Members", "casual_ratio": "Casual riders"}
        for state in ["present", "absent"]:
            subset = city_panel[city_panel["snowpack_state"].eq(state)]
            if subset.empty:
                continue
            for target, label in labels.items():
                event_means = subset.groupby(["event_id", "h"])[target].mean().reset_index()
                grouped = event_means.groupby("h")[target].agg(["mean", "sem"]).reset_index()
                ax.plot(grouped["h"], grouped["mean"], marker="o", color=colors[state], linestyle="-" if target == "casual_ratio" else "--" if target == "member_ratio" else ":", label=f"{label}, snowpack {'present' if state == 'present' else 'absent'}")
        ax.axhline(1.0, color="#56645f", linewidth=1, linestyle="--")
        ax.set(xlabel="Days after snowfall ends", ylabel="Rides / matched dry-day median", xticks=range(1, 8), title="Observed recovery after snowfall")
        ax.legend(frameon=False, ncol=2, fontsize=8)
        ax.grid(axis="y", color="#e5ebe7", linewidth=0.8)
        fig.tight_layout()
        fig.savefig(FIG / "01_event_recovery_curves.png", dpi=200)
        plt.close(fig)
    if not station_clusters.empty:
        try:
            points = station_clusters.merge(pd.read_csv(PROC / "station_metadata.csv"), on="station_id", how="left", suffixes=("", "_meta"))
            fig, ax = plt.subplots(figsize=(7.2, 7.2))
            palette = ["#287a71", "#e09a45", "#3c78a8"]
            for cluster in sorted(points["cluster"].unique()):
                d = points[(points["cluster"] == cluster) & points["lat"].notna() & points["lon"].notna()]
                ax.scatter(d["lon"], d["lat"], s=8, alpha=0.7, color=palette[int(cluster) % len(palette)], label=f"Station type {int(cluster) + 1}", linewidths=0)
            ax.set(xlabel="Longitude", ylabel="Latitude", title="Station recovery types in Chicago")
            ax.legend(frameon=False)
            ax.set_aspect("equal", adjustable="datalim")
            ax.grid(color="#e5ebe7", linewidth=0.6)
            fig.tight_layout()
            fig.savefig(FIG / "02_station_recovery_types_map.png", dpi=200)
            plt.close(fig)
        except Exception as error:
            write_json(OUT / "station_map_status.json", {"status": "plot_failed", "error": str(error)})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    analyze()
