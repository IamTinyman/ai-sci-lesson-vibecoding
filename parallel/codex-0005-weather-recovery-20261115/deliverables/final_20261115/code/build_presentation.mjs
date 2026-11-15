import fs from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const WORKSPACE = "/Users/tinyman/BUPT/PHD/2026_2027_1/ai-sci/incoming/0005-codex/final_20261115";
const BUILD_DIR = path.join(WORKSPACE, ".presentation-build-v3");
const PREVIEW_DIR = path.join(BUILD_DIR, "slides");
const OUTPUT_DIR = path.join(WORKSPACE, "presentations");
const FINAL_PPTX = path.join(OUTPUT_DIR, "weather-recovery-classroom-20261115-v3.pptx");
const FIGURES = path.join(WORKSPACE, "figures-final");
const FONT = "Heiti SC";
const COLORS = {
  ink: "#18322D",
  green: "#287A71",
  orange: "#D9822B",
  muted: "#596B65",
  line: "#D9E2DE",
  paper: "#FFFFFF",
};

const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function addText(slide, name, text, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: options.fontSize ?? 24,
    color: options.color ?? COLORS.ink,
    bold: options.bold ?? false,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "top",
    autoFit: "shrinkText",
    wrap: "square",
    insets: 0,
  };
  return shape;
}

function addLine(slide, name, x, y, width, color = COLORS.line, thickness = 1) {
  slide.shapes.add({
    geometry: "line",
    name,
    position: { left: x, top: y, width, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: thickness },
  });
}

function addImage(slide, fileName, alt, position) {
  const imageBytes = readFileSync(path.join(FIGURES, fileName));
  slide.images.add({
    blob: new Uint8Array(imageBytes),
    contentType: "image/png",
    alt,
    fit: "contain",
    position,
  });
}

function addBaseSlide(title, page) {
  const slide = presentation.slides.add();
  slide.background.fill = COLORS.paper;
  addText(slide, `title-${page}`, title, { left: 68, top: 40, width: 1135, height: 56 }, {
    fontSize: 42,
    bold: true,
  });
  addLine(slide, `title-rule-${page}`, 68, 116, 1144, COLORS.line, 1.2);
  addText(slide, `footer-${page}`, `Divvy × NOAA  |  雪后共享单车恢复  |  ${page}`, {
    left: 68,
    top: 680,
    width: 1140,
    height: 22,
  }, { fontSize: 15, color: COLORS.muted });
  return slide;
}

function addNotes(slide, notes) {
  slide.speakerNotes.text = notes;
}

{
  const slide = presentation.slides.add();
  slide.background.fill = COLORS.ink;
  addLine(slide, "cover-accent", 76, 105, 90, COLORS.orange, 5);
  addText(slide, "cover-title", "雪停以后，\n谁先回来？", {
    left: 76,
    top: 140,
    width: 520,
    height: 180,
  }, { fontSize: 62, bold: true, color: COLORS.paper });
  addText(slide, "cover-subtitle", "残余积雪与会员、临时用户的恢复差异", {
    left: 78,
    top: 355,
    width: 530,
    height: 70,
  }, { fontSize: 28, color: "#EAF2EE" });
  addText(slide, "cover-context", "芝加哥 Divvy × NOAA\n2021—2025 四个冬季  |  研究阶段报告  |  2026 年 11 月 15 日", {
    left: 78,
    top: 500,
    width: 520,
    height: 74,
  }, { fontSize: 19, color: "#CFDCD6" });
  addImage(slide, "04_residual_snow_comparison.png", "有无残雪时的骑行恢复比例对比", {
    left: 660,
    top: 205,
    width: 535,
    height: 275,
  });
  addText(slide, "cover-takeaway", "残雪日临时用户恢复比例 0.62\n无残雪日 0.83", {
    left: 685,
    top: 510,
    width: 490,
    height: 80,
  }, { fontSize: 26, bold: true, color: COLORS.paper, alignment: "center" });
  addNotes(slide, "图中数据来自本轮 Divvy 与 NOAA 实验结果。残雪日与无残雪日比较按降雪事件等权汇总，尚未控制雪后时间和天气因素。完整分析见配套中文 PDF 报告。\n数据来源为 Divvy System Data 与 NOAA NCEI Daily Summaries。获取日期为 2026-11-15。");
}

{
  const slide = addBaseSlide("研究问题与可检验判断", 2);
  addText(slide, "question-lead", "雪已经停了，为什么骑行量还没回到平常？", {
    left: 74,
    top: 155,
    width: 1100,
    height: 72,
  }, { fontSize: 36, bold: true, color: COLORS.green });
  addText(slide, "question-explanation", "我们观察雪后的无新雪日期，并把当天骑行量与相似的干燥无雪日比较。相似日来自同一冬季，星期几和节假日状态相同，气温接近。", {
    left: 76,
    top: 252,
    width: 1080,
    height: 98,
  }, { fontSize: 25 });
  addLine(slide, "hypothesis-rule", 76, 390, 100, COLORS.orange, 4);
  addText(slide, "hypothesis-label", "要检验的判断", {
    left: 76,
    top: 418,
    width: 220,
    height: 35,
  }, { fontSize: 22, bold: true, color: COLORS.muted });
  addText(slide, "hypothesis-text", "雪停后，地面残雪越深，临时用户相对会员的骑行恢复越弱。", {
    left: 76,
    top: 463,
    width: 1080,
    height: 66,
  }, { fontSize: 32, bold: true });
  addText(slide, "hypothesis-caveat", "这是一项观察性分析，可以检查这种关系是否重复出现，不能单独证明积雪造成了变化。", {
    left: 76,
    top: 562,
    width: 1080,
    height: 52,
  }, { fontSize: 20, color: COLORS.muted });
  addNotes(slide, "恢复比例定义为实际骑行量与同冬季匹配晴朗日中位数之比。模型匹配同星期、同节假日状态、相近气温的干燥无雪日，并排除雪事件前后 7 天。雨量进入后续模型作为控制变量。本轮没有单独分析雨后恢复事件。");
}

{
  const slide = addBaseSlide("数据与对照方法", 3);
  const metrics = [
    ["485", "个冬季日期"],
    ["323 万", "条保留行程"],
    ["29", "场达阈值降雪"],
    ["68", "个匹配雪后日"],
  ];
  const startX = 74;
  const gap = 22;
  const colWidth = 260;
  metrics.forEach(([value, label], index) => {
    const x = startX + index * (colWidth + gap);
    addText(slide, `metric-${index}-value`, value, { left: x, top: 160, width: colWidth, height: 65 }, {
      fontSize: 48,
      bold: true,
      color: index === 3 ? COLORS.orange : COLORS.green,
    });
    addText(slide, `metric-${index}-label`, label, { left: x, top: 231, width: colWidth, height: 34 }, {
      fontSize: 21,
      color: COLORS.muted,
    });
  });
  addLine(slide, "data-method-rule", 74, 318, 1130, COLORS.line, 1);
  addText(slide, "event-definition", "雪事件", { left: 74, top: 348, width: 160, height: 34 }, {
    fontSize: 22,
    bold: true,
    color: COLORS.green,
  });
  addText(slide, "event-definition-detail", "日新雪至少 1 mm 连续成段，整场累计新雪至少 10 mm。识别到 29 场，其中 26 场有可匹配的雪后日期。", {
    left: 250,
    top: 348,
    width: 925,
    height: 58,
  }, { fontSize: 21 });
  addText(slide, "recovery-definition", "对照日", { left: 74, top: 435, width: 160, height: 34 }, {
    fontSize: 22,
    bold: true,
    color: COLORS.green,
  });
  addText(slide, "recovery-definition-detail", "同冬季、同星期、同节假日状态、气温相差不超过 5°C（候选不足时放宽到 8°C），且无雨、无新雪、无积雪。", {
    left: 250,
    top: 435,
    width: 925,
    height: 60,
  }, { fontSize: 21 });
  addText(slide, "station-data", "站点分析另有 39,236 条站点—事件—日期记录；有足够雪后观察的 577 个站点进入恢复分组。", {
    left: 74,
    top: 532,
    width: 1130,
    height: 40,
  }, { fontSize: 19, color: COLORS.muted });
  addText(slide, "data-sources", "数据期为 2021-12-01 至 2025-03-31。Divvy 官方行程档案与 NOAA O’Hare 日天气，获取于 2026-11-15。", {
    left: 74,
    top: 600,
    width: 1130,
    height: 35,
  }, { fontSize: 16, color: COLORS.muted });
  addNotes(slide, "清洗保留 3,233,071 条行程。缺少起点站编号的 506,391 条仍用于城市总量，未用于站点分析。NOAA O'Hare 站 USW00094846 的 PRCP、SNOW、SNWD、AWND、TMAX、TMIN 六项日字段在研究期内无整日缺失。数据入口为 Divvy System Data 和 NOAA NCEI Daily Summaries。");
}

{
  const slide = addBaseSlide("残雪越深，临时用户恢复越弱", 4);
  addImage(slide, "04_residual_snow_comparison.png", "按雪事件等权汇总的残雪与无残雪恢复比例", {
    left: 60,
    top: 150,
    width: 730,
    height: 350,
  });
  addText(slide, "recovery-gap-number", "0.62", { left: 850, top: 170, width: 270, height: 78 }, {
    fontSize: 66,
    bold: true,
    color: COLORS.orange,
  });
  addText(slide, "recovery-gap-label", "仍有残雪时，临时用户\n相对晴朗日的恢复比例", {
    left: 850,
    top: 245,
    width: 330,
    height: 74,
  }, { fontSize: 22 });
  addText(slide, "recovery-clear-number", "0.83", { left: 850, top: 350, width: 270, height: 70 }, {
    fontSize: 54,
    bold: true,
    color: COLORS.green,
  });
  addText(slide, "recovery-clear-label", "没有残雪时的对应比例", {
    left: 850,
    top: 415,
    width: 330,
    height: 35,
  }, { fontSize: 21, color: COLORS.muted });
  addLine(slide, "model-rule", 74, 530, 1132, COLORS.line, 1);
  addText(slide, "model-estimate", "控制雪后第几天、冬季、气温、降雨和风速后，每多 10 cm 残雪，临时用户恢复比例约低 33.5%。\n95% 区间约低 14.6% 至 48.2%；会员估计接近不变，用户差异仍明显。", {
    left: 74,
    top: 552,
    width: 1125,
    height: 82,
  }, { fontSize: 21, bold: true });
  addNotes(slide, "图上点和区间按雪事件等权重做重抽样。主模型使用 136 条用户类别—恢复日记录、26 场雪事件，并为每场雪设置随机截距。主模型临时用户每 10 cm 雪深的比例因子为 0.665，95% 区间 0.518–0.854，p=0.0014。会员因子为 0.969，95% 区间 0.755–1.244，p=0.806。临时用户与会员斜率差异 p=0.0000896。按事件聚类稳健标准误的普通最小二乘敏感性模型估计临时用户因子 0.54、会员 0.79，斜率差异 p=0.000682。效应大小依赖模型设定，解释为关联。");
}

{
  const slide = addBaseSlide("恢复分组能否跨冬季复现", 5);
  addImage(slide, "01_event_recovery_curves.png", "雪后总量、会员和临时用户恢复曲线", {
    left: 58,
    top: 155,
    width: 710,
    height: 390,
  });
  addText(slide, "event-cluster-number", "12 场", { left: 825, top: 165, width: 300, height: 60 }, {
    fontSize: 44,
    bold: true,
    color: COLORS.green,
  });
  addText(slide, "event-cluster-number-label", "有足够恢复记录的事件\n被探索性地分成两类", {
    left: 825,
    top: 225,
    width: 345,
    height: 70,
  }, { fontSize: 22 });
  addText(slide, "event-silhouette", "0.286", { left: 825, top: 340, width: 280, height: 62 }, {
    fontSize: 44,
    bold: true,
    color: COLORS.orange,
  });
  addText(slide, "event-silhouette-label", "两类边界较模糊", {
    left: 825,
    top: 401,
    width: 320,
    height: 36,
  }, { fontSize: 22 });
  addLine(slide, "cluster-validity-rule", 825, 467, 330, COLORS.line, 1);
  addText(slide, "event-cluster-validity", "逐场雪留出时，分组一致度 ARI = 0.177；12 场中只有 8 场落在训练事件距离的 95% 范围内。\n\n事件分组目前只能帮助提出问题，不能作为稳定类型结论。", {
    left: 825,
    top: 488,
    width: 350,
    height: 120,
  }, { fontSize: 19 });
  addNotes(slide, "事件分组只纳入至少有 3 个匹配恢复日的事件，共 12 场。两类 K-means 轮廓系数为 0.286。留一冬季时 4 折中有 3 折都能看到两类，逐场事件留出与全量标签的一致度 ARI 为 0.177。8/12 场落在训练事件距离的 95% 范围内。数值来自 event_cluster_validation_summary.json 和相关 CSV。");
}

{
  const slide = addBaseSlide("站点恢复有差异，空间原因仍待验证", 6);
  addImage(slide, "02_station_recovery_types_map.png", "芝加哥 577 个站点的雪后恢复分组", {
    left: 62,
    top: 152,
    width: 480,
    height: 480,
  });
  addText(slide, "station-types-heading", "577 个站点分成三组", {
    left: 590,
    top: 160,
    width: 580,
    height: 45,
  }, { fontSize: 30, bold: true, color: COLORS.green });
  addText(slide, "station-types", "类型 1  282 个站点恢复比例偏低\n类型 2  125 个站点比例偏高，但平常骑行基数较低\n类型 3  170 个站点的临时用户恢复比例偏高", {
    left: 592,
    top: 225,
    width: 570,
    height: 116,
  }, { fontSize: 21 });
  addText(slide, "station-stability", "四个留出冬季都能分出三组。平均分组一致度 ARI = 0.552；2024—25 留出冬季降到 0.276，说明具体站点的归类会随冬季变化。", {
    left: 592,
    top: 370,
    width: 575,
    height: 100,
  }, { fontSize: 21 });
  addLine(slide, "spatial-rule", 592, 495, 560, COLORS.line, 1);
  addText(slide, "spatial-finding", "最近 CTA 轨道站和公园的距离没有明显线性关系。加入社区区后，样本内 R² 从 0.233 升至 0.364，但还没有做留出社区验证。", {
    left: 592,
    top: 517,
    width: 575,
    height: 94,
  }, { fontSize: 20, color: COLORS.ink });
  addNotes(slide, "站点恢复类型来自以恢复比例对数为输入的聚类，未把日常骑行量作为聚类特征。留一冬季三类均出现，平均 ARI 0.552，2025 fold ARI 0.276。空间模型覆盖 577 个有恢复特征的站点。CTA 轨道站和公园距离未显示明显线性关系。加入 43 个社区区固定效应，样本内 R² 从 0.233 增至 0.364。尚未留出社区验证，因此只能说明区域差异，不支持因果解释。");
}

{
  const slide = addBaseSlide("前一天的天气预报改善了骑行预测", 7);
  addText(slide, "forecast-method", "模型用过去 14 天的骑行和天气，同时预测总量、会员、临时用户。预报版只使用目标日前一天中午前已发布的 NOAA 预报。", {
    left: 72,
    top: 136,
    width: 1135,
    height: 62,
  }, { fontSize: 21 });
  addImage(slide, "03_winter_test_predictions.png", "2024-25 独立测试冬季三类骑行量预测", {
    left: 56,
    top: 210,
    width: 690,
    height: 420,
  });
  addText(slide, "wape-heading", "WAPE 越低越好", {
    left: 795,
    top: 215,
    width: 370,
    height: 34,
  }, { fontSize: 25, bold: true, color: COLORS.green });
  addText(slide, "wape-table-heading", "预测对象        前一天预报    过去天气", {
    left: 795,
    top: 270,
    width: 400,
    height: 34,
  }, { fontSize: 18, bold: true, color: COLORS.muted });
  addText(slide, "wape-table", "总骑行量          18.1%             25.8%\n会员                  16.3%             22.7%\n临时用户             26.4%             38.7%", {
    left: 795,
    top: 312,
    width: 405,
    height: 113,
  }, { fontSize: 21 });
  addLine(slide, "relative-error-rule", 795, 452, 390, COLORS.line, 1);
  addText(slide, "relative-error", "相对误差按 (GT − 预测值) / GT 计算。预报版逐日平均误差为 −4.0%、−2.9%、−11.7%，负数表示平均高估。\n\n测试集是完整留出的 2024—25 冬季，共 107 天。", {
    left: 795,
    top: 473,
    width: 400,
    height: 128,
  }, { fontSize: 18 });
  addNotes(slide, "GRU 输入 14 天历史总量、会员量、临时用户量、日天气和日历特征，共享模型同时预测三类骑行量。预报版额外加入 NDFD 目标日预报，所有文件发布时间不晚于目标日前一天芝加哥中午。训练使用 2021-22 和 2022-23，2023-24 选择训练轮数，前三个冬季合并重训，2024-12-15 至 2025-03-31 共 107 天作为测试。WAPE 定义为 sum(abs(GT-prediction))/sum(GT)。相对误差定义为 (GT-prediction)/GT，负值表示高估。预报模型 WAPE 为 18.1%、16.3%、26.4%，仅用过去天气为 25.8%、22.7%、38.7%。");
}

{
  const slide = addBaseSlide("目前的研究位置与新颖性判断", 8);
  addText(slide, "prior-work-heading", "已发表研究已覆盖相邻问题", {
    left: 74,
    top: 150,
    width: 520,
    height: 42,
  }, { fontSize: 27, bold: true, color: COLORS.green });
  addText(slide, "prior-work-list", "极端天气后的共享单车恢复曲线\n多伦多、蒙特利尔等城市的站点天气韧性与土地利用\nChicago Divvy 会员和临时用户在不同降雨强度下的差异\n骑行量模型中已经使用降雪深度等天气变量", {
    left: 76,
    top: 210,
    width: 530,
    height: 185,
  }, { fontSize: 21 });
  addText(slide, "candidate-heading", "本项目的候选差异", {
    left: 675,
    top: 150,
    width: 490,
    height: 42,
  }, { fontSize: 27, bold: true, color: COLORS.orange });
  addText(slide, "candidate-text", "把焦点放在雪停后的残余雪深，比较会员与临时用户的恢复差距，并测试提前一天可用的天气预报能否改善运营预测。", {
    left: 678,
    top: 210,
    width: 485,
    height: 130,
  }, { fontSize: 25, bold: true });
  addLine(slide, "novelty-rule", 75, 445, 1125, COLORS.line, 1);
  addText(slide, "novelty-status", "这是一条有数据支持的研究线索，还不是经过完整文献核查确认的首创贡献。单城、四个冬季和事件聚类不稳定，限制了目前能提出的论文主张。", {
    left: 76,
    top: 480,
    width: 1100,
    height: 100,
  }, { fontSize: 22, color: COLORS.ink });
  addText(slide, "citation-strip", "相关研究：Zhu et al., TR-D (2026), DOI 10.1016/j.trd.2026.105413；Zhu et al., Cities (2026), DOI 10.1016/j.cities.2026.107152；Li et al., TBS (2026), DOI 10.1016/j.tbs.2025.101166。", {
    left: 76,
    top: 610,
    width: 1100,
    height: 42,
  }, { fontSize: 14, color: COLORS.muted });
  addNotes(slide, "来源文献包括 Zhu, Sun & Miranda-Moreno, Global assessment of bike-sharing sensitivity and resilience to extreme weather, Transportation Research Part D 157 (2026), 105413, DOI 10.1016/j.trd.2026.105413；Zhu et al., Assessing resilience of urban bike-sharing systems: Weather and land-use influences on demand dynamics, Cities 176 (2026), 107152, DOI 10.1016/j.cities.2026.107152；Li et al., Exploring inter-user differences in bike-sharing origin-destination flows across rainfall intensities, Travel Behaviour and Society 42 (2026), 101166, DOI 10.1016/j.tbs.2025.101166；Cheng et al., The Role of Bike Sharing in Promoting Transport Resilience, Networks and Spatial Economics 22 (2022), 567–585, DOI 10.1007/s11067-021-09518-9. Related-work screening is not exhaustive, so novelty remains unverified.");
}

{
  const slide = addBaseSlide("阶段性结论", 9);
  addText(slide, "conclusion-lead", "残雪与临时用户恢复较弱有关，这个差异比事件聚类更站得住。", {
    left: 75,
    top: 145,
    width: 1120,
    height: 64,
  }, { fontSize: 32, bold: true, color: COLORS.green });
  addText(slide, "conclusion-supported", "已完成的验证", { left: 76, top: 246, width: 330, height: 38 }, {
    fontSize: 22,
    bold: true,
    color: COLORS.orange,
  });
  addText(slide, "conclusion-supported-detail", "匹配晴朗日与雪后恢复日；比较总量、会员和临时用户；做事件与站点分组；用整季留出的 GRU 检验前一天预报。", {
    left: 76,
    top: 292,
    width: 510,
    height: 100,
  }, { fontSize: 21 });
  addText(slide, "conclusion-limits", "解释边界", { left: 665, top: 246, width: 360, height: 38 }, {
    fontSize: 22,
    bold: true,
    color: COLORS.orange,
  });
  addText(slide, "conclusion-limits-detail", "O’Hare 天气代表机场附近，不是每条街道的积雪；观察数据不能证明因果；模型只在一个冬季独立测试；本轮没有单独分析雨后恢复。", {
    left: 665,
    top: 292,
    width: 500,
    height: 110,
  }, { fontSize: 21 });
  addLine(slide, "conclusion-next-rule", 76, 455, 1120, COLORS.line, 1);
  addText(slide, "conclusion-next", "下一步最需要的是更细的街区雪况与清雪数据，再用独立城市或更多冬季检验用户恢复差距。", {
    left: 76,
    top: 490,
    width: 1100,
    height: 82,
  }, { fontSize: 25, bold: true });
  addNotes(slide, "研究假设获得初步支持，但残雪只是城市机场气象站的区域代理。聚类属于探索性发现。预测实验的测试冬季仅一个。相关文献已覆盖广义的天气韧性、土地利用和用户差异，不能把当前研究描述为已确认的顶会创新。");
}

await fs.mkdir(PREVIEW_DIR, { recursive: true });
await fs.mkdir(OUTPUT_DIR, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(PREVIEW_DIR, `slide-${String(index + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
}

const candidatePath = path.join(BUILD_DIR, "candidate.pptx");
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(candidatePath);

const skillDir = "/Users/tinyman/.codex/plugins/cache/openai-primary-runtime/presentations/26.1110.11613/skills/presentations";
const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);
const result = await finalizePresentation({
  explicitTotalSlideCount: 9,
  workspaceDir: WORKSPACE,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: "/Users/tinyman/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  fontPolicy: { basis: "design", families: [FONT], scriptFonts: { ea: FONT } },
  verifyArtifactToolImport: true,
  receiptPath: path.join(BUILD_DIR, "validation-v3.json"),
});
console.log(JSON.stringify(result, null, 2));
