from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
DATA = ROOT / "data"
FIGURES = ROOT / "figures-final"
FONT_CANDIDATES = [
    ROOT / "assets/fonts/NotoSansSC-Regular.ttf",
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
]
FONT_PATH = next((path for path in FONT_CANDIDATES if path.exists()), None)
if FONT_PATH is None:
    raise RuntimeError("A Chinese-capable system font is required to render the figures.")

CJK = FontProperties(fname=str(FONT_PATH))
INK = "#18322D"
GREEN = "#287A71"
ORANGE = "#D9822B"
BLUE = "#3C78A8"
MUTED = "#596B65"

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.unicode_minus": False,
})


def make_event_recovery_figure() -> None:
    city = pd.read_csv(RESULTS / "event_matched_city_recovery.csv")
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    state_colors = {"present": ORANGE, "absent": GREEN}
    state_labels = {"present": "仍有残雪", "absent": "无残雪"}
    targets = [
        ("rides_ratio", "总骑行量", ":"),
        ("member_ratio", "会员", "--"),
        ("casual_ratio", "临时用户", "-"),
    ]

    for state in ["present", "absent"]:
        subset = city[city["snowpack_state"].eq(state)]
        if subset.empty:
            continue
        for target, target_label, line_style in targets:
            event_means = subset.groupby(["event_id", "h"])[target].mean().reset_index()
            grouped = event_means.groupby("h")[target].mean().reset_index()
            ax.plot(
                grouped["h"],
                grouped[target],
                marker="o",
                color=state_colors[state],
                linestyle=line_style,
                label=f"{target_label}（{state_labels[state]}）",
            )

    ax.axhline(1.0, color=MUTED, linewidth=1, linestyle="--")
    ax.set(
        xlabel="降雪结束后的天数",
        ylabel="实际骑行量 / 匹配晴朗日基准",
        xticks=range(1, 8),
    )
    ax.set_title("雪停后 1 至 7 天的骑行恢复比例", loc="left", color=INK, fontweight="bold", fontproperties=CJK)
    ax.xaxis.label.set_fontproperties(CJK)
    ax.yaxis.label.set_fontproperties(CJK)
    ax.legend(frameon=False, ncol=2, fontsize=8, prop=CJK)
    ax.grid(axis="y", color="#e5ebe7", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(FIGURES / "01_event_recovery_curves.png", dpi=220)
    plt.close(fig)


def make_station_map() -> None:
    clusters = pd.read_csv(RESULTS / "station_recovery_clusters.csv")
    metadata = pd.read_csv(DATA / "station_metadata.csv")
    points = clusters.merge(metadata, on="station_id", how="left", suffixes=("", "_meta"))
    points = points[points["lat"].notna() & points["lon"].notna()]
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    palette = [GREEN, ORANGE, BLUE]

    for cluster in sorted(points["cluster"].unique()):
        subset = points[points["cluster"].eq(cluster)]
        ax.scatter(
            subset["lon"],
            subset["lat"],
            s=8,
            alpha=0.7,
            color=palette[int(cluster) % len(palette)],
            label=f"类型 {int(cluster) + 1}",
            linewidths=0,
        )

    ax.set_xlabel("经度", fontproperties=CJK)
    ax.set_ylabel("纬度", fontproperties=CJK)
    ax.set_title("芝加哥 Divvy 站点恢复类型", color=INK, fontweight="bold", fontproperties=CJK)
    ax.legend(frameon=False, prop=CJK)
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(color="#e5ebe7", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(FIGURES / "02_station_recovery_types_map.png", dpi=220)
    plt.close(fig)


def make_forecast_figure() -> None:
    predictions = pd.read_csv(RESULTS / "gru_test_predictions.csv", parse_dates=["date"])
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    columns = ["rides", "member", "casual"]
    titles = ["总骑行量", "会员骑行量", "临时用户骑行量"]
    labels = {
        "GRU: lagged weather": "GRU：历史天气",
        "GRU: day-ahead forecast": "GRU：前一日天气预报",
        "Previous week": "上周同日",
        "Month + weekday median": "月份＋星期中位数",
    }
    palette = {
        "GRU: lagged weather": GREEN,
        "GRU: day-ahead forecast": ORANGE,
        "Previous week": "#777777",
        "Month + weekday median": BLUE,
    }

    for axis, target, title in zip(axes, columns, titles):
        axis.plot(predictions["date"], predictions[f"gt_{target}"], color=INK, linewidth=1.7, label="实际")
        for model, color in palette.items():
            axis.plot(
                predictions["date"],
                predictions[f"pred_{model}_{target}"],
                color=color,
                linewidth=1.15,
                alpha=0.9,
                label=labels[model],
            )
        axis.set_ylabel("每日骑行量", fontproperties=CJK)
        axis.set_title(title, loc="left", fontsize=11, fontweight="bold", fontproperties=CJK)
        axis.grid(axis="y", color="#e4e9e6", linewidth=0.7)

    axes[-1].set_xlabel("日期（2024-25 留出冬季）", fontproperties=CJK)
    axes[0].legend(ncol=3, frameon=False, fontsize=8, loc="upper right", prop=CJK)
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    fig.savefig(FIGURES / "03_winter_test_predictions.png", dpi=220)
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    make_event_recovery_figure()
    make_station_map()
    make_forecast_figure()


if __name__ == "__main__":
    main()
