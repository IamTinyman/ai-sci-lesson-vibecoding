from pathlib import Path
import json
import zipfile

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.neighbors import NearestNeighbors
from sklearn.neural_network import MLPRegressor


ROOT = Path("/root/autodl-tmp/ai-sci/parallel/codex-0005-weather-recovery-20261115")
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def stage_a_event_stability():
    events = pd.read_csv(RESULTS / "event_clusters.csv")
    value_cols = [
        c for c in events.columns
        if c.startswith("rides_ratio_h") or c.startswith("mix_ratio_h")
    ]
    raw_x = events[value_cols].fillna(events[value_cols].median()).to_numpy()
    winters = sorted(events["winter"].unique())
    rows = []
    for held_out in winters:
        train_mask = events["winter"] != held_out
        scaler = StandardScaler().fit(raw_x[train_mask])
        train_x = scaler.transform(raw_x[train_mask])
        test_x = scaler.transform(raw_x[~train_mask])
        if len(train_x) < 6 or len(test_x) == 0:
            continue
        km = KMeans(n_clusters=2, random_state=20261115, n_init=50).fit(train_x)
        rows.append({
            "held_out_winter": int(held_out),
            "train_events": int(train_mask.sum()),
            "test_events": int((~train_mask).sum()),
            "train_silhouette": float(silhouette_score(train_x, km.labels_)),
            "test_cluster_0": int((km.predict(test_x) == 0).sum()),
            "test_cluster_1": int((km.predict(test_x) == 1).sum()),
        })
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "event_cluster_leave_winter_out.csv", index=False)

    station = pd.read_csv(RESULTS / "station_recovery_clusters.csv")
    feat_cols = ["rides_ratio", "member_ratio", "casual_ratio", "casual_share", "baseline"]
    sx = StandardScaler().fit_transform(station[feat_cols].fillna(station[feat_cols].median()))
    reference = KMeans(n_clusters=3, random_state=20261115, n_init=50).fit(sx).labels_
    rng = np.random.default_rng(20261115)
    ari = []
    for _ in range(100):
        idx = rng.choice(len(station), len(station), replace=True)
        model = KMeans(n_clusters=3, random_state=int(rng.integers(1, 1_000_000)), n_init=20)
        labels = model.fit_predict(sx[idx])
        ari.append(adjusted_rand_score(reference[idx], labels))
    stability = {
        "event_leave_winter_rows": int(len(out)),
        "event_mean_train_silhouette": float(out["train_silhouette"].mean()) if len(out) else None,
        "station_bootstrap_ari_mean": float(np.mean(ari)),
        "station_bootstrap_ari_p05": float(np.quantile(ari, 0.05)),
        "station_bootstrap_ari_p95": float(np.quantile(ari, 0.95)),
    }
    (RESULTS / "cluster_stability.json").write_text(json.dumps(stability, indent=2))


def make_sequences(d: pd.DataFrame, history=14):
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["winter"] = np.where(d["date"].dt.month >= 11, d["date"].dt.year + 1, d["date"].dt.year)
    d = d[d["date"].dt.month.isin([1, 2, 3, 12])].sort_values("date")
    for col in ["rides", "member", "casual", "PRCP", "SNOW", "SNWD", "AWND", "TMAX", "TMIN"]:
        if col not in d:
            d[col] = 0.0
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)
    d["tmean"] = (d["TMAX"] + d["TMIN"]) / 2
    d["hour"] = d["date"].dt.dayofyear / 366
    d["dow_sin"] = np.sin(d["date"].dt.dayofweek * 2 * np.pi / 7)
    d["dow_cos"] = np.cos(d["date"].dt.dayofweek * 2 * np.pi / 7)
    d["season_sin"] = np.sin(d["date"].dt.dayofyear * 2 * np.pi / 366)
    d["season_cos"] = np.cos(d["date"].dt.dayofyear * 2 * np.pi / 366)
    sequences = []
    for winter, g in d.groupby("winter", sort=True):
        g = g.sort_values("date").reset_index(drop=True)
        for i in range(history, len(g)):
            if (g.loc[i, "date"] - g.loc[i - history, "date"]).days != history:
                continue
            hist = g.iloc[i - history:i]
            target = g.iloc[i]
            counts = np.log1p(hist[["rides", "member", "casual"]].to_numpy(dtype=np.float32))
            weather = hist[["PRCP", "SNOW", "SNWD", "AWND", "tmean"]].to_numpy(dtype=np.float32)
            calendar = hist[["hour", "dow_sin", "dow_cos", "season_sin", "season_cos"]].to_numpy(dtype=np.float32)
            target_weather = target[["PRCP", "SNOW", "SNWD", "AWND", "tmean"]].to_numpy(dtype=np.float32)
            y = np.log1p(target[["rides", "member", "casual"]].to_numpy(dtype=np.float32))
            sequences.append({
                "winter": int(winter),
                "date": str(target["date"].date()),
                "counts": counts,
                "weather": weather,
                "calendar": calendar,
                "target_weather": target_weather,
                "y": y,
            })
    return sequences


def evaluate_predictions(pred, truth):
    p = np.clip(np.expm1(pred), 0, None)
    y = np.clip(np.expm1(truth), 0, None)
    ae = np.abs(p - y)
    positive = y > 0
    signed = np.where(positive, (y - p) / y, np.nan)
    return {
        "mae": float(ae.mean()),
        "wape": float(ae.sum() / max(y.sum(), 1)),
        "signed_relative_bias_nonzero": float(np.nanmean(signed)),
        "positive_days": int(positive.sum()),
    }


def stage_b_sequence_mlp():
    d = pd.read_csv(DATA / "city_daily.csv")
    seq = make_sequences(d)
    train = [s for s in seq if s["winter"] in {2022, 2023, 2024}]
    test = [s for s in seq if s["winter"] in {2025, 2026}]
    if len(train) < 30 or len(test) < 10:
        raise RuntimeError(f"Insufficient sequence data train={len(train)} test={len(test)}")
    results = []
    for name, use_weather, use_target in [
        ("history_only", False, False),
        ("lagged_weather", True, False),
        ("current_weather", True, True),
    ]:
        xs = []
        ys = []
        tw = []
        for s in train:
            parts = [s["counts"], s["calendar"]]
            if use_weather:
                parts.insert(1, s["weather"])
            xs.append(np.concatenate(parts, axis=1))
            ys.append(s["y"])
            tw.append(s["target_weather"])
        X = np.stack(xs).reshape(len(xs), -1)
        Y = np.stack(ys)
        TW = np.stack(tw)
        test_x = []
        test_y = []
        test_tw = []
        for s in test:
            parts = [s["counts"], s["calendar"]]
            if use_weather:
                parts.insert(1, s["weather"])
            test_x.append(np.concatenate(parts, axis=1))
            test_y.append(s["y"])
            test_tw.append(s["target_weather"])
        TX = np.stack(test_x).reshape(len(test_x), -1)
        TY = np.stack(test_y)
        TTW = np.stack(test_tw)
        # Flattened 14-day windows keep the comparison transparent while
        # retaining a nonlinear multi-output model in the existing environment.
        if use_target:
            X_fit = np.concatenate([X, TW], axis=1)
            X_test = np.concatenate([TX, TTW], axis=1)
        else:
            X_fit = X
            X_test = TX
        x_scaler = StandardScaler().fit(X_fit)
        y_scaler = StandardScaler().fit(Y)
        model = MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            learning_rate_init=0.003,
            max_iter=600,
            early_stopping=True,
            validation_fraction=0.2,
            n_iter_no_change=40,
            random_state=20261115,
        )
        model.fit(x_scaler.transform(X_fit), y_scaler.transform(Y))
        pred = y_scaler.inverse_transform(model.predict(x_scaler.transform(X_test)))
        for j, target in enumerate(["rides", "member", "casual"]):
            m = evaluate_predictions(pred[:, j], TY[:, j])
            m.update({
                "model": name,
                "target": target,
                "test_samples": len(test),
                "test_start": test[0]["date"],
                "test_end": test[-1]["date"],
                "iterations": int(model.n_iter_),
            })
            results.append(m)
        np.save(RESULTS / f"mlp_pred_{name}.npy", pred)
    out = pd.DataFrame(results)
    out.to_csv(RESULTS / "mlp_metrics.csv", index=False)


def stage_c_spatial():
    trip_root = Path("/root/autodl-tmp/ai-sci/data/raw/divvy")
    pieces = []
    for path in sorted(trip_root.rglob("*.zip")):
        if "2025" not in path.name:
            continue
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")]
            if len(names) != 1:
                continue
            d = pd.read_csv(z.open(names[0]), usecols=["start_station_name", "start_lat", "start_lng"])
        d["station"] = d["start_station_name"].astype("string").str.strip()
        d = d.dropna(subset=["station", "start_lat", "start_lng"])
        pieces.append(d.groupby("station", observed=True).agg(lat=("start_lat", "median"), lon=("start_lng", "median"), n=("station", "size")).reset_index())
    coords = pd.concat(pieces).groupby("station", as_index=False).agg(lat=("lat", "median"), lon=("lon", "median"), n=("n", "sum"))
    coords["distance_center_km"] = 111 * np.sqrt((coords["lat"] - 41.88) ** 2 + ((coords["lon"] + 87.63) * 0.75) ** 2)
    xy = coords[["lat", "lon"]].to_numpy()
    nn = NearestNeighbors(n_neighbors=min(9, len(coords))).fit(xy)
    dist, _ = nn.kneighbors(xy)
    coords["local_density_proxy"] = 1 / np.maximum(dist[:, -1], 1e-4)
    clusters = pd.read_csv(RESULTS / "station_recovery_clusters.csv")
    out = clusters.merge(coords, on="station", how="left")
    out.to_csv(RESULTS / "station_spatial_features.csv", index=False)
    summary = out.groupby("cluster").agg(
        stations=("station", "size"),
        mean_distance_center_km=("distance_center_km", "mean"),
        mean_density_proxy=("local_density_proxy", "mean"),
        mean_casual_share=("casual_share", "mean"),
        mean_baseline=("baseline", "mean"),
    )
    summary.to_csv(RESULTS / "station_spatial_summary.csv")


def main():
    stage_a_event_stability()
    stage_b_sequence_mlp()
    stage_c_spatial()
    print("stage_abc_completed")


if __name__ == "__main__":
    main()
