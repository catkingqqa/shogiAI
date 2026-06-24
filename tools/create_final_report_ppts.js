const path = require("path");
const fs = require("fs");
const PptxGenJS = require("pptxgenjs");

const OUT_DIR = path.join(process.cwd(), "outputs");
fs.mkdirSync(OUT_DIR, { recursive: true });

const C = {
  navy: "0F2A3F",
  blue: "2563EB",
  cyan: "BFE5F2",
  green: "D7F1E8",
  yellow: "FFF1B8",
  red: "F7D6DE",
  ink: "1F2937",
  muted: "64748B",
  line: "D7DEE8",
  bg: "F8FAFC",
  white: "FFFFFF",
};

const FONT = "Microsoft JhengHei";
const MONO = "Consolas";
const W = 13.333;
const H = 7.5;
const SHAPE = new PptxGenJS().ShapeType;

function deck() {
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "shogiAI";
  pptx.subject = "shogiAI report slides";
  pptx.company = "shogiAI";
  pptx.lang = "zh-TW";
  pptx.theme = {
    headFontFace: FONT,
    bodyFontFace: FONT,
    lang: "zh-TW",
  };
  pptx.defineLayout({ name: "CUSTOM_WIDE", width: W, height: H });
  pptx.layout = "CUSTOM_WIDE";
  return pptx;
}

function txt(slide, text, x, y, w, h, opt = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: opt.fontFace || FONT,
    fontSize: opt.fontSize || 18,
    color: opt.color || C.ink,
    bold: opt.bold || false,
    margin: opt.margin ?? 0.04,
    breakLine: false,
    fit: opt.fit || "shrink",
    valign: opt.valign || "mid",
    align: opt.align || "left",
    paraSpaceAfterPt: opt.paraSpaceAfterPt ?? 0,
    lineSpacingMultiple: opt.lineSpacingMultiple || 0.95,
    ...opt.extra,
  });
}

function header(slide, label, n) {
  txt(slide, label, 0.55, 0.23, 3.3, 0.22, { fontSize: 7.5, color: C.blue, bold: true });
  slide.addShape(SHAPE.line, { x: 0.55, y: 0.68, w: 12.25, h: 0, line: { color: C.line, width: 1 } });
  txt(slide, String(n).padStart(2, "0"), 12.1, 0.18, 0.55, 0.24, { fontSize: 7.5, color: C.muted, align: "right" });
  txt(slide, "shogiAI", 0.55, 7.1, 1.2, 0.18, { fontSize: 6.8, color: "9AA6B2" });
}

function title(slide, s) {
  txt(slide, s, 0.58, 0.82, 11.9, 0.48, { fontSize: 20, bold: true, color: C.ink });
}

function bulletText(items) {
  return items.map((v) => `• ${v}`).join("\n");
}

function bullets(slide, items, x, y, w, h, opt = {}) {
  txt(slide, bulletText(items), x, y, w, h, {
    fontSize: opt.fontSize || 13,
    color: opt.color || C.ink,
    lineSpacingMultiple: opt.lineSpacingMultiple || 1.05,
    extra: { breakLine: false },
  });
}

function card(slide, x, y, w, h, fill, line = C.line) {
  slide.addShape(SHAPE.rect, {
    x, y, w, h,
    rectRadius: 0.03,
    fill: { color: fill },
    line: { color: line, width: 1 },
  });
}

function labeledCard(slide, x, y, w, h, label, body, fill = C.white, accent = C.blue) {
  card(slide, x, y, w, h, fill);
  txt(slide, label, x + 0.16, y + 0.12, w - 0.32, 0.24, { fontSize: 10.5, bold: true, color: accent });
  txt(slide, body, x + 0.16, y + 0.46, w - 0.32, h - 0.55, { fontSize: 10.5, color: C.ink, lineSpacingMultiple: 1.02 });
}

function metrics(slide, data, y = 1.65) {
  const gap = 0.32;
  const w = (11.6 - gap * (data.length - 1)) / data.length;
  data.forEach((m, i) => {
    const x = 0.85 + i * (w + gap);
    labeledCard(slide, x, y, w, 0.95, m.k, m.v, C.white, m.c || C.blue);
  });
}

function table(slide, x, y, w, h, rows, widths) {
  const rh = h / rows.length;
  rows.forEach((row, r) => {
    let cx = x;
    row.forEach((cell, c) => {
      const cw = w * widths[c];
      const fill = r === 0 ? C.blue : (r % 2 ? C.white : "F1F5F9");
      slide.addShape(SHAPE.rect, { x: cx, y: y + r * rh, w: cw, h: rh, fill: { color: fill }, line: { color: C.line, width: 0.6 } });
      txt(slide, cell, cx + 0.08, y + r * rh + 0.04, cw - 0.16, rh - 0.08, {
        fontSize: r === 0 ? 8.8 : 8.3,
        bold: r === 0,
        color: r === 0 ? C.white : C.ink,
      });
      cx += cw;
    });
  });
}

function code(slide, text, x, y, w, h, fontSize = 7.5) {
  slide.addShape(SHAPE.rect, { x, y, w, h, fill: { color: "07111F" }, line: { color: "07111F" } });
  txt(slide, text, x + 0.15, y + 0.13, w - 0.3, h - 0.24, {
    fontFace: MONO,
    fontSize,
    color: "E5E7EB",
    lineSpacingMultiple: 0.82,
    valign: "top",
  });
}

function flow(slide, labels, x, y, w, h, fills) {
  const gap = 0.18;
  const bw = (w - gap * (labels.length - 1)) / labels.length;
  labels.forEach((l, i) => {
    const bx = x + i * (bw + gap);
    slide.addShape(SHAPE.rect, { x: bx, y, w: bw, h, fill: { color: fills[i % fills.length] }, line: { color: C.line, width: 1 } });
    txt(slide, l, bx + 0.05, y + 0.05, bw - 0.1, h - 0.1, { fontSize: 8.8, bold: true, align: "center" });
    if (i < labels.length - 1) {
      slide.addShape(SHAPE.rightArrow, { x: bx + bw - 0.02, y: y + h / 2 - 0.08, w: 0.22, h: 0.16, fill: { color: C.muted }, line: { color: C.muted } });
    }
  });
}

function cover(slide, big, sub) {
  slide.background = { color: C.navy };
  txt(slide, "shogiAI", 0.68, 0.58, 1.8, 0.3, { fontSize: 11, color: C.white, bold: true });
  txt(slide, big, 0.68, 1.82, 6.4, 0.72, { fontSize: 28, color: C.white, bold: true });
  txt(slide, sub, 0.7, 2.72, 6.6, 0.45, { fontSize: 13, color: "C7D2DE" });
  flow(slide, ["data", "model", "search"], 7.85, 2.0, 3.7, 1.7, [C.cyan, C.green, C.yellow]);
  txt(slide, "15 分鐘課堂報告", 0.7, 6.62, 2.4, 0.28, { fontSize: 10, color: "C7D2DE" });
}

function notes(slide, arr) {
  slide.addNotes(arr.join("\n"));
}

function dataScienceDeck() {
  const pptx = deck();
  const slides = [];
  function add(label, t) {
    const s = pptx.addSlide();
    if (slides.length === 0) cover(s, "數據科學理論與應用", "Policy-only CNN、資料集設計與 Alpha-beta 搜尋");
    else { s.background = { color: C.bg }; header(s, label, slides.length + 1); title(s, t); }
    slides.push(s);
    return s;
  }

  let s = add("", "");
  notes(s, ["開場說明本專案把將棋局面轉成可學習資料，訓練 policy-only CNN，再與搜尋結合。"]);

  s = add("問題定義", "把將棋決策轉成可監督學習問題");
  table(s, 0.9, 1.55, 7.8, 2.0, [
    ["元素", "本專案中的意義"],
    ["輸入 X", "9x9 棋盤、持駒、輪到誰、棋子種類與陣營"],
    ["輸出 y", "職業棋譜或 CSA 棋譜中實際選擇的下一手"],
    ["目標", "最大化正確走法的機率，讓模型學會局面到走法的對應"],
    ["限制", "只預測 policy，不估計 value，勝負判斷交給搜尋與評估函數"],
  ], [0.22, 0.78]);
  labeledCard(s, 9.15, 1.55, 2.95, 2.0, "核心觀念", "模型不是直接「思考勝負」，而是學習在某個局面下哪些合法手較像人類或強棋譜會下的手。", C.white, C.green);
  notes(s, ["說明 supervised learning：資料是棋譜局面與下一手，模型學的是條件機率 P(move | position)。"]);

  s = add("資料來源與規模", "最新資料集：4,855,173 筆 position-policy 對");
  metrics(s, [
    { k: "棋局數", v: "42,534 games", c: C.blue },
    { k: "訓練樣本", v: "4,855,173 rows", c: "059669" },
    { k: "NPZ 檔案", v: "約 332 MB", c: "B7791F" },
    { k: "無效列", v: "0 invalid rows", c: "BE123C" },
  ]);
  table(s, 1.35, 3.15, 10.2, 1.7, [
    ["項目", "內容"],
    ["資料來源", "MySQL 匯入後的 CSA/game/position/move 資料"],
    ["輸出檔", "policy_dataset.policy_only_latest.npz"],
    ["資料時間", "2026-06-16 匯出並開始訓練"],
  ], [0.28, 0.72]);
  notes(s, ["這頁放最新規模，讓聽眾知道訓練不是玩具資料，而是百萬級樣本。"]);

  s = add("資料前處理", "從 MySQL 棋譜資料轉成可訓練的 NPZ");
  flow(s, ["MySQL\npositions/moves", "匯出\nCSA/game rows", "解析 SFEN\n還原局面", "產生 features\n43 planes", "產生 labels\n13,689 類", "輸出 NPZ"], 0.8, 1.75, 11.7, 0.85, [C.green, C.cyan, C.green, C.cyan, C.yellow, "E2E8F0"]);
  code(s, "python export_policy_dataset.py \\\n  --database DB11211213 \\\n  --output out/policy_dataset.policy_only_latest.npz", 1.55, 3.18, 10.1, 1.1, 8.5);
  bullets(s, ["前處理負責把資料庫中可查詢、可保存的棋譜資料，轉成神經網路可直接吃的張量。", "同時檢查局面與走法是否能對齊，避免模型學到錯誤標籤。"], 1.35, 4.65, 10.4, 0.9, { fontSize: 12 });
  notes(s, ["強調資料庫與數據科學的銜接：資料庫是來源，NPZ 是訓練格式。"]);

  s = add("局面特徵編碼", "43 個 planes 保留棋盤、持駒與輪次資訊");
  table(s, 0.9, 1.55, 7.4, 2.35, [
    ["Plane 範圍", "內容"],
    ["0-13", "先手 14 種棋子在 9x9 棋盤上的位置"],
    ["14-27", "後手 14 種棋子的位置"],
    ["28-41", "持駒資訊，表示手中可打入的棋子"],
    ["42", "side-to-move，表示輪到哪一方行動"],
  ], [0.26, 0.74]);
  labeledCard(s, 8.75, 1.55, 3.25, 1.1, "為什麼用 planes", "CNN 擅長讀取空間結構；把不同棋子拆成不同平面，可避免單一整數編碼造成大小關係誤導。", C.white, C.blue);
  labeledCard(s, 8.75, 2.9, 3.25, 1.0, "為什麼不用文字", "棋盤文字適合儲存與查詢，但訓練時需要固定大小、可批次運算的數值張量。", C.white, C.green);
  notes(s, ["補充 one-hot/plane 編碼是把類別特徵轉成空間特徵，方便卷積核掃描。"]);

  s = add("走法標籤與 Rule Mask", "13,689 類候選動作，合法性由規則過濾");
  metrics(s, [
    { k: "policy logits", v: "13,122", c: C.blue },
    { k: "drop / promotion", v: "567", c: "B7791F" },
    { k: "label space", v: "13,689", c: "059669" },
  ], 1.55);
  flow(s, ["policy logits", "legal move rows", "Rule Mask", "legal softmax"], 2.0, 3.35, 9.3, 0.75, [C.cyan, C.green, C.yellow, "E2E8F0"]);
  bullets(s, ["模型輸出完整動作空間的分數，Rule Mask 把當前局面不合法的手排除。", "使用 Rule Mask 是因為將棋合法手受棋子走法、打入限制、升變與王手狀態影響，單靠 CNN 很難保證永遠合法。"], 1.25, 4.55, 10.8, 1.0, { fontSize: 12 });
  notes(s, ["說明 softmax 前遮罩：非法手不參與機率分布，模型只在合法手中排序。"]);

  s = add("Policy-only 模型架構", "CNN 輸入 43x9x9，輸出走法機率");
  code(s, "features: [batch, 43, 9, 9]\nConv2d(43, C, 3, padding=1) + ReLU\nResidual / Conv blocks\nFlatten / global features\nLinear(..., 13689)\nsoftmax over legal moves", 0.95, 1.55, 5.3, 2.95, 8.5);
  labeledCard(s, 6.75, 1.55, 2.65, 1.1, "Policy-only", "只學下一手分布，不輸出 value head。", C.white, C.blue);
  labeledCard(s, 9.7, 1.55, 2.7, 1.1, "移除 value", "資料主要來自走法監督，局面勝率標籤不足；保留 value 會讓訓練目標混雜。", C.white, "BE123C");
  labeledCard(s, 6.75, 2.95, 5.65, 1.15, "輸出意義", "每個 logit 是某個候選走法的偏好分數；經過合法手遮罩與 softmax 後，形成可排序的走法候選。", C.white, C.green);
  notes(s, ["清楚說明以前 value head 的問題與拿掉原因：資料標籤、任務定義與訓練穩定性。"]);

  s = add("捲積與激活函數", "卷積抓局部棋形，ReLU 保留非線性判斷");
  code(s, "out[c, r, f] = Σ input[p, r+i, f+j] * kernel[c,p,i,j]\nReLU(x) = max(0, x)", 0.95, 1.55, 5.5, 1.15, 8.2);
  labeledCard(s, 6.8, 1.55, 2.55, 1.12, "為何使用卷積", "棋子攻防、鄰近威脅、成區附近的型態都具有局部空間關係。", C.white, C.blue);
  labeledCard(s, 9.65, 1.55, 2.65, 1.12, "為何使用 ReLU", "計算簡單、梯度穩定，可避免多層網路只剩線性組合。", C.white, "059669");
  labeledCard(s, 1.1, 3.15, 11.1, 1.2, "為何搭配規則", "卷積能學到「像好棋」的模式，但不能形式化保證二步、打步詰、王手逃避等規則；Rule Mask 補上棋理合法性。", C.yellow, "B7791F");
  notes(s, ["這頁是理論細節：卷積核共享參數、掃描棋盤；ReLU 是非線性激活。"]);

  s = add("訓練方法", "CrossEntropy、AdamW、Cosine Scheduler 與 game-level split");
  labeledCard(s, 0.85, 1.55, 2.65, 1.05, "CrossEntropy", "把正解走法視為類別標籤，最小化 -log P(correct move)。", C.white, C.blue);
  labeledCard(s, 3.78, 1.55, 2.65, 1.05, "AdamW", "自適應學習率並分離 weight decay，讓大模型訓練較穩。", C.white, "059669");
  labeledCard(s, 6.72, 1.55, 2.65, 1.05, "Cosine LR", "逐步降低 learning rate，後期更細緻收斂。", C.white, "B7791F");
  labeledCard(s, 9.65, 1.55, 2.65, 1.05, "Game-level split", "同一棋局不切到 train/valid 兩邊，避免資料洩漏。", C.white, "BE123C");
  code(s, "loss = cross_entropy(policy_logits[:, legal], target_label)\noptimizer = AdamW(model.parameters(), lr=..., weight_decay=...)", 1.45, 3.3, 10.5, 1.0, 8.5);
  notes(s, ["把訓練講成標準分類問題，並說明 game-level split 的重要性。"]);

  s = add("訓練結果", "Top-1 41.10%，Top-5 65.24%，Best validation 74.49%");
  metrics(s, [
    { k: "Top-1 accuracy", v: "41.10%", c: C.blue },
    { k: "Top-5 accuracy", v: "65.24%", c: "059669" },
    { k: "Best validation", v: "74.49%", c: "B7791F" },
  ], 1.55);
  table(s, 1.45, 3.05, 10.25, 1.55, [
    ["項目", "數值"],
    ["Train samples", "3,884,238"],
    ["Validation samples", "485,293"],
    ["Test samples", "485,642"],
    ["Best epoch", "15"],
  ], [0.35, 0.65]);
  txt(s, "結果解讀：Top-1 代表直接猜中下一手；Top-5 更貼近搜尋使用情境，因為搜尋會從多個候選手中再評估。", 1.45, 4.85, 10.25, 0.45, { fontSize: 11, color: C.ink });
  notes(s, ["提醒不要只看 Top-1，因為 policy network 主要是縮小搜尋分支。"]);

  s = add("Alpha-beta 搜尋概論", "用剪枝減少 minimax 的展開量");
  labeledCard(s, 0.95, 1.55, 3.1, 0.95, "Minimax / Negamax", "假設雙方都選擇對自己最有利的走法。", C.white, C.blue);
  labeledCard(s, 4.35, 1.55, 3.1, 0.95, "Alpha-beta pruning", "當某分支不可能影響最終選擇，就停止深入。", C.white, "059669");
  labeledCard(s, 7.75, 1.55, 3.1, 0.95, "Quiescence", "在吃子或王手等劇烈局面延伸，避免 horizon effect。", C.white, "B7791F");
  code(s, "score = -alpha_beta(child, depth-1, -beta, -alpha)\nif score >= beta: cutoff\nif score > alpha: alpha = score", 2.55, 3.45, 8.0, 1.05, 8.5);
  notes(s, ["講 alpha 是目前已知下界，beta 是對手能接受的上界；排序越好，剪枝越有效。"]);

  s = add("手工評估函數", "在搜尋葉節點估計局面好壞");
  bullets(s, ["材料分：王以外各棋子的價值，例如飛、角、金、銀、桂、香、步。", "位置分：棋子靠近成區、王的安全、攻防效率可加入加權。", "持駒分：將棋可打入，手中棋子本身就是戰術資源。", "局限：手工規則可解釋，但難完整捕捉長期戰略與複雜手筋。"], 1.0, 1.55, 6.1, 2.2, { fontSize: 12 });
  labeledCard(s, 7.65, 1.75, 3.85, 0.9, "rule-based 評分", "eval(position) = material + piece-square + king safety + hand pieces", C.white, C.blue);
  labeledCard(s, 7.65, 3.05, 3.85, 0.9, "與 policy 的分工", "policy 負責排序候選手，評估函數負責葉節點分數。", C.white, C.green);
  notes(s, ["說明目前沒有 value head，所以葉節點仍靠手工評估。"]);

  s = add("Policy Network 結合 Alpha-beta", "用 policy 排序候選手，提高剪枝效率");
  flow(s, ["輸入局面", "產生合法手", "Policy Top-k 排序", "Alpha-beta 展開", "手工評估葉節點", "選擇最佳手"], 0.8, 2.0, 11.8, 0.85, [C.green, C.cyan, C.yellow, C.green, C.cyan, "E2E8F0"]);
  txt(s, "關鍵效果：好的 move ordering 會讓 alpha-beta 更早找到強候選手，因此更多差分支會被剪掉。", 1.25, 3.55, 10.8, 0.5, { fontSize: 13, bold: true, color: C.ink });
  labeledCard(s, 1.35, 4.35, 10.5, 0.75, "實作概念", "policy 不直接取代搜尋，而是把搜尋資源集中在較有希望的走法上；最後仍由搜尋結果決定落子。", C.white, C.blue);
  notes(s, ["這頁是整個 AI 推論流程重點。"]);

  s = add("限制與改進方向", "目前模型可用，但仍有資料、架構與搜尋上的提升空間");
  labeledCard(s, 0.85, 1.55, 3.35, 1.05, "資料偏差", "棋譜來源與棋力分布會影響模型學到的風格。", C.white, C.blue);
  labeledCard(s, 4.55, 1.55, 3.35, 1.05, "模型深度", "可加入更完整的 residual blocks、BatchNorm 或注意力特徵。", C.white, "059669");
  labeledCard(s, 8.25, 1.55, 3.35, 1.05, "Legal Move Mask", "需要持續補齊特殊規則測試，降低邊界錯誤。", C.white, "B7791F");
  labeledCard(s, 2.05, 3.25, 9.2, 1.05, "未來：Self-play / Value", "若能產生可靠勝率標籤或 self-play 結果，再重新加入 value head 會更合理。", C.white, "BE123C");
  notes(s, ["說明不是永遠不要 value，而是目前資料條件下 policy-only 更符合任務。"]);

  s = add("結論", "資料、模型、規則與搜尋共同形成可運作的將棋 AI");
  bullets(s, ["4,855,173 筆局面資料讓 supervised policy learning 具備規模。", "43 個 feature planes 保留棋盤空間結構，適合 CNN 學習。", "Policy-only 架構讓任務聚焦於走法預測，移除不穩定的 value 目標。", "Rule Mask 保證合法性；Alpha-beta 與手工評估補上搜尋與勝負推理。", "未來可朝更深模型、資料清理、自我對弈與更完整評估函數前進。"], 2.0, 1.65, 9.4, 2.7, { fontSize: 13 });
  labeledCard(s, 1.45, 5.35, 10.5, 0.65, "一句話總結", "Policy Network 負責提出好候選手，Alpha-beta 負責在候選手中做更深的局面推理。", C.cyan, C.blue);
  notes(s, ["收尾時回到課堂要求的理論與應用：資料科學流程加上搜尋應用。"]);

  return pptx;
}

function databaseDeck() {
  const pptx = deck();
  const slides = [];
  function add(label, t) {
    const s = pptx.addSlide();
    if (slides.length === 0) cover(s, "資料庫系統與設計", "資料庫目標、ER 圖、Relational Model 與 CREATE SQL");
    else { s.background = { color: C.bg }; header(s, label, slides.length + 1); title(s, t); }
    slides.push(s);
    return s;
  }

  let s = add("", "");
  notes(s, ["開場說明資料庫負責把棋譜保存成可查詢、可匯出、可訓練的結構。"]);

  s = add("系統目標", "讓棋譜資料可保存、可查詢、可重建、可訓練");
  bullets(s, ["集中保存 game、position、move、player、event 與 import batch 資訊。", "支援從 CSA 棋譜匯入 MySQL，再匯出成 policy-only 訓練資料集。", "保存 Position 與 Move 的對齊關係，確保每個局面都有正確下一手。", "讓後續查詢、統計、資料清理與模型訓練可以重複執行。"], 0.95, 1.55, 7.0, 2.3, { fontSize: 12.2 });
  labeledCard(s, 8.35, 1.65, 3.3, 1.35, "資料庫在系統中的角色", "不是只存檔案，而是把棋譜拆成有語意的實體與關聯，讓資料科學流程可以可靠使用。", C.white, C.blue);
  notes(s, ["強調資料庫設計的中心：結構化、可追蹤、可重建。"]);

  s = add("系統架構", "CSA 檔案到模型訓練的資料管線");
  flow(s, ["CSA 檔案", "import script", "MySQL tables", "查詢 / 統計", "NPZ dataset", "policy training"], 0.82, 1.75, 11.8, 0.85, [C.cyan, C.green, C.yellow, C.green, C.cyan, "E2E8F0"]);
  labeledCard(s, 1.0, 3.15, 3.6, 1.0, "匯入端", "解析棋譜、建立棋局、逐手產生 positions 與 moves。", C.white, C.blue);
  labeledCard(s, 4.85, 3.15, 3.6, 1.0, "資料庫端", "用主鍵、外鍵、索引保證資料關聯與查詢效率。", C.white, "059669");
  labeledCard(s, 8.7, 3.15, 3.6, 1.0, "訓練端", "依照 position ply 對齊 move，產生 features 與 labels。", C.white, "B7791F");
  notes(s, ["講出整體架構，後面每一頁都回到這條管線。"]);

  s = add("需求分析", "資料庫必須回答三類問題");
  labeledCard(s, 0.9, 1.55, 3.35, 1.25, "資料保存", "一盤棋、每個局面、每一步、玩家與匯入批次都要能追蹤。", C.white, C.blue);
  labeledCard(s, 4.65, 1.55, 3.35, 1.25, "資料查詢", "可依棋局、玩家、日期、棋子走法、局面 ply 查詢。", C.white, "059669");
  labeledCard(s, 8.4, 1.55, 3.35, 1.25, "資料輸出", "可穩定匯出成模型訓練需要的 X/y，避免樣本重複或錯位。", C.white, "B7791F");
  table(s, 1.35, 3.35, 10.5, 1.4, [
    ["需求", "設計回應"],
    ["完整性", "PRIMARY KEY、FOREIGN KEY、UNIQUE 約束"],
    ["效能", "game_id、position_id、ply、label 欄位建立索引"],
    ["可追蹤", "import_batches 紀錄來源、時間、狀態與錯誤"],
  ], [0.28, 0.72]);
  notes(s, ["說明需求如何轉成資料庫設計選擇。"]);

  s = add("資料庫設計方法", "先找實體，再決定關聯、鍵與正規化");
  flow(s, ["辨識實體", "定義屬性", "建立關聯", "正規化", "建立索引", "設計匯出查詢"], 0.95, 1.7, 11.45, 0.8, [C.green, C.cyan, C.green, C.cyan, C.yellow, "E2E8F0"]);
  bullets(s, ["Game 是一盤棋的根；Position 是某一手前後的局面；Move 是從某局面採取的動作。", "一盤棋有多個 position 與 move；position 和 move 透過 game_id 與 ply 對齊。", "可重複資訊拆成獨立表，例如 player、event、import_batch，降低冗餘。"], 1.25, 3.1, 10.5, 1.35, { fontSize: 12 });
  notes(s, ["這頁把 ER 與 relational model 的設計理由先鋪好。"]);

  s = add("ER 圖", "核心實體：Game、Position、Move、Player、ImportBatch");
  const nodes = [
    ["ImportBatch", 0.8, 1.55, C.yellow],
    ["Game", 3.35, 1.55, C.cyan],
    ["Position", 6.05, 1.55, C.green],
    ["Move", 9.0, 1.55, C.green],
    ["Player", 3.35, 3.5, C.white],
    ["Event", 0.8, 3.5, C.white],
  ];
  nodes.forEach(([n, x, y, f]) => labeledCard(s, x, y, 1.9, 0.82, n, "PK / attributes", f, C.blue));
  flow(s, ["1:N", "1:N", "1:1 by ply"], 2.65, 2.0, 6.65, 0.32, ["E2E8F0"]);
  slideLine(s, 2.7, 1.95, 3.35, 1.95);
  slideLine(s, 5.25, 1.95, 6.05, 1.95);
  slideLine(s, 7.95, 1.95, 9.0, 1.95);
  slideLine(s, 4.25, 2.37, 4.25, 3.5);
  slideLine(s, 2.7, 3.91, 3.35, 3.91);
  txt(s, "重點：Position 與 Move 是訓練資料的核心對齊點，Game 則提供同一盤棋內的順序與切分邊界。", 1.15, 5.15, 10.9, 0.55, { fontSize: 12.2, bold: true });
  notes(s, ["可口頭說明基數：ImportBatch 1:N Game，Game 1:N Position/Move，Position 與 Move 透過 ply 對齊。"]);

  s = add("Relational Model", "把 ER 圖落成資料表與外鍵");
  table(s, 0.8, 1.45, 11.85, 3.0, [
    ["Relation", "Primary Key", "Foreign Keys / 重要欄位"],
    ["import_batches", "batch_id", "source_path, imported_at, status"],
    ["games", "game_id", "batch_id, black_player_id, white_player_id, event_id"],
    ["positions", "position_id", "game_id, ply, sfen, side_to_move"],
    ["moves", "move_id", "game_id, ply, usi, csa, from_sq, to_sq, promote"],
    ["players", "player_id", "name, rating"],
    ["events", "event_id", "name, played_at"],
  ], [0.22, 0.22, 0.56]);
  txt(s, "資料科學匯出時主要讀取 positions JOIN moves，依 game_id + ply 取得「局面 -> 下一手」。", 1.0, 4.85, 11.2, 0.45, { fontSize: 11.2, bold: true, color: C.ink });
  notes(s, ["講 relational model 是 ER 的實作版本，表、鍵、欄位都要明確。"]);

  s = add("資料表設計", "Position 與 Move 分表，保留查詢彈性與訓練對齊");
  labeledCard(s, 0.85, 1.45, 3.5, 1.2, "games", "保存整盤棋的 metadata，提供 game-level split。", C.white, C.blue);
  labeledCard(s, 4.9, 1.45, 3.5, 1.2, "positions", "保存每個 ply 的 SFEN 與輪次，是 feature 的來源。", C.white, "059669");
  labeledCard(s, 8.95, 1.45, 3.5, 1.2, "moves", "保存實際走法與 label 所需資訊，是 target 的來源。", C.white, "B7791F");
  table(s, 1.35, 3.2, 10.4, 1.55, [
    ["設計點", "原因"],
    ["UNIQUE(game_id, ply) on positions", "同一盤棋同一手數只有一個局面"],
    ["UNIQUE(game_id, ply) on moves", "同一局面只對應棋譜中的下一手"],
    ["INDEX(game_id, ply)", "快速依序重建棋局與匯出訓練樣本"],
  ], [0.36, 0.64]);
  notes(s, ["把資料表設計和功能連起來：查詢、重建、訓練。"]);

  s = add("如何 Create", "用 SQL 建立核心資料表、約束與索引");
  code(s, `CREATE TABLE games (
  game_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id BIGINT,
  black_player_id BIGINT,
  white_player_id BIGINT,
  result ENUM('BLACK_WIN','WHITE_WIN','DRAW','SENNICHITE'),
  start_time DATETIME,
  FOREIGN KEY (batch_id) REFERENCES import_batches(batch_id)
);

CREATE TABLE positions (
  position_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  game_id BIGINT NOT NULL,
  ply INT NOT NULL,
  sfen TEXT NOT NULL,
  side_to_move CHAR(1) NOT NULL,
  UNIQUE KEY uq_position_game_ply (game_id, ply),
  FOREIGN KEY (game_id) REFERENCES games(game_id)
);`, 0.75, 1.35, 5.8, 4.85, 6.4);
  code(s, `CREATE TABLE moves (
  move_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  game_id BIGINT NOT NULL,
  ply INT NOT NULL,
  usi VARCHAR(16) NOT NULL,
  csa VARCHAR(16),
  from_sq VARCHAR(8),
  to_sq VARCHAR(8),
  piece VARCHAR(8),
  promote BOOLEAN DEFAULT FALSE,
  label_id INT,
  UNIQUE KEY uq_move_game_ply (game_id, ply),
  INDEX idx_move_label (label_id),
  FOREIGN KEY (game_id) REFERENCES games(game_id)
);`, 6.8, 1.35, 5.8, 4.85, 6.4);
  notes(s, ["這頁是資料庫報告要求的 CREATE 程式碼，重點講 PK、FK、UNIQUE、INDEX。"]);

  s = add("資料匯入", "匯入流程要能重跑、能追蹤、能檢查錯誤");
  flow(s, ["掃描 CSA", "解析 header", "建立 game", "逐手產生 position", "寫入 move", "紀錄 batch 狀態"], 0.85, 1.65, 11.75, 0.85, [C.cyan, C.green, C.yellow, C.green, C.cyan, "E2E8F0"]);
  code(s, "python import_csa_to_db.py \\\n  --input /path/to/csa \\\n  --host 140.135.65.53 --port 3306 \\\n  --user l1211213 --database DB11211213 \\\n  --skip-existing --create-tables", 1.45, 3.0, 10.3, 1.25, 8.0);
  bullets(s, ["batch table 保存匯入狀態，避免中斷後不知道進度。", "skip-existing 可避免重複匯入同一棋譜。", "create-tables 讓第一次部署可直接建立 schema。"], 1.35, 4.6, 10.5, 0.95, { fontSize: 11.5 });
  notes(s, ["講匯入不是單純 insert，而是 ETL：extract, transform, load。"]);

  s = add("Position 與 Move 對齊", "game_id + ply 是 supervised learning 的生命線");
  table(s, 0.95, 1.55, 6.4, 2.2, [
    ["資料", "對齊欄位", "用途"],
    ["positions", "game_id, ply", "模型輸入 X"],
    ["moves", "game_id, ply", "正解標籤 y"],
    ["games", "game_id", "切分 train/valid/test"],
  ], [0.28, 0.28, 0.44]);
  labeledCard(s, 7.8, 1.65, 3.95, 1.05, "設計理由", "若局面與下一手錯位，模型會把正確棋形配到錯誤走法，訓練結果會失真。", C.white, "BE123C");
  code(s, "SELECT p.sfen, m.usi, m.label_id\nFROM positions p\nJOIN moves m\n  ON p.game_id = m.game_id\n AND p.ply = m.ply\nWHERE p.game_id = ?\nORDER BY p.ply;", 7.8, 3.05, 3.95, 1.7, 7.2);
  notes(s, ["強調這是資料庫設計最重要的一頁：對齊錯了，模型就全錯。"]);

  s = add("查詢功能", "用 SQL 支援統計、除錯與資料集匯出");
  code(s, `-- 查某盤棋的完整序列
SELECT p.ply, p.sfen, m.usi
FROM positions p
JOIN moves m ON p.game_id=m.game_id AND p.ply=m.ply
WHERE p.game_id = 1001
ORDER BY p.ply;

-- 統計常見走法標籤
SELECT label_id, COUNT(*) AS n
FROM moves
GROUP BY label_id
ORDER BY n DESC
LIMIT 20;`, 0.85, 1.42, 5.65, 3.7, 7.1);
  code(s, `-- 匯出訓練樣本
SELECT g.game_id, p.ply, p.sfen, m.usi, m.label_id
FROM games g
JOIN positions p ON g.game_id=p.game_id
JOIN moves m
  ON p.game_id=m.game_id AND p.ply=m.ply
WHERE m.label_id IS NOT NULL
ORDER BY g.game_id, p.ply;`, 6.85, 1.42, 5.65, 3.7, 7.1);
  notes(s, ["讓聽眾看到 SQL 如何直接支援功能，不只是概念。"]);

  s = add("如何支援各項功能", "資料庫設計對應到系統功能");
  table(s, 0.9, 1.5, 11.6, 3.25, [
    ["功能", "需要的資料表 / 欄位", "設計如何支援"],
    ["棋局重建", "games, positions, moves", "依 game_id + ply 排序即可重建"],
    ["資料集匯出", "positions.sfen, moves.label_id", "JOIN 後形成 X/y"],
    ["訓練切分", "games.game_id", "game-level split 防止資料洩漏"],
    ["匯入追蹤", "import_batches.status", "記錄來源、時間、錯誤與批次"],
    ["查詢統計", "label_id, result, player_id", "索引加速 group by 與篩選"],
  ], [0.22, 0.28, 0.5]);
  notes(s, ["這頁是總結資料庫設計和功能的對應關係。"]);

  s = add("限制與改進方向", "目前 schema 可運作，仍可強化品質控管與效能");
  labeledCard(s, 0.85, 1.55, 3.35, 1.1, "資料品質", "可加入更完整的棋譜 checksum、非法手檢查與匯入錯誤表。", C.white, C.blue);
  labeledCard(s, 4.55, 1.55, 3.35, 1.1, "查詢效能", "大量資料下可評估 partition、covering index 或 materialized summary。", C.white, "059669");
  labeledCard(s, 8.25, 1.55, 3.35, 1.1, "資料版本", "NPZ 匯出應記錄 dataset version，對應模型訓練紀錄。", C.white, "B7791F");
  labeledCard(s, 2.05, 3.3, 9.2, 1.0, "未來方向", "增加 schema migration、匯入測試、資料血緣紀錄，讓研究結果更可重現。", C.white, "BE123C");
  notes(s, ["提出改善方向要和資料庫課程連結：完整性、效能、版本、可維護性。"]);

  s = add("結論", "好的資料庫設計讓 AI 訓練資料可靠且可重現");
  bullets(s, ["資料庫目標是把棋譜拆成可查詢的 Game、Position、Move 等實體。", "ER 圖描述實體與關聯，Relational Model 把它落成表、鍵、外鍵與索引。", "CREATE SQL 透過 PK、FK、UNIQUE 與 INDEX 保證完整性與查詢效率。", "Position 與 Move 的 game_id + ply 對齊，是產生正確 supervised dataset 的關鍵。", "資料庫支援匯入、查詢、統計、匯出與模型訓練，是整個 shogiAI 的資料底座。"], 1.85, 1.62, 9.8, 2.75, { fontSize: 13 });
  labeledCard(s, 1.45, 5.35, 10.5, 0.65, "一句話總結", "資料庫把棋譜整理成可靠的關聯資料，模型才能學到正確的局面與走法對應。", C.cyan, C.blue);
  notes(s, ["結尾回扣設計主題：資料庫不是附屬，而是模型可靠性的前提。"]);

  return pptx;
}

function slideLine(slide, x1, y1, x2, y2) {
  slide.addShape(SHAPE.line, {
    x: x1,
    y: y1,
    w: x2 - x1,
    h: y2 - y1,
    line: { color: C.muted, width: 1.2, beginArrowType: "none", endArrowType: "triangle" },
  });
}

async function main() {
  const data = dataScienceDeck();
  const db = databaseDeck();
  const dataPath = path.join(OUT_DIR, "shogiAI_data_science_final_15min.pptx");
  const dbPath = path.join(OUT_DIR, "shogiAI_database_system_final_15min.pptx");
  await data.writeFile({ fileName: dataPath });
  await db.writeFile({ fileName: dbPath });
  console.log(JSON.stringify({ dataPath, dbPath }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
