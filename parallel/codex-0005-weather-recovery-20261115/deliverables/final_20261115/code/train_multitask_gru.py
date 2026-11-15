from __future__ import annotations

import json
import math
import random
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


PROJECT = Path("/root/autodl-tmp/ai-sci")
TASK = PROJECT / "parallel/codex-0005-weather-recovery-20261115"
PROC = TASK / "data/final_20261115"
OUT = TASK / "results/final_20261115"
FIG = TASK / "figures/final_20261115"
TARGETS = ["rides", "member", "casual"]
SEQUENCE_FEATURES = ["rides", "member", "casual", "tmean_c", "PRCP", "SNOW", "SNWD", "AWND"]
FORECAST_FEATURES = ["forecast_tmean_c", "forecast_tmin_c", "forecast_tmax_c", "forecast_qpf_mm", "forecast_snow_cm"]
WINDOW = 14
SEED = 20261115


class MultiTaskGRU(nn.Module):
    def __init__(self, sequence_features: int, static_features: int, hidden_size: int = 32):
        super().__init__()
        self.encoder = nn.GRU(sequence_features, hidden_size, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden_size + static_features, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, len(TARGETS)),
        )

    def forward(self, sequence: torch.Tensor, static: torch.Tensor) -> torch.Tensor:
        _, hidden = self.encoder(sequence)
        return self.head(torch.cat([hidden[-1], static], dim=1))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def feature_rows() -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    city = pd.read_csv(PROC / "city_daily.csv", parse_dates=["date"])
    forecast = pd.read_csv(PROC / "ndfd_daily_forecasts.csv", parse_dates=["date"])
    data = city.merge(forecast, on="date", how="left", validate="one_to_one")
    data = data.sort_values(["winter", "date"]).reset_index(drop=True)
    data["dow_sin"] = np.sin(data["dow"] * 2 * np.pi / 7)
    data["dow_cos"] = np.cos(data["dow"] * 2 * np.pi / 7)
    data["month_sin"] = np.sin(data["month"] * 2 * np.pi / 12)
    data["month_cos"] = np.cos(data["month"] * 2 * np.pi / 12)
    calendar_features = ["dow_sin", "dow_cos", "month_sin", "month_cos", "is_holiday"]
    data["is_holiday"] = data["is_holiday"].astype(float)
    for target in ["rides", "member", "casual"]:
        data[target] = np.log1p(data[target].clip(lower=0))
    for field in ["PRCP", "SNOW", "SNWD", "AWND", "tmean_c"]:
        data[field] = pd.to_numeric(data[field], errors="coerce")
    data[SEQUENCE_FEATURES] = data[SEQUENCE_FEATURES].replace([np.inf, -np.inf], np.nan)
    data[SEQUENCE_FEATURES] = data.groupby("winter")[SEQUENCE_FEATURES].transform(lambda group: group.ffill()).fillna(0)
    data[FORECAST_FEATURES] = data[FORECAST_FEATURES].replace([np.inf, -np.inf], np.nan)

    sequences = []
    static_calendar = []
    static_forecasts = []
    targets = []
    records = []
    for winter, group in data.groupby("winter", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        sequence_values = group[SEQUENCE_FEATURES].to_numpy(dtype=np.float32)
        outcome_values = np.expm1(group[TARGETS].to_numpy(dtype=np.float32))
        for position in range(WINDOW, len(group)):
            row = group.iloc[position]
            sequences.append(sequence_values[position - WINDOW:position])
            static_calendar.append(row[calendar_features].to_numpy(dtype=np.float32))
            static_forecasts.append(row[FORECAST_FEATURES].to_numpy(dtype=np.float32))
            targets.append(np.log1p(outcome_values[position]))
            records.append({
                "date": row["date"],
                "winter": int(winter),
                "month": int(row["month"]),
                "dow": int(row["dow"]),
                "gt_rides": float(outcome_values[position, 0]),
                "gt_member": float(outcome_values[position, 1]),
                "gt_casual": float(outcome_values[position, 2]),
                "forecast_complete": bool(np.isfinite(static_forecasts[-1]).all()),
            })
    arrays = {
        "sequence": np.asarray(sequences, dtype=np.float32),
        "calendar": np.asarray(static_calendar, dtype=np.float32),
        "forecast": np.asarray(static_forecasts, dtype=np.float32),
        "target_log": np.asarray(targets, dtype=np.float32),
    }
    metadata = pd.DataFrame(records)
    return arrays, metadata


def standardize(train: np.ndarray, *others: np.ndarray) -> tuple[np.ndarray, ...]:
    axes = tuple(range(train.ndim - 1))
    mean = np.nanmean(train, axis=axes, keepdims=True)
    scale = np.nanstd(train, axis=axes, keepdims=True)
    scale = np.where(scale < 1e-6, 1.0, scale)
    return tuple(((value - mean) / scale).astype(np.float32) for value in (train, *others)) + (mean, scale)


def target_standardize(train: np.ndarray, *others: np.ndarray) -> tuple[np.ndarray, ...]:
    mean = np.mean(train, axis=0, keepdims=True)
    scale = np.std(train, axis=0, keepdims=True)
    scale = np.where(scale < 1e-6, 1.0, scale)
    return tuple(((value - mean) / scale).astype(np.float32) for value in (train, *others)) + (mean, scale)


def make_model_data(arrays: dict[str, np.ndarray], metadata: pd.DataFrame, version: str) -> dict:
    complete_mask = metadata["forecast_complete"].to_numpy(dtype=bool)
    keep = np.flatnonzero(complete_mask)
    rows = metadata.loc[complete_mask].copy().reset_index(drop=True)
    sequence = arrays["sequence"][keep]
    calendar = arrays["calendar"][keep]
    forecast = arrays["forecast"][keep]
    target = arrays["target_log"][keep]
    train_mask = rows["winter"].isin([2022, 2023]).to_numpy()
    validation_mask = rows["winter"].eq(2024).to_numpy()
    final_train_mask = rows["winter"].isin([2022, 2023, 2024]).to_numpy()
    test_mask = rows["winter"].eq(2025).to_numpy()
    context = calendar if version == "lagged_weather" else np.concatenate([calendar, forecast], axis=1)

    x_train, x_val, _, _ = standardize(sequence[train_mask], sequence[validation_mask])
    c_train, c_val, _, _ = standardize(context[train_mask], context[validation_mask])
    y_train, y_val, _, _ = target_standardize(target[train_mask], target[validation_mask])

    seq_train_final, seq_test_final, _, _ = standardize(sequence[final_train_mask], sequence[test_mask])
    context_train_final, context_test_final, _, _ = standardize(context[final_train_mask], context[test_mask])
    target_train_final, target_test_final, y_mean, y_scale = target_standardize(target[final_train_mask], target[test_mask])
    return {
        "rows": rows,
        "train_mask": train_mask,
        "validation_mask": validation_mask,
        "final_train_mask": final_train_mask,
        "test_mask": test_mask,
        "x_train": x_train,
        "c_train": c_train,
        "y_train": y_train,
        "x_val": x_val,
        "c_val": c_val,
        "y_val": y_val,
        "x_train_final": seq_train_final,
        "c_train_final": context_train_final,
        "y_train_final": target_train_final,
        "x_test_final": seq_test_final,
        "c_test_final": context_test_final,
        "y_test_final": target_test_final,
        "y_mean": y_mean,
        "y_scale": y_scale,
        "gt_test": rows.loc[test_mask, ["gt_rides", "gt_member", "gt_casual"]].to_numpy(dtype=float),
        "test_metadata": rows.loc[test_mask].reset_index(drop=True),
    }


def tensor_loader(sequence: np.ndarray, context: np.ndarray, target: np.ndarray, shuffle: bool) -> DataLoader:
    tensors = TensorDataset(
        torch.from_numpy(sequence),
        torch.from_numpy(context),
        torch.from_numpy(target),
    )
    return DataLoader(tensors, batch_size=32, shuffle=shuffle, drop_last=False)


def train_epoch(model: nn.Module, loader: DataLoader, optimizer: torch.optim.Optimizer, device: torch.device) -> float:
    model.train()
    loss_function = nn.HuberLoss(delta=1.0)
    losses = []
    for sequence, context, target in loader:
        sequence, context, target = sequence.to(device), context.to(device), target.to(device)
        optimizer.zero_grad(set_to_none=True)
        prediction = model(sequence, context)
        loss = loss_function(prediction, target)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    return float(np.mean(losses))


def evaluate_loss(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    loss_function = nn.HuberLoss(delta=1.0)
    losses = []
    with torch.no_grad():
        for sequence, context, target in loader:
            sequence, context, target = sequence.to(device), context.to(device), target.to(device)
            losses.append(float(loss_function(model(sequence, context), target).cpu()))
    return float(np.mean(losses))


def select_epoch_count(data: dict, version: str, device: torch.device) -> tuple[int, list[dict]]:
    train_loader = tensor_loader(data["x_train"], data["c_train"], data["y_train"], shuffle=True)
    val_loader = tensor_loader(data["x_val"], data["c_val"], data["y_val"], shuffle=False)
    set_seed(SEED)
    model = MultiTaskGRU(data["x_train"].shape[-1], data["c_train"].shape[-1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.004, weight_decay=1e-4)
    best_loss = math.inf
    best_epoch = 1
    wait = 0
    history = []
    for epoch in range(1, 251):
        training_loss = train_epoch(model, train_loader, optimizer, device)
        validation_loss = evaluate_loss(model, val_loader, device)
        history.append({"model": version, "phase": "validation", "epoch": epoch, "train_loss": training_loss, "validation_loss": validation_loss})
        if validation_loss < best_loss - 1e-5:
            best_loss = validation_loss
            best_epoch = epoch
            wait = 0
        else:
            wait += 1
        if wait >= 30:
            break
    return best_epoch, history


def fit_final(data: dict, version: str, epochs: int, device: torch.device) -> np.ndarray:
    loader = tensor_loader(data["x_train_final"], data["c_train_final"], data["y_train_final"], shuffle=True)
    set_seed(SEED)
    model = MultiTaskGRU(data["x_train_final"].shape[-1], data["c_train_final"].shape[-1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.004, weight_decay=1e-4)
    history = []
    for epoch in range(1, epochs + 1):
        training_loss = train_epoch(model, loader, optimizer, device)
        history.append({"model": version, "phase": "final_fit", "epoch": epoch, "train_loss": training_loss, "validation_loss": np.nan})
    model.eval()
    with torch.no_grad():
        predicted_scaled = model(torch.from_numpy(data["x_test_final"]).to(device), torch.from_numpy(data["c_test_final"]).to(device)).cpu().numpy()
    predicted_log = predicted_scaled * data["y_scale"] + data["y_mean"]
    prediction = np.expm1(predicted_log).clip(min=0)
    return prediction, history


def metric_rows(model_name: str, truth: np.ndarray, prediction: np.ndarray) -> list[dict]:
    rows = []
    for index, target in enumerate(TARGETS):
        gt = truth[:, index]
        pred = prediction[:, index]
        nonzero = gt > 0
        signed = (gt[nonzero] - pred[nonzero]) / gt[nonzero]
        rows.append({
            "model": model_name,
            "target": target,
            "n_days": int(len(gt)),
            "mae_rides": float(np.mean(np.abs(gt - pred))),
            "rmse_rides": float(np.sqrt(np.mean(np.square(gt - pred)))),
            "wape": float(np.sum(np.abs(gt - pred)) / max(np.sum(gt), 1)),
            "mean_signed_relative_error_gt_minus_pred": float(np.mean(signed)) if len(signed) else np.nan,
            "pooled_signed_relative_error_gt_minus_pred": float(np.sum(gt - pred) / max(np.sum(gt), 1)),
            "test_start": str(pd.Timestamp.min.date()) if len(gt) == 0 else "",
        })
    return rows


def make_figure(predictions: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    columns = ["rides", "member", "casual"]
    titles = ["Total rides", "Members", "Casual riders"]
    palette = {"GRU: lagged weather": "#287a71", "GRU: day-ahead forecast": "#d9822b", "Previous week": "#777777", "Month + weekday median": "#3c78a8"}
    for axis, target, title in zip(axes, columns, titles):
        axis.plot(predictions["date"], predictions[f"gt_{target}"], color="#1d2723", linewidth=1.7, label="Observed")
        for model, color in palette.items():
            axis.plot(predictions["date"], predictions[f"pred_{model}_{target}"], color=color, linewidth=1.15, alpha=0.9, label=model)
        axis.set_ylabel("Daily rides")
        axis.set_title(title, loc="left", fontsize=11, fontweight="bold")
        axis.grid(axis="y", color="#e4e9e6", linewidth=0.7)
    axes[-1].set_xlabel("Held-out winter 2024-25")
    axes[0].legend(ncol=3, frameon=False, fontsize=8, loc="upper right")
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    fig.savefig(FIG / "03_winter_test_predictions.png", dpi=200)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    set_seed(SEED)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.cuda.set_per_process_memory_fraction(0.08, device=device)
        torch.cuda.empty_cache()
    arrays, metadata = feature_rows()
    available = metadata["forecast_complete"].sum()
    if available < 100:
        raise RuntimeError(f"Only {available} complete target-day forecasts are available for training and evaluation")
    all_predictions = None
    metrics = []
    histories = []
    chosen_epochs = {}
    for version in ["lagged_weather", "forecast_aware"]:
        data = make_model_data(arrays, metadata, version)
        if data["x_train"].shape[0] < 100 or data["x_val"].shape[0] < 50 or data["x_test_final"].shape[0] < 50:
            raise RuntimeError(f"Insufficient whole-winter samples for {version}: train={len(data['x_train'])}, val={len(data['x_val'])}, test={len(data['x_test_final'])}")
        best_epoch, history = select_epoch_count(data, version, device)
        prediction, final_history = fit_final(data, version, best_epoch, device)
        histories.extend(history + final_history)
        chosen_epochs[version] = best_epoch
        rows = metric_rows(f"GRU: {'lagged weather' if version == 'lagged_weather' else 'day-ahead forecast'}", data["gt_test"], prediction)
        for row in rows:
            row["n_days"] = len(data["test_metadata"])
            row["test_start"] = data["test_metadata"]["date"].min().date().isoformat()
            row["test_end"] = data["test_metadata"]["date"].max().date().isoformat()
            row["selected_epochs"] = best_epoch
        metrics.extend(rows)
        predictions = data["test_metadata"][["date", "winter"]].copy()
        for index, target in enumerate(TARGETS):
            predictions[f"gt_{target}"] = data["gt_test"][:, index]
            predictions[f"pred_{'GRU: lagged weather' if version == 'lagged_weather' else 'GRU: day-ahead forecast'}_{target}"] = prediction[:, index]
        if all_predictions is None:
            all_predictions = predictions
        else:
            all_predictions = all_predictions.merge(predictions.drop(columns=["winter"]), on=["date", *[f"gt_{target}" for target in TARGETS]], how="inner", validate="one_to_one")
        del data
        if device.type == "cuda":
            torch.cuda.empty_cache()

    test_dates = all_predictions["date"]
    city = pd.read_csv(PROC / "city_daily.csv", parse_dates=["date"])
    train_days = city[city["winter"].isin([2022, 2023, 2024])]
    test = city[city["date"].isin(test_dates)].copy().sort_values("date")
    baseline_weekday = train_days.assign(month=train_days["date"].dt.month, dow=train_days["date"].dt.day_of_week).groupby(["month", "dow"])[TARGETS].median()
    baseline_predictions = []
    for row in test.itertuples(index=False):
        key = (int(row.date.month), int(row.date.day_of_week))
        baseline = baseline_weekday.loc[key] if key in baseline_weekday.index else train_days[TARGETS].median()
        baseline_predictions.append([float(baseline[target]) for target in TARGETS])
    baseline_predictions = np.asarray(baseline_predictions)
    truth = test[TARGETS].to_numpy(dtype=float)
    previous_week = city.set_index("date")[TARGETS].reindex(test["date"] - pd.Timedelta(days=7)).to_numpy(dtype=float)
    if np.isnan(previous_week).any():
        previous_week = np.where(np.isnan(previous_week), baseline_predictions, previous_week)
    metrics.extend(metric_rows("Month + weekday median", truth, baseline_predictions))
    metrics.extend(metric_rows("Previous week", truth, previous_week))
    for row in metrics:
        row["n_days"] = len(test)
        row["test_start"] = test["date"].min().date().isoformat()
        row["test_end"] = test["date"].max().date().isoformat()
    month_cols = ["gt_rides", "gt_member", "gt_casual"]
    all_predictions = all_predictions.sort_values("date").reset_index(drop=True)
    all_predictions["pred_Previous week_rides"] = previous_week[:, 0]
    all_predictions["pred_Previous week_member"] = previous_week[:, 1]
    all_predictions["pred_Previous week_casual"] = previous_week[:, 2]
    all_predictions["pred_Month + weekday median_rides"] = baseline_predictions[:, 0]
    all_predictions["pred_Month + weekday median_member"] = baseline_predictions[:, 1]
    all_predictions["pred_Month + weekday median_casual"] = baseline_predictions[:, 2]
    all_predictions.to_csv(OUT / "gru_test_predictions.csv", index=False)
    pd.DataFrame(metrics).to_csv(OUT / "gru_metrics.csv", index=False)
    pd.DataFrame(histories).to_csv(OUT / "gru_training_history.csv", index=False)
    make_figure(all_predictions)
    write = {
        "architecture": "single-layer GRU, 32 hidden units, shared three-output regression head",
        "targets": TARGETS,
        "sequence_length_days": WINDOW,
        "sequence_inputs": SEQUENCE_FEATURES,
        "static_calendar_inputs": ["weekday sine/cosine", "month sine/cosine", "US federal holiday"],
        "forecast_inputs": FORECAST_FEATURES,
        "split": {"train": [2022, 2023], "validation_for_epoch_selection": [2024], "final_fit": [2022, 2023, 2024], "test": [2025]},
        "sample_counts": {str(winter): int(count) for winter, count in metadata[metadata["forecast_complete"]].groupby("winter").size().items()},
        "test_days": len(test),
        "test_period": [test["date"].min().date().isoformat(), test["date"].max().date().isoformat()],
        "selected_epochs": chosen_epochs,
        "device": str(device),
        "gpu_memory_cap_fraction": 0.08 if device.type == "cuda" else None,
        "seed": SEED,
        "metrics_definition": {
            "WAPE": "sum(abs(GT-prediction))/sum(GT)",
            "mean_signed_relative_error": "mean((GT-prediction)/GT) for GT>0; positive means underprediction",
            "pooled_signed_relative_error": "sum(GT-prediction)/sum(GT)",
        },
        "forecast_version": "target-day NDFD forecast issued no later than noon local time on the prior day",
    }
    (OUT / "gru_config.json").write_text(json.dumps(write, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(write, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
