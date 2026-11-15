from pathlib import Path
import json
import zipfile
import hashlib

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from sklearn.ensemble import RandomForestRegressor
import matplotlib.pyplot as plt


ROOT = Path("/root/autodl-tmp/ai-sci/parallel/codex-0005-weather-recovery-20261115")
RAW = Path("/root/autodl-tmp/ai-sci/data/raw")
TRIP_ROOT = RAW / "divvy"
NOAA_ROOT = RAW / "noaa"

ROOT.joinpath("results").mkdir(parents=True, exist_ok=True)
ROOT.joinpath("data").mkdir(parents=True, exist_ok=True)
ROOT.joinpath("figures").mkdir(parents=True, exist_ok=True)


def load_weather() -> pd.DataFrame:
    frames = []
    for path in sorted(NOAA_ROOT.glob("*.csv")):
        d = pd.read_csv(path, low_memory=False)
        d["date"] = pd.to_datetime(d["DATE"], errors="coerce")
        keep = ["date", "PRCP", "SNOW", "SNWD", "AWND", "TMAX", "TMIN"]
        d = d[keep].copy()
        for col in keep[1:]:
            d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)
        frames.append(d)
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def load_trips() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_parts = []
    station_parts = []
    files = sorted(TRIP_ROOT.rglob("*.zip"))
    manifest = []
    for path in files:
        manifest.append({
            "file": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")]
            if len(names) != 1:
                continue
            use = [
                "started_at", "start_station_name", "start_station_id",
                "member_casual", "rideable_type", "ride_id",
            ]
            d = pd.read_csv(z.open(names[0]), usecols=use, low_memory=False)
        d["date"] = pd.to_datetime(d["started_at"], errors="coerce").dt.floor("D")
        d = d[(d["date"] >= "2021-12-01") & (d["date"] <= "2025-12-31")].copy()
        d["station"] = d["start_station_name"].astype("string").str.strip()
        d["user"] = d["member_casual"].astype("string").fillna("unknown")
        d = d[d["date"].notna() & d["station"].notna() & (d["station"] != "")]
        daily = (
            d.groupby(["date", "user"], observed=True)
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        daily["rides"] = daily.drop(columns=["date"]).sum(axis=1)
        daily_parts.append(daily)
        station = (
            d.groupby(["date", "station", "user"], observed=True)
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        station["rides"] = station.drop(columns=["date", "station"]).sum(axis=1)
        station_parts.append(station)
        print(path.name, len(d), flush=True)
    city = pd.concat(daily_parts, ignore_index=True).groupby("date", as_index=False).sum(numeric_only=True)
    station = pd.concat(station_parts, ignore_index=True).groupby(
        ["date", "station"], as_index=False
    ).sum(numeric_only=True)
    (ROOT / "results" / "raw_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return city, station


def winter_id(index: pd.Series) -> pd.Series:
    return np.where(index.dt.month >= 11, index.dt.year + 1, index.dt.year)


def attach_weather(city: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    d = city.merge(weather, on="date", how="inner")
    d["winter"] = winter_id(d["date"])
    d["dow"] = d["date"].dt.dayofweek
    d["tmean"] = (d["TMAX"] + d["TMIN"]) / 2
    d["rain_state"] = (d["PRCP"] >= 1) & (d["SNOW"] < 1)
    d["snow_state"] = d["SNOW"] >= 1
    d["deep_snowpack"] = (d["SNWD"] >= 25) & (d["SNOW"] < 1) & (d["PRCP"] < 1)
    d["shallow_snowpack"] = (d["SNWD"] > 0) & (d["SNWD"] < 25) & (d["SNOW"] < 1) & (d["PRCP"] < 1)
    d["dry_clear"] = (d["PRCP"] < 1) & (d["SNOW"] < 1) & (d["SNWD"] < 1)
    return d.sort_values("date").reset_index(drop=True)


def add_baselines(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    dry = d[d["dry_clear"]].copy()
    for target in ["rides", "member", "casual"]:
        if target not in d:
            d[target] = 0
        base = dry.groupby(["winter", "dow"])[target].median().rename(f"{target}_base")
        d = d.join(base, on=["winter", "dow"])
        d[f"{target}_base"] = d[f"{target}_base"].fillna(d[target].median())
        d[f"{target}_ratio"] = (d[target] + 0.5) / (d[f"{target}_base"] + 0.5)
    d["mix"] = (d.get("casual", 0) + 0.5) / (d.get("member", 0) + 0.5)
    d["mix_base"] = (d["casual_base"] + 0.5) / (d["member_base"] + 0.5)
    d["mix_ratio"] = d["mix"] / d["mix_base"]
    return d


def event_catalog(d: pd.DataFrame) -> pd.DataFrame:
    flag = d["snow_state"]
    groups = (flag.ne(flag.shift()) | d["date"].diff().dt.days.ne(1)).cumsum()
    rows = []
    for _, block in d[flag].groupby(groups[flag]):
        start = block["date"].min()
        end = block["date"].max()
        amount = block["SNOW"].sum()
        if amount < 10:
            continue
        after = d[d["date"].between(end + pd.Timedelta(days=1), end + pd.Timedelta(days=7))]
        rows.append({
            "event": f"snow_{end.date()}",
            "start": start,
            "end": end,
            "winter": int(block["winter"].iloc[0]),
            "snow_total": float(amount),
            "peak_snow": float(block["SNOW"].max()),
            "peak_depth": float(block["SNWD"].max()),
            "end_depth": float(block["SNWD"].iloc[-1]),
            "temp_end": float(block["tmean"].iloc[-1]),
            "temp_plus3": float(after["tmean"].iloc[:3].mean()) if len(after) else np.nan,
        })
    return pd.DataFrame(rows)


def build_event_profiles(d: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    profiles = []
    for row in events.itertuples(index=False):
        days = d[d["date"].between(row.end + pd.Timedelta(days=1), row.end + pd.Timedelta(days=4))].copy()
        if len(days) < 2:
            continue
        for h, day in enumerate(days.itertuples(index=False), start=1):
            profiles.append({
                "event": row.event,
                "winter": row.winter,
                "h": h,
                "rides_ratio": day.rides_ratio,
                "member_ratio": day.member_ratio,
                "casual_ratio": day.casual_ratio,
                "mix_ratio": day.mix_ratio,
                "depth": day.SNWD,
                "tmean": day.tmean,
            })
    return pd.DataFrame(profiles)


def cluster_events(profiles: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    wide = profiles.pivot_table(index="event", columns="h", values=["rides_ratio", "mix_ratio"], aggfunc="mean")
    wide.columns = [f"{a}_h{b}" for a, b in wide.columns]
    wide = wide.dropna()
    if len(wide) < 6:
        return pd.DataFrame()
    x = StandardScaler().fit_transform(wide)
    scores = {}
    for k in (2, 3, 4):
        km = KMeans(n_clusters=k, random_state=20261115, n_init=30).fit(x)
        scores[k] = silhouette_score(x, km.labels_)
    k = max(scores, key=scores.get)
    km = KMeans(n_clusters=k, random_state=20261115, n_init=30).fit(x)
    out = wide.reset_index()
    out["cluster"] = km.labels_
    out = out.merge(events, on="event", how="left")
    out.to_csv(ROOT / "results" / "event_clusters.csv", index=False)
    (ROOT / "results" / "event_cluster_scores.json").write_text(
        json.dumps({"silhouette": scores, "chosen_k": k}, indent=2), encoding="utf-8"
    )
    return out


def station_profiles(station: pd.DataFrame, weather: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    s = station.merge(weather, on="date", how="inner")
    s["winter"] = winter_id(s["date"])
    s["dow"] = s["date"].dt.dayofweek
    s["dry_clear"] = (s["PRCP"] < 1) & (s["SNOW"] < 1) & (s["SNWD"] < 1)
    for target in ["rides", "member", "casual"]:
        base_name = f"{target}_base"
        base = s[s["dry_clear"]].groupby(["station", "winter", "dow"])[target].median().rename(base_name)
        s = s.join(base, on=["station", "winter", "dow"])
        s[base_name] = s[base_name].fillna(
            s.groupby(["station", "winter"])[target].transform("median")
        ).fillna(0)
        s[f"{target}_ratio"] = (s[target] + 0.5) / (s[base_name] + 0.5)
    rows = []
    for event in events.itertuples(index=False):
        dates = pd.date_range(event.end + pd.Timedelta(days=1), event.end + pd.Timedelta(days=4))
        x = s[s["date"].isin(dates)].copy()
        if x.empty:
            continue
        for station_name, g in x.groupby("station", observed=True):
            if g["rides_base"].mean() < 3:
                continue
            rec = {"station": station_name, "event": event.event, "winter": event.winter}
            for target in ["rides", "member", "casual"]:
                rec[f"{target}_ratio"] = g[f"{target}_ratio"].mean()
            rec["casual_share"] = g["casual"].sum() / max(g["rides"].sum(), 1)
            rec["baseline"] = g["rides_base"].mean()
            rows.append(rec)
    long = pd.DataFrame(rows)
    if long.empty:
        return long
    out = long.groupby("station", as_index=False).agg(
        rides_ratio=("rides_ratio", "mean"),
        member_ratio=("member_ratio", "mean"),
        casual_ratio=("casual_ratio", "mean"),
        casual_share=("casual_share", "mean"),
        baseline=("baseline", "mean"),
        events=("event", "nunique"),
    )
    feat = out[["rides_ratio", "member_ratio", "casual_ratio", "casual_share", "baseline"]].copy()
    x = StandardScaler().fit_transform(feat)
    km = KMeans(n_clusters=3, random_state=20261115, n_init=30).fit(x)
    out["cluster"] = km.labels_
    out.to_csv(ROOT / "results" / "station_recovery_clusters.csv", index=False)
    out.groupby("cluster").agg(
        stations=("station", "size"),
        rides_ratio=("rides_ratio", "mean"),
        member_ratio=("member_ratio", "mean"),
        casual_ratio=("casual_ratio", "mean"),
        casual_share=("casual_share", "mean"),
        baseline=("baseline", "mean"),
        events=("events", "mean"),
    ).to_csv(ROOT / "results" / "station_cluster_summary.csv")
    return out


def make_figures(d: pd.DataFrame, events: pd.DataFrame, event_clusters: pd.DataFrame, station_clusters: pd.DataFrame):
    plt.rcParams.update({"font.size": 10, "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(8, 4.5))
    state_order = ["dry_clear", "shallow_snowpack", "deep_snowpack", "snow_state", "rain_state"]
    labels = ["Clear", "Shallow snow", "Deep snow", "Snowing", "Rain"]
    vals = [d.loc[d[s], "casual_ratio"].median() for s in state_order]
    ax.bar(labels, vals, color=["#9ecae1", "#74c476", "#238b45", "#6baed6", "#fdae6b"])
    ax.axhline(1, color="#555", ls="--", lw=1)
    ax.set_ylabel("Casual/member ratio")
    ax.set_title("User composition by weather state")
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "01_weather_states.png", dpi=180)
    plt.close(fig)

    if not event_clusters.empty:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
        for cluster, g in event_clusters.groupby("cluster"):
            cols = [c for c in g.columns if c.startswith("rides_ratio_h")]
            ys = g[cols].mean().to_numpy()
            axes[0].plot(range(1, len(ys) + 1), ys, marker="o", label=f"Event type {cluster}")
            cols = [c for c in g.columns if c.startswith("mix_ratio_h")]
            ys = g[cols].mean().to_numpy()
            axes[1].plot(range(1, len(ys) + 1), ys, marker="o", label=f"Event type {cluster}")
        for ax, title in zip(axes, ["Total rides recovery", "Casual/member recovery"]):
            ax.axhline(1, color="#555", ls="--", lw=1)
            ax.set_xlabel("Days after snowfall")
            ax.set_ylabel("Relative to dry baseline")
            ax.set_title(title)
            ax.legend()
        fig.tight_layout()
        fig.savefig(ROOT / "figures" / "02_event_recovery_clusters.png", dpi=180)
        plt.close(fig)

    if not station_clusters.empty:
        summary = station_clusters.groupby("cluster")[["rides_ratio", "member_ratio", "casual_ratio"]].mean()
        summary.plot(kind="bar", figsize=(8, 4), color=["#3979a8", "#167d63", "#bb7621"])
        plt.axhline(1, color="#555", ls="--", lw=1)
        plt.ylabel("Relative recovery ratio, days 1-4")
        plt.xlabel("Station recovery type")
        plt.title("Station recovery types after snowfall")
        plt.legend(["Total rides", "Members", "Casual users"])
        plt.tight_layout()
        plt.savefig(ROOT / "figures" / "03_station_recovery_clusters.png", dpi=180)
        plt.close()


def main():
    weather = load_weather()
    city, station = load_trips()
    city = attach_weather(city, weather)
    city = add_baselines(city)
    events = event_catalog(city)
    profiles = build_event_profiles(city, events)
    event_clusters = cluster_events(profiles, events)
    station_clusters = station_profiles(station, weather, events)
    city.to_csv(ROOT / "data" / "city_daily.csv", index=False)
    station.to_csv(ROOT / "data" / "station_daily.csv", index=False)
    events.to_csv(ROOT / "results" / "snow_events.csv", index=False)
    profiles.to_csv(ROOT / "results" / "event_profiles.csv", index=False)
    make_figures(city, events, event_clusters, station_clusters)
    summary = {
        "city_days": int(len(city)),
        "weather_days": int(len(weather)),
        "station_rows": int(len(station)),
        "stations": int(station["station"].nunique()),
        "snow_events": int(len(events)),
        "event_profile_rows": int(len(profiles)),
        "event_clusters": int(event_clusters["cluster"].nunique()) if not event_clusters.empty else 0,
        "station_clusters": int(station_clusters["cluster"].nunique()) if not station_clusters.empty else 0,
    }
    (ROOT / "results" / "extended_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
