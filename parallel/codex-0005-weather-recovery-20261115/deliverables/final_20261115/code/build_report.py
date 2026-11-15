from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from matplotlib.font_manager import FontProperties
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures-final"
OUT = ROOT / "weather-recovery-final-report-v2.pdf"
FONT = ROOT / "assets/fonts/NotoSansSC-Regular.ttf"
SEED = 20261115

pdfmetrics.registerFont(TTFont("CJK", str(FONT)))
CJK_FONT = FontProperties(fname=str(FONT))
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

GREEN = "#287a71"
ORANGE = "#d9822b"
INK = "#18322d"
MUTED = "#586862"
LINE = "#d9e2de"


def load_json(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def paragraph(text: str, style: str = "BodyCJK") -> Paragraph:
    return Paragraph(text, styles[style])


def make_residual_snow_figure(city: pd.DataFrame) -> None:
    rng = np.random.default_rng(SEED)
    targets = ["rides_ratio", "member_ratio", "casual_ratio"]
    labels = ["全部骑行", "会员", "临时用户"]
    colors_by_target = [INK, GREEN, ORANGE]
    fig, ax = plt.subplots(figsize=(8.8, 4.1))
    states = ["absent", "present"]
    state_labels = ["无残雪", "仍有残雪"]
    offsets = [-0.16, 0.0, 0.16]
    for state_index, (state, state_label) in enumerate(zip(states, state_labels)):
        event_values = city[city["snowpack_state"].eq(state)].groupby("event_id")[targets].mean()
        x_base = state_index
        for target_index, (target, label, color) in enumerate(zip(targets, labels, colors_by_target)):
            values = event_values[target].dropna().to_numpy()
            draws = np.array([
                rng.choice(values, size=len(values), replace=True).mean()
                for _ in range(5000)
            ])
            low, high = np.quantile(draws, [0.025, 0.975])
            mean = float(values.mean())
            x = x_base + offsets[target_index]
            ax.errorbar(
                x,
                mean,
                yerr=[[mean - low], [high - mean]],
                fmt="o",
                color=color,
                capsize=4,
                markersize=7,
                linewidth=1.7,
                label=label if state_index == 0 else None,
            )
    ax.axhline(1.0, color="#71817b", linestyle="--", linewidth=1.1)
    ax.set_xticks([0, 1], state_labels, fontproperties=CJK_FONT)
    ax.set_ylabel("实际骑行量 / 匹配晴朗日基准", fontproperties=CJK_FONT)
    ax.set_ylim(0.35, 1.15)
    ax.grid(axis="y", color="#e4e9e6", linewidth=0.7)
    ax.legend(frameon=False, ncol=3, loc="upper center", prop=CJK_FONT)
    ax.set_title("残雪状态下的骑行恢复比例", loc="left", color=INK, weight="bold", fontproperties=CJK_FONT)
    fig.tight_layout()
    fig.savefig(FIGURES / "04_residual_snow_comparison.png", dpi=220)
    plt.close(fig)


def build_styles() -> None:
    global styles
    styles = getSampleStyleSheet()
    base = styles
    styles.add(ParagraphStyle(
        name="TitleCJK",
        parent=base["Title"],
        fontName="CJK",
        fontSize=25,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor(INK),
        spaceAfter=13,
    ))
    styles.add(ParagraphStyle(
        name="SubtitleCJK",
        parent=base["Normal"],
        fontName="CJK",
        fontSize=11,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor(MUTED),
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="H1CJK",
        parent=base["Heading1"],
        fontName="CJK",
        fontSize=16,
        leading=22,
        textColor=colors.HexColor(INK),
        spaceBefore=8,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="H2CJK",
        parent=base["Heading2"],
        fontName="CJK",
        fontSize=11.5,
        leading=17,
        textColor=colors.HexColor(GREEN),
        spaceBefore=8,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="BodyCJK",
        parent=base["BodyText"],
        fontName="CJK",
        fontSize=8.8,
        leading=14,
        textColor=colors.HexColor("#1d2b27"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SmallCJK",
        parent=base["BodyText"],
        fontName="CJK",
        fontSize=7.2,
        leading=10.5,
        textColor=colors.HexColor(MUTED),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="CalloutCJK",
        parent=base["BodyText"],
        fontName="CJK",
        fontSize=10,
        leading=16,
        textColor=colors.HexColor(INK),
        backColor=colors.HexColor("#e7f1ec"),
        borderColor=colors.HexColor(GREEN),
        borderWidth=0.8,
        borderPadding=9,
        spaceBefore=5,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="TableCJK",
        parent=base["BodyText"],
        fontName="CJK",
        fontSize=7.0,
        leading=9.6,
        textColor=colors.HexColor("#1d2b27"),
    ))
    styles.add(ParagraphStyle(
        name="CaptionCJK",
        parent=base["BodyText"],
        fontName="CJK",
        fontSize=7.1,
        leading=10,
        textColor=colors.HexColor(MUTED),
        spaceBefore=3,
        spaceAfter=7,
    ))


def make_table(rows: list[list[Paragraph]], widths: list[float], header_color: str = "#e7f1ec") -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(LINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor(LINE))
    canvas.line(1.55 * cm, 1.28 * cm, A4[0] - 1.55 * cm, 1.28 * cm)
    canvas.setFont("CJK", 7)
    canvas.setFillColor(colors.HexColor(MUTED))
    canvas.drawString(1.55 * cm, 0.82 * cm, "Divvy × NOAA  雨雪冲击后的共享单车恢复")
    canvas.drawRightString(A4[0] - 1.55 * cm, 0.82 * cm, str(doc.page))
    canvas.restoreState()


def main() -> None:
    build_styles()
    FIGURES.mkdir(parents=True, exist_ok=True)
    cleaning = load_json("data_cleaning_summary.json")
    weather = load_json("weather_coverage_summary.json")
    stage_a = load_json("stage_a_summary.json")
    event_validation = load_json("event_cluster_validation_summary.json")
    station_validation = load_json("station_cluster_validation_summary.json")
    hierarchy = load_json("hierarchical_model_status.json")
    spatial = load_json("station_spatial_model_status.json")
    area_spatial = load_json("station_community_area_model_status.json")
    forecast = load_json("ndfd_feature_summary.json")
    gru_config = load_json("gru_config.json")

    city = pd.read_csv(RESULTS / "event_matched_city_recovery.csv")
    event_profiles = pd.read_csv(RESULTS / "event_cluster_profiles.csv")
    event_clusters = pd.read_csv(RESULTS / "event_clusters.csv")
    station_profiles = pd.read_csv(RESULTS / "station_cluster_summary.csv")
    event_effects = pd.read_csv(RESULTS / "hierarchical_model_coefficients.csv").set_index("term")
    robust_effects = pd.read_csv(RESULTS / "event_cluster_robust_regression.csv").set_index("term")
    gru_metrics = pd.read_csv(RESULTS / "gru_metrics.csv")
    make_residual_snow_figure(city)

    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.55 * cm,
        rightMargin=1.55 * cm,
        topMargin=1.45 * cm,
        bottomMargin=1.6 * cm,
        title="雨雪冲击后的共享单车恢复机制研究",
        author="AI-SCI project",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="report", frames=frame, onPage=header_footer)])
    story = []

    story.extend([
        Spacer(1, 1.05 * cm),
        paragraph("雪停以后，谁先回来？", "TitleCJK"),
        paragraph("芝加哥 Divvy 雨雪天气下的需求恢复、用户差异与预测实验", "SubtitleCJK"),
        paragraph("研究阶段报告  |  2026 年 11 月 15 日", "SmallCJK"),
        Spacer(1, 0.45 * cm),
        paragraph(
            "<b>一句话结论</b>　雪停以后，地面残留积雪越深，临时用户相对平常天气的骑行恢复越弱。"
            "在按相同冬季、星期几、节假日状态和相近气温挑选晴朗对照，并控制雪后时间、温度、降雨和风速后，"
            "这种关系仍然存在，且对临时用户更明显。一个按整季留出的 GRU 实验还显示，前一天可获得的天气预报"
            "能改善总骑行量、会员和临时用户的预测。",
            "CalloutCJK",
        ),
        paragraph("这份报告回答什么", "H2CJK"),
        paragraph(
            "报告沿着“清理数据、发现问题、做额外验证”的顺序展开。我们先观察 2021-22 至 2024-25 四个冬季的"
            "雪后恢复，再检查事件和站点分组是否能跨冬季重现，随后用 GRU 检验真实可用的天气预报能否帮助预测。"
            "所有数字都来自本轮生成的结果表和脚本。",
        ),
        PageBreak(),
    ])

    story.extend([
        paragraph("1. 数据与研究问题", "H1CJK"),
        paragraph(
            f"分析覆盖四个冬季、{cleaning['study_dates']} 个日期，时间范围为 2021 年 12 月 1 日至 2025 年 3 月 31 日。"
            f"我们读取 {cleaning['input_rows']:,} 条 Divvy 原始行程，保留研究窗口内 {cleaning['clean_rows']:,} 条。"
            f"其中 {cleaning['rows_without_station']:,} 条没有可用起点站标识，仍计入城市总量，但不进入站点分析。"
            f"站点日表包含 {cleaning['station_day_records']:,} 条记录。"
        ),
        paragraph(
            f"NOAA O’Hare 日天气表包含 {weather['study_days']} 天，降水、新雪、积雪深度、风速、最高温和最低温均无整日缺失。"
            f"为模拟运营者在前一天做准备，我们还下载了 {forecast['usable_product_files']:,} 份历史天气预报，"
            f"三类预报覆盖 {forecast['dates_with_all_three_daily_products']} 天。每份预报均在目标日前一天芝加哥中午前发布。"
        ),
        paragraph(
            "本轮主实验聚焦降雪结束后的残雪恢复。降雨作为模型控制变量，并未另行建立雨后恢复事件分类。"
            "行程取自 Divvy 官方历史行程档案，下载日期为 2026 年 11 月 15 日；日天气取自 NOAA O’Hare 站点 "
            "USW00094846；提前一天的天气信息取自 NOAA 数字预报网格历史预报。原始行程按数据使用条款留在服务器数据盘，未放入交付副本。"
        ),
        paragraph("可验证假设", "H2CJK"),
        paragraph(
            "在降雪结束后的无新雪日期，残余积雪越深，临时用户相对会员的骑行恢复比例越低。"
            "这里的“低”是与同冬季中星期几、节假日状态相同、气温相近的干燥无雪日相比。"
            "数据是观察性记录，因此实验可以检验这个关系是否持续出现，不能单独证明积雪造成了变化。"
        ),
        paragraph("怎样计算“恢复比例”", "H2CJK"),
        paragraph(
            "每个雪后恢复日的实际骑行量除以匹配晴朗日骑行量的中位数，并在分子、分母各加 0.5 以避免零值问题。"
            "比例为 1 表示与参照相近，0.7 表示约为参照的七成。匹配日来自同一冬季、同一星期几和同一节假日状态，"
            "温度先限制在正负 5°C 内。若候选不足 3 天才放宽到正负 8°C。匹配日还必须无降水、无新雪、无积雪，"
            "并避开每场雪前后 7 天。每个恢复日最多选 5 个对照日。"
        ),
        paragraph("清洗后留下的雪事件", "H2CJK"),
        paragraph(
            f"把日新雪至少 1 mm 的日期连成雪事件，累计新雪至少 10 mm 才进入事件分析。共识别 {stage_a['events_at_10mm_threshold']} 场事件，"
            f"其中 {stage_a['events_with_matched_recovery']} 场至少有一个可匹配的雪后日期。最终得到 {stage_a['matched_city_event_days']} 个城市级雪后日，"
            f"并在 {stage_a['matched_station_event_days']:,} 个站点—事件—日期记录上分析站点差异。"
        ),
        PageBreak(),
    ])

    casual_snow = float(event_effects.loc["residual_snow_cm", "coefficient"])
    casual_ci = event_effects.loc["residual_snow_cm", ["ci_low", "ci_high"]].astype(float).to_numpy()
    casual_factor = np.exp(casual_snow * 10)
    casual_factor_ci = np.exp(casual_ci * 10)
    member_snow = casual_snow + float(event_effects.loc["residual_snow_cm:C(user_type)[T.member]", "coefficient"])
    member_p = float(hierarchy["primary_snow_depth_member_p_value"])
    member_ci = np.exp(np.array([
        hierarchy["primary_snow_depth_member_ci_low"],
        hierarchy["primary_snow_depth_member_ci_high"],
    ]) * 10)
    interaction_p = float(hierarchy["primary_snow_depth_user_interaction_p_value"])
    robust_casual = float(robust_effects.loc["residual_snow_cm", "coefficient"])
    robust_member = robust_casual + float(robust_effects.loc["residual_snow_cm:C(user_type)[T.member]", "coefficient"])
    robust_casual_ci = robust_effects.loc["residual_snow_cm", ["ci_low", "ci_high"]].astype(float).to_numpy()
    robust_member_ci = np.exp(np.array([
        hierarchy["sensitivity_snow_depth_member_ci_low"],
        hierarchy["sensitivity_snow_depth_member_ci_high"],
    ]) * 10)
    robust_member_p = float(hierarchy["sensitivity_snow_depth_member_p_value"])
    robust_interaction_p = float(robust_effects.loc["residual_snow_cm:C(user_type)[T.member]", "p_value"])

    story.extend([
        paragraph("2. 雪停后，残雪和用户恢复并不同步", "H1CJK"),
        paragraph(
            f"事件内匹配后，68 个恢复日中有 {stage_a['snowpack_present_days']} 天记录到残余积雪，平均深度为约 6.1 cm；"
            f"另有 {stage_a['snowpack_absent_days']} 天 NOAA 报告无积雪。按雪事件等权汇总，残雪日临时用户的恢复比例约为 0.62，"
            "无残雪日约为 0.83。这个直观比较尚未控制雪后时间等因素，接下来用层级模型进一步检查。"
        ),
        Image(str(FIGURES / "04_residual_snow_comparison.png"), width=16.5 * cm, height=7.7 * cm),
        paragraph(
            "图 1　按雪事件等权的雪后恢复比例。点表示各组事件平均值，线表示按雪事件重抽样得到的 95% 区间。"
            "同一场雪提供的多个日期不会被当作彼此独立的事件。",
            "CaptionCJK",
        ),
        paragraph("控制因素以后，用户差异仍然出现", "H2CJK"),
        paragraph(
            f"主模型包含 {hierarchy['rows']} 条用户—恢复日记录和 {hierarchy['events']} 场降雪事件，按事件设置随机截距，"
            "并控制雪后第几天、冬季、气温、雨量和风速。模型估计，积雪深度每多 10 cm，临时用户相对对照的骑行比例"
            f"乘以 {casual_factor:.2f}，约低 {(1-casual_factor)*100:.0f}%。95% 区间对应约低 {(1-casual_factor_ci[1])*100:.0f}% 至 {(1-casual_factor_ci[0])*100:.0f}%。"
            f"会员的估计较接近不变（比例因子 {np.exp(member_snow*10):.2f}，95% 区间 {member_ci[0]:.2f}–{member_ci[1]:.2f}，p={member_p:.3f}）。"
            f"两类用户的积雪斜率差异明显（p={interaction_p:.5f}）。"
        ),
        paragraph(
            f"补充普通最小二乘回归使用相同控制项，并按雪事件聚类计算稳健标准误。该模型估计每 10 cm 残雪对应临时用户比例因子 "
            f"{np.exp(robust_casual*10):.2f}（95% 区间 {np.exp(robust_casual_ci[0]*10):.2f}–{np.exp(robust_casual_ci[1]*10):.2f}），"
            f"会员比例因子 {np.exp(robust_member*10):.2f}（95% 区间 {robust_member_ci[0]:.2f}–{robust_member_ci[1]:.2f}）。"
            f"两者的雪深斜率不同（p={robust_interaction_p:.5f}）；会员斜率在这一补充模型中也为负（p={robust_member_p:.3f}）。"
            "这组估计比主模型更大，说明精确幅度受模型设定影响，较稳妥的结论是两种模型都发现临时用户受残雪影响更明显。"
        ),
        paragraph(
            "模型曾尝试纳入节假日项，但所有匹配的恢复日都不是美国联邦假日，这一项无法由样本估计。最终模型删去了该项，"
            "同时保留了匹配对照时必须同节假日状态的规则。"
        ),
        PageBreak(),
    ])

    story.extend([
        paragraph("3. 恢复类型是否能跨冬季重现", "H1CJK"),
        paragraph("降雪事件的两类分组", "H2CJK"),
        paragraph(
            f"从 26 场有匹配日的事件中，只有 {event_validation['eligible_events']} 场拥有至少 3 个匹配恢复日，足以计算完整曲线。"
            f"按雪后总量、会员和临时用户曲线分成两类，轮廓系数为 {event_validation['full_fit_silhouette']:.3f}。"
            "一类以较轻降雪和接近参照的骑行为主，另一类降雪更重且总量在雪后几天仍较低。"
            "轮廓系数本身不高，表示两类边界并不清楚。"
        ),
    ])
    event_table = [[
        paragraph("分组", "TableCJK"),
        paragraph("事件数", "TableCJK"),
        paragraph("累计新雪", "TableCJK"),
        paragraph("雪后第 4 天总量 / 参照", "TableCJK"),
        paragraph("雪后第 4 天临时用户 / 参照", "TableCJK"),
    ]]
    for cluster_id in sorted(event_profiles["cluster"].unique()):
        row = event_profiles[event_profiles["cluster"].eq(cluster_id)].iloc[0]
        event_table.append([
            paragraph("较轻雪、较接近参照" if cluster_id == 0 else "较重雪、持续偏低", "TableCJK"),
            paragraph(str(int((event_clusters["cluster"] == cluster_id).sum())), "TableCJK"),
            paragraph(f"{row['snow_total_mm']:.1f} mm", "TableCJK"),
            paragraph(f"{row['rides_ratio_h4']:.2f}", "TableCJK"),
            paragraph(f"{row['casual_ratio_h4']:.2f}", "TableCJK"),
        ])
    story.append(make_table(event_table, [4.1 * cm, 1.7 * cm, 2.6 * cm, 4.1 * cm, 4.2 * cm], "#fbf0dc"))
    story.extend([
        Spacer(1, 0.15 * cm),
        paragraph(
            f"留一冬季时，两个事件类型在 {event_validation['loyo_winter_types_both_present_folds']} 个冬季中都出现。"
            f"把每场事件轮流留出后，与全量分组的一致性 ARI 只有 {event_validation['loeo_agreement_ari']:.3f}，"
            f"12 场中 {event_validation['loeo_events_within_training_95pct_radius']} 场落在训练事件距离的 95% 范围内。"
            "因此，“轻雪 / 重雪两种稳定恢复类型”目前只能作为探索线索，不能当成已经验证的分类规律。"
        ),
        Image(str(FIGURES / "01_event_recovery_curves.png"), width=16.4 * cm, height=7.0 * cm),
        paragraph("图 2　不同残雪状态下、相对匹配晴朗日基准的恢复曲线。部分事件窗口没有足够匹配日，因此每日可用样本量会变化。", "CaptionCJK"),
        PageBreak(),
        paragraph("3.2 站点恢复类型", "H1CJK"),
        paragraph("站点分组更接近可复核，但仍有冬季差异", "H2CJK"),
        paragraph(
            f"577 个站点按总量、会员和临时用户恢复比例以及用户差值和恢复斜率分为三组。为了不把大站、小站误当作恢复类型，"
            "模型对恢复比例取对数，并且不把站点平常骑行量输入聚类。这里的 577 个站点仅指有足够雪后记录、可计算恢复曲线的站点。"
        ),
    ])
    station_table = [[
        paragraph("站点恢复模式", "TableCJK"),
        paragraph("站点数", "TableCJK"),
        paragraph("总量 / 参照", "TableCJK"),
        paragraph("会员 / 参照", "TableCJK"),
        paragraph("临时用户 / 参照", "TableCJK"),
    ]]
    for _, row in station_profiles.iterrows():
        if row["rides_ratio"] < 0.9:
            label = f"类型{int(row['cluster']) + 1} 恢复比例偏低"
        elif row["casual_member_gap"] > 0.25:
            label = f"类型{int(row['cluster']) + 1} 临时用户恢复偏高"
        elif row["baseline_mean"] < 5:
            label = f"类型{int(row['cluster']) + 1} 比例偏高、日常基数低"
        else:
            label = f"类型{int(row['cluster']) + 1} 总体恢复比例偏高"
        station_table.append([
            paragraph(label, "TableCJK"),
            paragraph(str(int(row["stations"])), "TableCJK"),
            paragraph(f"{row['rides_ratio']:.2f}", "TableCJK"),
            paragraph(f"{row['member_ratio']:.2f}", "TableCJK"),
            paragraph(f"{row['casual_ratio']:.2f}", "TableCJK"),
        ])
    story.append(make_table(station_table, [5.4 * cm, 2.0 * cm, 3.1 * cm, 3.1 * cm, 3.1 * cm], "#eaf2f8"))
    story.extend([
        Spacer(1, 0.15 * cm),
        paragraph(
            f"留一冬季检查时，四个冬季都能分出三类，平均分区 ARI 为 {station_validation['mean_held_winter_partition_ari']:.3f}。"
            f"但最新留出冬季的 ARI 为 {station_validation['winter_folds'][-1]['cluster_coverage_ari']:.3f}，显示分组随冬季仍会变化。"
            "这些标签描述的是样本中的恢复轨迹，不说明站点周围环境造成了这种轨迹。"
        ),
        Image(str(FIGURES / "02_station_recovery_types_map.png"), width=9.4 * cm, height=9.4 * cm),
        paragraph("图 3　按恢复比例分组的 577 个站点。地图展示点位和分组，不代表道路或街区边界。", "CaptionCJK"),
        PageBreak(),
    ])

    metrics_order = [
        "GRU: lagged weather",
        "GRU: day-ahead forecast",
        "Month + weekday median",
        "Previous week",
    ]
    target_labels = {"rides": "总骑行量", "member": "会员", "casual": "临时用户"}
    model_labels = {
        "GRU: lagged weather": "GRU：过去天气",
        "GRU: day-ahead forecast": "GRU：前一天预报",
        "Month + weekday median": "月份 + 星期中位数",
        "Previous week": "上周同日",
    }
    story.extend([
        paragraph("4. 天气预报能不能提前帮忙", "H1CJK"),
        paragraph(
            "模型读取连续 14 天的城市骑行量和已发生天气，同时知道目标日的月份、星期和节假日。"
            "第一版只用过去 14 天实际记录的天气。第二版加入真实存档的 NDFD 预报，预报最多只能发布到目标日前一天中午，"
            "因此不会把目标日实际天气误当成提前可知信息。一个 GRU 共享输出头同时预测总骑行、会员和临时用户骑行。"
        ),
        paragraph(
            f"训练与测试按完整冬季切分。2021-22、2022-23 冬季训练，2023-24 冬季选训练轮数，"
            f"最后用前三个冬季重训，并在 2024-12-15 至 2025-03-31 的 {gru_config['test_days']} 天测试。"
            "同一场雪的相邻日没有被随机分到训练和测试两边。GPU 训练进程限制在设备显存的 8%。"
        ),
    ])
    gru_table = [[
        paragraph("模型", "TableCJK"),
        paragraph("预测对象", "TableCJK"),
        paragraph("MAE（次 / 日）", "TableCJK"),
        paragraph("WAPE", "TableCJK"),
        paragraph("平均日相对误差", "TableCJK"),
        paragraph("汇总相对误差", "TableCJK"),
    ]]
    for model in metrics_order:
        for target in ["rides", "member", "casual"]:
            row = gru_metrics[(gru_metrics["model"] == model) & (gru_metrics["target"] == target)].iloc[0]
            gru_table.append([
                paragraph(model_labels[model], "TableCJK"),
                paragraph(target_labels[target], "TableCJK"),
                paragraph(f"{row['mae_rides']:,.0f}", "TableCJK"),
                paragraph(f"{row['wape']:.1%}", "TableCJK"),
                paragraph(f"{row['mean_signed_relative_error_gt_minus_pred']:+.1%}", "TableCJK"),
                paragraph(f"{row['pooled_signed_relative_error_gt_minus_pred']:+.1%}", "TableCJK"),
            ])
    story.extend([
        make_table(gru_table, [3.5 * cm, 2.0 * cm, 2.5 * cm, 1.9 * cm, 3.4 * cm, 3.1 * cm], "#eaf2f8"),
        Spacer(1, 0.15 * cm),
        paragraph(
            "WAPE 是测试期所有绝对误差加总除以真实骑行总量。相对误差严格按“(GT − 预测值) / GT”计算。"
            "平均日相对误差先算每天再平均，负数表示模型在普通日期上更常高估。汇总相对误差把每天误差加总后再除以总真实量，"
            "会更受大流量日影响，所以两列数值可能方向不同。"
        ),
        paragraph(
            "前一天预报版的 WAPE 为总量 18.1%、会员 16.3%、临时用户 26.4%。只用过去天气时分别为 25.8%、22.7% 和 38.7%。"
            "在这一个完整留出冬季中，前一天预报版优于历史天气版和两个简单基线。临时用户的日均相对误差为 −11.7%，"
            "也就是平均每天约高估 11.7%；但按骑行量加权的汇总相对误差为 +2.1%，整体骑行量则略低估。"
        ),
        Image(str(FIGURES / "03_winter_test_predictions.png"), width=16.2 * cm, height=8.9 * cm),
        paragraph("图 4　2024-25 独立测试冬季的实际骑行量与预测曲线。天气预报版更贴近多数日变化，但峰值日仍有明显误差。", "CaptionCJK"),
        PageBreak(),
    ])

    story.extend([
        paragraph("5. 站点周边环境与相关工作", "H1CJK"),
        paragraph(
            f"站点周边空间分析覆盖 {spatial['n_stations']} 个站点。最近 CTA 轨道站和公园距离与临时用户恢复比例的线性关系不明显，"
            "而平常骑行量与恢复比例有关。加上所在社区区后，样本内 R² 从 "
            f"{area_spatial['base_model_r_squared_same_sample']:.3f} 增至 {area_spatial['area_fixed_effect_model_r_squared']:.3f}，调整后 R² 为 "
            f"{area_spatial['area_fixed_effect_model_adjusted_r_squared']:.3f}。这是 43 个社区区上的样本内比较，尚未留出社区验证，"
            "只能说明区域差异值得追查。公园或轨道距离的结果也不能解释为因果。"
        ),
        paragraph("目前能不能说新颖", "H2CJK"),
        paragraph(
            "截至 2026 年 11 月，已有研究用共享单车行程分析极端天气敏感性和恢复曲线 [1]，也有研究比较极端天气下站点需求和周边土地利用差异 [2]。"
            "Chicago Divvy 的工作分析过不同降雨强度下会员与临时用户的骑行变化 [3]，较早的研究也把降雪深度等天气变量纳入骑行韧性模型 [4]。"
            "因此，“天气影响骑行”“雪深与骑行相关”“会员和临时用户反应不同”都不能单独作为本项目的创新主张。"
        ),
        paragraph(
            "本项目较有希望的区别是把研究焦点具体到“雪停后的地面残雪深度”，并追踪它和会员、临时用户恢复差异之间的关系，"
            "再用前一日真实天气预报检验这种信息能否用于运营预测。这是一个候选贡献，不是已经确认的首创结论。"
            "当前实验只有四个冬季和一座城市，事件类别复现较弱，站点分群对冬季也有变化。现有分析不足以判断这一组合相对已发表工作的首创性。"
            "若要形成论文主张，需要逐篇核对相关研究的样本、事件定义与恢复指标，再补充独立城市或更多冬季，检验站点周边环境和清雪条件。"
        ),
        paragraph("参考研究", "H2CJK"),
        paragraph(
            "[1] Zhu, Sun & Miranda-Moreno. Global assessment of bike-sharing sensitivity and resilience to extreme weather. "
            "Transportation Research Part D, 157, 105413 (2026). DOI: 10.1016/j.trd.2026.105413。",
            "SmallCJK",
        ),
        paragraph(
            "[2] Zhu, Wang, Sun & Miranda-Moreno. Assessing resilience of urban bike-sharing systems: Weather and land-use influences on demand dynamics. "
            "Cities, 176, 107152 (2026). DOI: 10.1016/j.cities.2026.107152。",
            "SmallCJK",
        ),
        paragraph(
            "[3] Li et al. Exploring inter-user differences in bike-sharing origin-destination flows across rainfall intensities. "
            "Travel Behaviour and Society, 42, 101166 (2026). DOI: 10.1016/j.tbs.2025.101166。",
            "SmallCJK",
        ),
        paragraph(
            "[4] Cheng et al. The Role of Bike Sharing in Promoting Transport Resilience. Networks and Spatial Economics, 22, 567–585 (2022). "
            "DOI: 10.1007/s11067-021-09518-9。",
            "SmallCJK",
        ),
        paragraph(
            "[5] Divvy. System Data, 历史行程档案，2026-11-15 获取。NOAA NCEI. Daily Summaries, O’Hare 站 USW00094846。"
            "NOAA. National Digital Forecast Database, 历史预报产品，2026-11-15 获取。",
            "SmallCJK",
        ),
        PageBreak(),
    ])

    story.extend([
        paragraph("6. 结论与下一轮验证", "H1CJK"),
        paragraph("目前可以支持的结论", "H2CJK"),
        paragraph(
            "第一，雪后仍有积雪的日期，骑行量和用户构成通常低于相似晴朗日。第二，控制雪后日期、冬季和天气后，"
            "残雪深度与临时用户恢复率的负相关强于会员，事件聚类标准误下方向也一致。第三，三类站点恢复轨迹在四个冬季都能分出，"
            "但不同冬季的分组一致度只有中等，雪事件的两类划分复现不足。第四，提前一天的历史天气预报让 GRU 在 107 天独立冬季测试中"
            "优于只用过去天气版和两个简单基线。"
        ),
        paragraph("哪些结论仍需验证", "H2CJK"),
        paragraph(
            "观察数据不能证明积雪是唯一原因，也没有道路或站点逐点的积雪测量。NOAA 的 O’Hare 日观测代表机场附近环境，"
            "不能捕捉整个芝加哥每条街道清雪的差异。GRU 只有一个冬季作为最终测试，误差提升需要更多冬季和城市复验。"
            "聚类结果是探索性分组，尤其事件级分组目前不够稳定。"
        ),
        paragraph("新颖性判断", "H2CJK"),
        paragraph(
            "当前结果足以形成一份有明确假设、匹配对照、层级分析、跨冬季检查和独立冬季预测的课堂报告。"
            "但不能把它包装成已证明的顶会创新。更有价值的下一步，是获取细到街区的降雪与清雪数据，扩大冬季和城市范围，"
            "预先固定分析协议，并再次检验“残雪状态下用户恢复差距”是否复现。"
        ),
        paragraph("AI 使用说明", "H2CJK"),
        paragraph(
            "研究主线“残余积雪状态下的分群恢复”由项目统筹者提出。AI 辅助编写数据清洗、匹配、层级模型、聚类、预测和绘图代码，"
            "整理输出并协助生成报告。实验数字来自代码运行结果。研究者仍需检查原始数据定义、模型假设、结果解释和文献范围，"
            "并决定是否将候选贡献发展为正式论文。"
        ),
        paragraph("复现位置", "H2CJK"),
        paragraph(
            "本目录包含服务器执行的 Python 源码、处理后的逐日数据、结果 CSV/JSON 和全部图件。原始 Divvy、NOAA、NDFD 与空间数据"
            "保存在服务器数据盘 /root/autodl-tmp/ai-sci/data/raw/。运行方法和软件环境写在同目录 README 中。",
            "SmallCJK",
        ),
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    main()
