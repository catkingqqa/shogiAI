const browserTab = document.querySelector("#browserTab");
const selfPlayTab = document.querySelector("#selfPlayTab");
const aiPlayTab = document.querySelector("#aiPlayTab");
const browserView = document.querySelector("#browserView");
const selfPlayView = document.querySelector("#selfPlayView");
const aiPlayView = document.querySelector("#aiPlayView");

const gameSelect = document.querySelector("#gameSelect");
const boardEl = document.querySelector("#board");
const firstBtn = document.querySelector("#firstBtn");
const prevBtn = document.querySelector("#prevBtn");
const nextBtn = document.querySelector("#nextBtn");
const lastBtn = document.querySelector("#lastBtn");
const plyStatus = document.querySelector("#plyStatus");
const lastMove = document.querySelector("#lastMove");
const gameMeta = document.querySelector("#gameMeta");
const blackName = document.querySelector("#blackName");
const whiteName = document.querySelector("#whiteName");
const blackHands = document.querySelector("#blackHands");
const whiteHands = document.querySelector("#whiteHands");
const moveList = document.querySelector("#moveList");
const moveListCount = document.querySelector("#moveListCount");
const eventFilter = document.querySelector("#eventFilter");
const dateFromFilter = document.querySelector("#dateFromFilter");
const dateToFilter = document.querySelector("#dateToFilter");
const playerFilter = document.querySelector("#playerFilter");
const openingFilter = document.querySelector("#openingFilter");
const searchBtn = document.querySelector("#searchBtn");
const clearSearchBtn = document.querySelector("#clearSearchBtn");
const dbSource = document.querySelector("#dbSource");
const dbGameCount = document.querySelector("#dbGameCount");
const dbPlayerCount = document.querySelector("#dbPlayerCount");
const dbMoveCount = document.querySelector("#dbMoveCount");
const dbPositionCount = document.querySelector("#dbPositionCount");
const dbDuplicateCount = document.querySelector("#dbDuplicateCount");

const selfPlayMeta = document.querySelector("#selfPlayMeta");
const selfBoard = document.querySelector("#selfBoard");
const selfBlackName = document.querySelector("#selfBlackName");
const selfWhiteName = document.querySelector("#selfWhiteName");
const selfResult = document.querySelector("#selfResult");
const selfBlackLabel = document.querySelector("#selfBlackLabel");
const selfWhiteLabel = document.querySelector("#selfWhiteLabel");
const selfBlackHands = document.querySelector("#selfBlackHands");
const selfWhiteHands = document.querySelector("#selfWhiteHands");
const selfFirstBtn = document.querySelector("#selfFirstBtn");
const selfUndoBtn = document.querySelector("#selfUndoBtn");
const selfRedoBtn = document.querySelector("#selfRedoBtn");
const selfLastBtn = document.querySelector("#selfLastBtn");
const selfPlyStatus = document.querySelector("#selfPlyStatus");
const selfLastMove = document.querySelector("#selfLastMove");
const selfMoveList = document.querySelector("#selfMoveList");
const selfMoveListCount = document.querySelector("#selfMoveListCount");
const downloadCsaBtn = document.querySelector("#downloadCsaBtn");
const resetSelfPlayBtn = document.querySelector("#resetSelfPlayBtn");

const aiPlayMeta = document.querySelector("#aiPlayMeta");
const aiPlayerSide = document.querySelector("#aiPlayerSide");
const aiDepth = document.querySelector("#aiDepth");
const aiTimeLimit = document.querySelector("#aiTimeLimit");
const startAiPlayBtn = document.querySelector("#startAiPlayBtn");
const resignAiPlayBtn = document.querySelector("#resignAiPlayBtn");
const aiScore = document.querySelector("#aiScore");
const aiSearchDepth = document.querySelector("#aiSearchDepth");
const aiNodes = document.querySelector("#aiNodes");
const aiValue = document.querySelector("#aiValue");
const aiPv = document.querySelector("#aiPv");
const aiCandidateCount = document.querySelector("#aiCandidateCount");
const aiCandidateList = document.querySelector("#aiCandidateList");
const aiBoard = document.querySelector("#aiBoard");
const aiBlackLabel = document.querySelector("#aiBlackLabel");
const aiWhiteLabel = document.querySelector("#aiWhiteLabel");
const aiBlackHands = document.querySelector("#aiBlackHands");
const aiWhiteHands = document.querySelector("#aiWhiteHands");
const aiPlyStatus = document.querySelector("#aiPlyStatus");
const aiLastMove = document.querySelector("#aiLastMove");
const aiMoveList = document.querySelector("#aiMoveList");
const aiMoveListCount = document.querySelector("#aiMoveListCount");

let activeMode = "browser";
let currentGameId = "";
let currentPly = 0;
let maxPly = 0;
let latestState = null;

let selfMoves = [];
let selfRedoMoves = [];
let selfState = null;
let selectedSelfSource = null;
let selfPlayLoaded = false;
let selfResultManuallySet = false;
let selfResultWasAuto = false;

let aiMoves = [];
let aiState = null;
let aiSelectedSource = null;
let aiPlayLoaded = false;
let aiThinking = false;
let aiResignedSide = null;

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function sideLabel(color) {
  return color === "+" ? "先手" : "後手";
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-TW");
}

function renderDbStats(stats) {
  dbSource.textContent = stats.database ? `${stats.source} / ${stats.database}` : stats.source;
  dbGameCount.textContent = formatNumber(stats.games);
  dbPlayerCount.textContent = formatNumber(stats.players);
  dbMoveCount.textContent = formatNumber(stats.moves);
  dbPositionCount.textContent = formatNumber(stats.positions);
  dbDuplicateCount.textContent = formatNumber(stats.duplicateGroups);
}

async function loadDbStats() {
  try {
    const data = await fetchJson("/api/db/stats");
    renderDbStats(data.stats);
  } catch {
    for (const el of [dbSource, dbGameCount, dbPlayerCount, dbMoveCount, dbPositionCount, dbDuplicateCount]) {
      el.textContent = "-";
    }
  }
}

function formatMoveNotation(move) {
  if (!move || !move.to || !move.label) {
    return move?.text || "";
  }
  const origin = move.from || "打";
  return `${move.ply}手目 ${sideLabel(move.color)}${move.to}${move.label}(${origin})`;
}

function pieceClass(piece) {
  const classes = ["piece", piece.color === "+" ? "black" : "white"];
  if (piece.promoted) {
    classes.push("promoted");
  }
  return classes.join(" ");
}

function setActiveMode(mode) {
  activeMode = mode;
  browserTab.classList.toggle("active", mode === "browser");
  selfPlayTab.classList.toggle("active", mode === "self-play");
  aiPlayTab.classList.toggle("active", mode === "ai-play");
  browserView.classList.toggle("active", mode === "browser");
  selfPlayView.classList.toggle("active", mode === "self-play");
  aiPlayView.classList.toggle("active", mode === "ai-play");
}

function markerStorageKey() {
  return `csa-browser-markers:${currentGameId}`;
}

function getMarkedPlies() {
  try {
    const raw = localStorage.getItem(markerStorageKey());
    const values = raw ? JSON.parse(raw) : [];
    return new Set(values.map(Number).filter((value) => Number.isInteger(value) && value >= 0));
  } catch {
    return new Set();
  }
}

function saveMarkedPlies(markedPlies) {
  localStorage.setItem(markerStorageKey(), JSON.stringify([...markedPlies].sort((a, b) => a - b)));
}

function toggleMarkedPly(ply) {
  const markedPlies = getMarkedPlies();
  if (markedPlies.has(ply)) {
    markedPlies.delete(ply);
  } else {
    markedPlies.add(ply);
  }
  saveMarkedPlies(markedPlies);
  if (latestState) {
    renderMoveList(latestState);
  }
}

function searchParams() {
  const params = new URLSearchParams();
  const filters = [
    ["event", eventFilter.value],
    ["date_from", dateFromFilter.value],
    ["date_to", dateToFilter.value],
    ["player", playerFilter.value],
    ["opening", openingFilter.value],
  ];
  for (const [key, value] of filters) {
    const trimmed = value.trim();
    if (trimmed) {
      params.set(key, trimmed);
    }
  }
  return params;
}

function clearBoardState(message) {
  currentGameId = "";
  currentPly = 0;
  maxPly = 0;
  latestState = null;
  boardEl.innerHTML = "";
  blackName.textContent = "先手";
  whiteName.textContent = "後手";
  blackHands.innerHTML = "";
  whiteHands.innerHTML = "";
  moveList.innerHTML = "";
  moveListCount.textContent = "0 手";
  plyStatus.textContent = "0 / 0";
  lastMove.textContent = "開始局面";
  gameMeta.textContent = message;
  firstBtn.disabled = true;
  prevBtn.disabled = true;
  nextBtn.disabled = true;
  lastBtn.disabled = true;
}

function renderBoardInto(container, state, options = {}) {
  const selectedSquare = options.selectedSource?.type === "board" ? options.selectedSource.square : null;
  const legalTargets = new Set(options.legalTargets || []);
  container.innerHTML = "";

  for (const row of state.board) {
    for (const cell of row) {
      const square = document.createElement("div");
      square.className = "square";
      square.dataset.square = cell.square;
      if (state.lastMove?.to === cell.square) {
        square.classList.add("last-to");
      }
      if (selectedSquare === cell.square) {
        square.classList.add("selected");
      }
      if (legalTargets.has(cell.square)) {
        square.classList.add("legal-target");
        if (cell.piece) {
          square.classList.add("occupied-target");
        }
      }

      if (cell.piece) {
        const piece = document.createElement("div");
        piece.className = pieceClass(cell.piece);
        piece.textContent = cell.piece.label;
        piece.title = `${cell.square} ${sideLabel(cell.piece.color)} ${cell.piece.label}`;
        square.appendChild(piece);
      }
      container.appendChild(square);
    }
  }
}

function renderHandsInto(container, hands, state, options = {}) {
  container.innerHTML = "";
  const legalDropPieces = new Set(options.legalDropPieces || []);
  const visible = state.handOrder
    .map((piece) => ({ piece, count: hands[piece] || 0 }))
    .filter((item) => item.count > 0);

  if (visible.length === 0) {
    const empty = document.createElement("span");
    empty.className = "hand-piece empty";
    empty.textContent = "無";
    container.appendChild(empty);
    return;
  }

  for (const item of visible) {
    const chip = document.createElement(options.interactive ? "button" : "span");
    if (options.interactive) {
      chip.type = "button";
    }
    chip.className = "hand-piece";
    chip.dataset.piece = item.piece;
    chip.textContent = `${state.pieceNames[item.piece]}×${item.count}`;
    if (options.interactive && legalDropPieces.has(item.piece)) {
      chip.classList.add("selectable");
    }
    if (options.selectedPiece === item.piece) {
      chip.classList.add("selected");
    }
    container.appendChild(chip);
  }
}

function renderMeta(state) {
  const game = state.game;
  blackName.textContent = game.black || "先手";
  whiteName.textContent = game.white || "後手";
  gameMeta.textContent = [game.event, game.opening, game.startTime, game.result ? `結果 ${game.result}` : ""]
    .filter(Boolean)
    .join(" · ") || game.name;
}

function renderStatus(state) {
  currentPly = state.ply;
  maxPly = state.maxPly;
  plyStatus.textContent = `${currentPly} / ${maxPly}`;
  lastMove.textContent = state.lastMove
    ? formatMoveNotation(state.lastMove)
    : "開始局面";

  if (state.isCheck) {
    lastMove.textContent += ` · ${state.turnLabel}被王手`;
  }

  firstBtn.disabled = currentPly <= 0;
  prevBtn.disabled = currentPly <= 0;
  nextBtn.disabled = currentPly >= maxPly;
  lastBtn.disabled = currentPly >= maxPly;
}

function createMoveListItem(move, markedPlies) {
  const ply = Number(move.ply);
  const row = document.createElement("div");
  row.className = "move-row";
  if (ply === currentPly) {
    row.classList.add("active");
  }
  if (markedPlies.has(ply)) {
    row.classList.add("marked");
  }

  const jump = document.createElement("button");
  jump.type = "button";
  jump.className = "move-jump";
  jump.dataset.ply = String(ply);
  jump.textContent = ply === 0 ? "0. 開始局面" : formatMoveNotation(move);

  const marker = document.createElement("button");
  marker.type = "button";
  marker.className = "move-marker";
  marker.dataset.ply = String(ply);
  marker.textContent = markedPlies.has(ply) ? "★" : "☆";
  marker.title = markedPlies.has(ply) ? "取消標記" : "標記重點";
  marker.setAttribute("aria-label", marker.title);
  marker.setAttribute("aria-pressed", markedPlies.has(ply) ? "true" : "false");

  row.appendChild(jump);
  row.appendChild(marker);
  return row;
}

function keepActiveMoveVisible(container, activeItem) {
  if (!activeItem) {
    return;
  }
  const containerRect = container.getBoundingClientRect();
  const itemRect = activeItem.getBoundingClientRect();
  const itemTop = itemRect.top - containerRect.top + container.scrollTop;
  const itemBottom = itemRect.bottom - containerRect.top + container.scrollTop;
  const visibleTop = container.scrollTop;
  const visibleBottom = visibleTop + container.clientHeight;

  if (itemTop < visibleTop) {
    container.scrollTop = itemTop;
  } else if (itemBottom > visibleBottom) {
    container.scrollTop = itemBottom - container.clientHeight;
  }
}

function renderMoveList(state) {
  moveList.innerHTML = "";
  const markedPlies = getMarkedPlies();
  moveListCount.textContent = `${state.maxPly} 手 · 標記 ${markedPlies.size}`;
  moveList.appendChild(createMoveListItem({ ply: 0, color: "+", text: "開始局面" }, markedPlies));
  for (const move of state.moves) {
    moveList.appendChild(createMoveListItem(move, markedPlies));
  }
  keepActiveMoveVisible(moveList, moveList.querySelector(".move-row.active"));
}

function renderState(state) {
  latestState = state;
  renderMeta(state);
  renderBoardInto(boardEl, state);
  renderHandsInto(blackHands, state.hands["+"] || {}, state);
  renderHandsInto(whiteHands, state.hands["-"] || {}, state);
  renderStatus(state);
  renderMoveList(state);
}

async function loadPosition(ply) {
  if (!currentGameId) {
    return;
  }
  const boundedPly = Math.max(0, Math.min(maxPly || ply, ply));
  const state = await fetchJson(`/api/games/${encodeURIComponent(currentGameId)}?ply=${boundedPly}`);
  renderState(state);
}

async function loadGames() {
  await loadDbStats();
  const params = searchParams();
  const url = params.toString() ? `/api/games?${params.toString()}` : "/api/games";
  const data = await fetchJson(url);
  gameSelect.innerHTML = "";

  if (data.games.length === 0) {
    clearBoardState("找不到符合條件的棋局");
    return;
  }

  for (const game of data.games) {
    const option = document.createElement("option");
    option.value = game.id;
    option.textContent = game.error ? `${game.name} - 讀取失敗` : `${game.name} (${game.moves} 手)`;
    option.disabled = Boolean(game.error);
    gameSelect.appendChild(option);
  }

  const firstPlayable = data.games.find((game) => !game.error);
  if (!firstPlayable) {
    clearBoardState("沒有可讀取的棋局");
    return;
  }

  currentGameId = firstPlayable.id;
  gameSelect.value = currentGameId;
  await loadPosition(0);
}

function legalMovesForSelection() {
  if (!selfState || !selectedSelfSource) {
    return [];
  }
  if (selectedSelfSource.type === "board") {
    return selfState.legalMoves.filter((move) => move.from === selectedSelfSource.square);
  }
  return selfState.legalMoves.filter((move) => move.isDrop && move.piece === selectedSelfSource.piece);
}

function legalDropPiecesForColor(color) {
  if (!selfState || selfState.turn !== color) {
    return [];
  }
  return selfState.legalMoves.filter((move) => move.isDrop).map((move) => move.piece);
}

function aiLegalMovesForSelection() {
  if (!aiState || !aiSelectedSource) {
    return [];
  }
  if (aiSelectedSource.type === "board") {
    return aiState.legalMoves.filter((move) => move.from === aiSelectedSource.square);
  }
  return aiState.legalMoves.filter((move) => move.isDrop && move.piece === aiSelectedSource.piece);
}

function aiLegalDropPiecesForColor(color) {
  if (!aiState || aiState.turn !== color || aiState.turn !== aiState.playerSide || aiThinking || aiState.isGameOver) {
    return [];
  }
  return aiState.legalMoves.filter((move) => move.isDrop).map((move) => move.piece);
}

function renderSelfPlayState(state) {
  selfState = state;
  syncAutomaticSelfPlayResult(state);
  const legalMoves = legalMovesForSelection();
  const legalTargets = legalMoves.map((move) => move.to);
  const selectedHandPiece = selectedSelfSource?.type === "hand" ? selectedSelfSource.piece : null;

  selfBlackLabel.textContent = selfBlackName.value.trim() || "先手";
  selfWhiteLabel.textContent = selfWhiteName.value.trim() || "後手";
  const resultText = selfResult.selectedOptions[0]?.textContent || "未設定";
  selfPlayMeta.textContent = [
    `${state.turnLabel}行棋`,
    `${state.legalMovesCount} 種合法走法`,
    state.isSennichite ? "已自動偵測千日手" : "",
    selfResult.value ? `結果 ${resultText}` : "",
  ].filter(Boolean).join(" · ");
  renderBoardInto(selfBoard, state, { selectedSource: selectedSelfSource, legalTargets });
  renderHandsInto(selfBlackHands, state.hands["+"] || {}, state, {
    interactive: true,
    selectedPiece: state.turn === "+" ? selectedHandPiece : null,
    legalDropPieces: legalDropPiecesForColor("+"),
  });
  renderHandsInto(selfWhiteHands, state.hands["-"] || {}, state, {
    interactive: true,
    selectedPiece: state.turn === "-" ? selectedHandPiece : null,
    legalDropPieces: legalDropPiecesForColor("-"),
  });

  selfPlyStatus.textContent = `${selfMoves.length} / ${selfMoves.length + selfRedoMoves.length}`;
  selfLastMove.textContent = state.lastMove
    ? formatMoveNotation(state.lastMove)
    : "開始局面";
  if (state.isCheck) {
    selfLastMove.textContent += ` · ${state.turnLabel}被王手`;
  }

  selfFirstBtn.disabled = selfMoves.length === 0;
  selfUndoBtn.disabled = selfMoves.length === 0;
  selfRedoBtn.disabled = selfRedoMoves.length === 0;
  selfLastBtn.disabled = selfRedoMoves.length === 0;
  renderSelfMoveList(state);
}

function aiResultLabel(state) {
  if (state.result === "checkmate") {
    return `${sideLabel(state.winner)}勝 · 將死`;
  }
  if (state.result === "sennichite") {
    return "千日手";
  }
  if (state.result === "resignation") {
    return `${sideLabel(state.winner)}勝 · 投了`;
  }
  return "";
}

function renderAiSearch(search, valueEstimate) {
  aiScore.textContent = search ? String(search.score) : "-";
  aiSearchDepth.textContent = search ? String(search.depth) : "-";
  aiNodes.textContent = search ? String(search.nodes) : "-";
  aiValue.textContent = valueEstimate == null ? "-" : valueEstimate.toFixed(3);
  aiPv.textContent = search?.pv?.length ? search.pv.join(" ") : "-";
}

function renderAiCandidates(candidates) {
  aiCandidateList.innerHTML = "";
  aiCandidateCount.textContent = `${candidates.length} 手`;
  if (candidates.length === 0) {
    const empty = document.createElement("div");
    empty.className = "candidate-item";
    empty.innerHTML = "<strong>尚無模型</strong><span>訓練後會顯示候選手</span>";
    aiCandidateList.appendChild(empty);
    return;
  }
  for (const [index, candidate] of candidates.entries()) {
    const item = document.createElement("div");
    item.className = "candidate-item";
    const title = document.createElement("strong");
    title.textContent = `${index + 1}. ${candidate.usi}`;
    const detail = document.createElement("span");
    detail.textContent = `${(candidate.probability * 100).toFixed(1)}% · ${candidate.label}`;
    item.appendChild(title);
    item.appendChild(detail);
    aiCandidateList.appendChild(item);
  }
}

function renderAiPlayState(state) {
  aiState = state;
  const legalMoves = aiLegalMovesForSelection();
  const legalTargets = legalMoves.map((move) => move.to);
  const selectedHandPiece = aiSelectedSource?.type === "hand" ? aiSelectedSource.piece : null;
  const resultText = aiResultLabel(state);

  aiBlackLabel.textContent = state.game.black;
  aiWhiteLabel.textContent = state.game.white;
  aiPlayMeta.textContent = [
    resultText || `${state.turnLabel}行棋`,
    aiThinking ? "AI 思考中" : "",
    !state.isGameOver && state.turn === state.playerSide ? "輪到你" : "",
    !state.isGameOver && state.turn !== state.playerSide ? "輪到 AI" : "",
    state.isSennichite ? "已偵測千日手" : "",
  ].filter(Boolean).join(" · ");
  renderAiSearch(state.search, state.valueEstimate);
  renderAiCandidates(state.policyCandidates || []);
  renderBoardInto(aiBoard, state, { selectedSource: aiSelectedSource, legalTargets });
  renderHandsInto(aiBlackHands, state.hands["+"] || {}, state, {
    interactive: true,
    selectedPiece: state.turn === "+" ? selectedHandPiece : null,
    legalDropPieces: aiLegalDropPiecesForColor("+"),
  });
  renderHandsInto(aiWhiteHands, state.hands["-"] || {}, state, {
    interactive: true,
    selectedPiece: state.turn === "-" ? selectedHandPiece : null,
    legalDropPieces: aiLegalDropPiecesForColor("-"),
  });
  aiPlyStatus.textContent = `${aiMoves.length} 手`;
  aiLastMove.textContent = state.lastMove ? formatMoveNotation(state.lastMove) : "開始局面";
  if (state.isCheck && !state.isGameOver) {
    aiLastMove.textContent += ` · ${state.turnLabel}被王手`;
  }
  resignAiPlayBtn.disabled = state.isGameOver || aiThinking;
  renderAiMoveList(state);
}

function syncAutomaticSelfPlayResult(state) {
  if (state.isSennichite && !selfResultManuallySet) {
    selfResult.value = "SENNICHITE";
    selfResultWasAuto = true;
    return;
  }
  if (!state.isSennichite && selfResultWasAuto && !selfResultManuallySet) {
    selfResult.value = "";
    selfResultWasAuto = false;
  }
}

function createPlainMoveListItem(move, ply, activePly) {
  const row = document.createElement("div");
  row.className = "move-row";
  if (ply === activePly) {
    row.classList.add("active");
  }

  const jump = document.createElement("button");
  jump.type = "button";
  jump.className = "move-jump";
  jump.dataset.ply = String(ply);
  jump.textContent = ply === 0 ? "0. 開始局面" : formatMoveNotation(move);
  row.appendChild(jump);
  return row;
}

function renderSelfMoveList(state) {
  selfMoveList.innerHTML = "";
  selfMoveListCount.textContent = `${selfMoves.length} 手 · 可還原 ${selfRedoMoves.length}`;
  selfMoveList.appendChild(createPlainMoveListItem({ color: "+", text: "開始局面" }, 0, selfMoves.length));
  state.moves.forEach((move, index) => {
    selfMoveList.appendChild(createPlainMoveListItem(move, index + 1, selfMoves.length));
  });
  keepActiveMoveVisible(selfMoveList, selfMoveList.querySelector(".move-row.active"));
}

function renderAiMoveList(state) {
  aiMoveList.innerHTML = "";
  aiMoveListCount.textContent = `${aiMoves.length} 手`;
  aiMoveList.appendChild(createPlainMoveListItem({ color: "+", text: "開始局面" }, 0, aiMoves.length));
  state.moves.forEach((move, index) => {
    aiMoveList.appendChild(createPlainMoveListItem(move, index + 1, aiMoves.length));
  });
  keepActiveMoveVisible(aiMoveList, aiMoveList.querySelector(".move-row.active"));
}

async function loadSelfPlayState() {
  const state = await postJson("/api/self-play/state", { moves: selfMoves });
  selectedSelfSource = null;
  selfPlayLoaded = true;
  renderSelfPlayState(state);
}

async function loadAiPlayState() {
  const state = await postJson("/api/ai-play/state", {
    moves: aiMoves,
    playerSide: aiPlayerSide.value,
    resignedSide: aiResignedSide,
  });
  aiSelectedSource = null;
  aiPlayLoaded = true;
  renderAiPlayState(state);
}

async function undoSelfPlay(count = 1) {
  for (let index = 0; index < count && selfMoves.length > 0; index += 1) {
    selfRedoMoves.unshift(selfMoves.pop());
  }
  await loadSelfPlayState();
}

async function redoSelfPlay(count = 1) {
  for (let index = 0; index < count && selfRedoMoves.length > 0; index += 1) {
    selfMoves.push(selfRedoMoves.shift());
  }
  await loadSelfPlayState();
}

async function rewindSelfPlayTo(ply) {
  const targetPly = Math.max(0, Math.min(selfMoves.length, ply));
  await undoSelfPlay(selfMoves.length - targetPly);
}

async function commitSelfMove(usi) {
  selfMoves.push(usi);
  selfRedoMoves = [];
  await loadSelfPlayState();
}

async function maybeRequestAiMove() {
  if (!aiState || aiState.isGameOver || aiState.turn === aiState.playerSide || aiThinking) {
    return;
  }
  aiThinking = true;
  renderAiPlayState(aiState);
  try {
    const state = await postJson("/api/ai-play/move", {
      moves: aiMoves,
      playerSide: aiPlayerSide.value,
      depth: aiDepth.value,
      timeLimitMs: aiTimeLimit.value,
    });
    aiMoves = state.moves.map((move) => move.text);
    aiSelectedSource = null;
    aiState = state;
  } finally {
    aiThinking = false;
  }
  renderAiPlayState(aiState);
}

async function commitAiMove(usi) {
  aiMoves.push(usi);
  aiSelectedSource = null;
  await loadAiPlayState();
  await maybeRequestAiMove();
}

function chooseMoveCandidate(candidates) {
  if (candidates.length <= 1) {
    return candidates[0] || null;
  }
  const promotionMove = candidates.find((move) => move.isPromotion);
  const normalMove = candidates.find((move) => !move.isPromotion);
  if (promotionMove && normalMove) {
    return window.confirm("要升變嗎？") ? promotionMove : normalMove;
  }
  return candidates[0];
}

function selfBoardPieceAt(square) {
  if (!selfState) {
    return null;
  }
  for (const row of selfState.board) {
    const cell = row.find((item) => item.square === square);
    if (cell) {
      return cell.piece;
    }
  }
  return null;
}

function aiBoardPieceAt(square) {
  if (!aiState) {
    return null;
  }
  for (const row of aiState.board) {
    const cell = row.find((item) => item.square === square);
    if (cell) {
      return cell.piece;
    }
  }
  return null;
}

function renderSelfSelection() {
  if (selfState) {
    renderSelfPlayState(selfState);
  }
}

function renderAiSelection() {
  if (aiState) {
    renderAiPlayState(aiState);
  }
}

function downloadTextFile(fileName, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

function selfPlayFileName() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `self-play-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.csa`;
}

function isFormControl(element) {
  return element instanceof HTMLInputElement
    || element instanceof HTMLTextAreaElement
    || element instanceof HTMLSelectElement;
}

browserTab.addEventListener("click", () => {
  setActiveMode("browser");
});

selfPlayTab.addEventListener("click", async () => {
  setActiveMode("self-play");
  if (!selfPlayLoaded) {
    await loadSelfPlayState();
  }
});

aiPlayTab.addEventListener("click", async () => {
  setActiveMode("ai-play");
  if (!aiPlayLoaded) {
    await loadAiPlayState();
    await maybeRequestAiMove();
  }
});

gameSelect.addEventListener("change", async () => {
  currentGameId = gameSelect.value;
  await loadPosition(0);
});

searchBtn.addEventListener("click", async () => {
  await loadGames();
});

clearSearchBtn.addEventListener("click", async () => {
  eventFilter.value = "";
  dateFromFilter.value = "";
  dateToFilter.value = "";
  playerFilter.value = "";
  openingFilter.value = "";
  await loadGames();
});

for (const input of [eventFilter, dateFromFilter, dateToFilter, playerFilter, openingFilter]) {
  input.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      await loadGames();
    }
  });
}

firstBtn.addEventListener("click", async () => {
  await loadPosition(0);
});

prevBtn.addEventListener("click", async () => {
  await loadPosition(currentPly - 1);
});

nextBtn.addEventListener("click", async () => {
  await loadPosition(currentPly + 1);
});

lastBtn.addEventListener("click", async () => {
  await loadPosition(maxPly);
});

moveList.addEventListener("click", async (event) => {
  const marker = event.target.closest(".move-marker");
  if (marker) {
    toggleMarkedPly(Number(marker.dataset.ply));
    return;
  }

  const jump = event.target.closest(".move-jump");
  if (jump) {
    await loadPosition(Number(jump.dataset.ply));
  }
});

selfBoard.addEventListener("click", async (event) => {
  if (!selfState) {
    return;
  }
  const square = event.target.closest(".square");
  if (!square) {
    return;
  }
  const squareName = square.dataset.square;
  const candidateMoves = legalMovesForSelection().filter((move) => move.to === squareName);
  if (candidateMoves.length > 0) {
    const chosenMove = chooseMoveCandidate(candidateMoves);
    if (chosenMove) {
      await commitSelfMove(chosenMove.usi);
    }
    return;
  }

  const piece = selfBoardPieceAt(squareName);
  if (piece && piece.color === selfState.turn) {
    selectedSelfSource = { type: "board", square: squareName };
  } else {
    selectedSelfSource = null;
  }
  renderSelfSelection();
});

for (const [container, color] of [[selfBlackHands, "+"], [selfWhiteHands, "-"]]) {
  container.addEventListener("click", (event) => {
    if (!selfState || selfState.turn !== color) {
      return;
    }
    const chip = event.target.closest(".hand-piece.selectable");
    if (!chip) {
      return;
    }
    const piece = chip.dataset.piece;
    if (selectedSelfSource?.type === "hand" && selectedSelfSource.piece === piece) {
      selectedSelfSource = null;
    } else {
      selectedSelfSource = { type: "hand", piece };
    }
    renderSelfSelection();
  });
}

aiBoard.addEventListener("click", async (event) => {
  if (!aiState || aiThinking || aiState.isGameOver || aiState.turn !== aiState.playerSide) {
    return;
  }
  const square = event.target.closest(".square");
  if (!square) {
    return;
  }
  const squareName = square.dataset.square;
  const candidateMoves = aiLegalMovesForSelection().filter((move) => move.to === squareName);
  if (candidateMoves.length > 0) {
    const chosenMove = chooseMoveCandidate(candidateMoves);
    if (chosenMove) {
      await commitAiMove(chosenMove.usi);
    }
    return;
  }

  const piece = aiBoardPieceAt(squareName);
  if (piece && piece.color === aiState.playerSide) {
    aiSelectedSource = { type: "board", square: squareName };
  } else {
    aiSelectedSource = null;
  }
  renderAiSelection();
});

for (const [container, color] of [[aiBlackHands, "+"], [aiWhiteHands, "-"]]) {
  container.addEventListener("click", (event) => {
    if (
      !aiState
      || aiThinking
      || aiState.isGameOver
      || aiState.turn !== color
      || aiState.turn !== aiState.playerSide
    ) {
      return;
    }
    const chip = event.target.closest(".hand-piece.selectable");
    if (!chip) {
      return;
    }
    const piece = chip.dataset.piece;
    if (aiSelectedSource?.type === "hand" && aiSelectedSource.piece === piece) {
      aiSelectedSource = null;
    } else {
      aiSelectedSource = { type: "hand", piece };
    }
    renderAiSelection();
  });
}

selfFirstBtn.addEventListener("click", async () => {
  await undoSelfPlay(selfMoves.length);
});

selfUndoBtn.addEventListener("click", async () => {
  await undoSelfPlay();
});

selfRedoBtn.addEventListener("click", async () => {
  await redoSelfPlay();
});

selfLastBtn.addEventListener("click", async () => {
  await redoSelfPlay(selfRedoMoves.length);
});

selfMoveList.addEventListener("click", async (event) => {
  const jump = event.target.closest(".move-jump");
  if (!jump) {
    return;
  }
  await rewindSelfPlayTo(Number(jump.dataset.ply));
});

for (const input of [selfBlackName, selfWhiteName]) {
  input.addEventListener("input", () => {
    if (selfState) {
      renderSelfPlayState(selfState);
    }
  });
}

selfResult.addEventListener("input", () => {
  selfResultManuallySet = true;
  selfResultWasAuto = false;
  if (selfState) {
    renderSelfPlayState(selfState);
  }
});

downloadCsaBtn.addEventListener("click", async () => {
  const data = await postJson("/api/self-play/csa", {
    moves: selfMoves,
    blackName: selfBlackName.value,
    whiteName: selfWhiteName.value,
    result: selfResult.value,
  });
  downloadTextFile(selfPlayFileName(), data.csa);
});

resetSelfPlayBtn.addEventListener("click", async () => {
  selfMoves = [];
  selfRedoMoves = [];
  selfResult.value = "";
  selfResultManuallySet = false;
  selfResultWasAuto = false;
  await loadSelfPlayState();
});

startAiPlayBtn.addEventListener("click", async () => {
  aiMoves = [];
  aiSelectedSource = null;
  aiResignedSide = null;
  await loadAiPlayState();
  await maybeRequestAiMove();
});

resignAiPlayBtn.addEventListener("click", async () => {
  if (!aiState || aiState.isGameOver) {
    return;
  }
  aiResignedSide = aiState.playerSide;
  await loadAiPlayState();
});

document.addEventListener("keydown", async (event) => {
  if (isFormControl(event.target)) {
    return;
  }
  if (activeMode === "browser") {
    if (event.key === "ArrowLeft" && currentPly > 0) {
      await loadPosition(currentPly - 1);
    }
    if (event.key === "ArrowRight" && currentPly < maxPly) {
      await loadPosition(currentPly + 1);
    }
    if (event.key === "Home") {
      await loadPosition(0);
    }
    if (event.key === "End") {
      await loadPosition(maxPly);
    }
    return;
  }

  if (activeMode !== "self-play") {
    return;
  }
  if (event.key === "ArrowLeft" && selfMoves.length > 0) {
    await undoSelfPlay();
  }
  if (event.key === "ArrowRight" && selfRedoMoves.length > 0) {
    await redoSelfPlay();
  }
  if (event.key === "Home" && selfMoves.length > 0) {
    await undoSelfPlay(selfMoves.length);
  }
  if (event.key === "End" && selfRedoMoves.length > 0) {
    await redoSelfPlay(selfRedoMoves.length);
  }
});

loadGames().catch((error) => {
  clearBoardState(error.message);
});
