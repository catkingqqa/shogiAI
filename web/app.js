// 功能：快取三個模式分頁與主要畫面容器，後續切換模式時直接更新 class。
const browserTab = document.querySelector("#browserTab");
const selfPlayTab = document.querySelector("#selfPlayTab");
const aiPlayTab = document.querySelector("#aiPlayTab");
const modelMatchTab = document.querySelector("#modelMatchTab");
const browserView = document.querySelector("#browserView");
const selfPlayView = document.querySelector("#selfPlayView");
const aiPlayView = document.querySelector("#aiPlayView");
const modelMatchView = document.querySelector("#modelMatchView");

// 功能：棋譜瀏覽模式的 DOM 元件：棋局選單、棋盤、手數控制、持駒與搜尋條件。
const gameSelect = document.querySelector("#gameSelect");
const gamePageStatus = document.querySelector("#gamePageStatus");
const loadMoreGamesBtn = document.querySelector("#loadMoreGamesBtn");
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

// 功能：自行對弈模式的 DOM 元件：棋盤、玩家名稱、結果、復原/重做與 CSA 下載。
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

// 功能：AI 對弈模式的 DOM 元件：玩家方、搜尋參數、搜尋統計、候選手與棋盤。
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

const modelMatchMeta = document.querySelector("#modelMatchMeta");
const engineMatchMeta = document.querySelector("#engineMatchMeta");
const engineAName = document.querySelector("#engineAName");
const engineBName = document.querySelector("#engineBName");
const engineAModelSelect = document.querySelector("#engineAModelSelect");
const engineBModelSelect = document.querySelector("#engineBModelSelect");
const engineADepth = document.querySelector("#engineADepth");
const engineBDepth = document.querySelector("#engineBDepth");
const engineATimeLimit = document.querySelector("#engineATimeLimit");
const engineBTimeLimit = document.querySelector("#engineBTimeLimit");
const engineAPolicyOrderPly = document.querySelector("#engineAPolicyOrderPly");
const engineBPolicyOrderPly = document.querySelector("#engineBPolicyOrderPly");
const engineMatchGames = document.querySelector("#engineMatchGames");
const engineMatchMaxPlies = document.querySelector("#engineMatchMaxPlies");
const engineMatchAdjudicateScore = document.querySelector("#engineMatchAdjudicateScore");
const runEngineMatchBtn = document.querySelector("#runEngineMatchBtn");
const oldModelSelect = document.querySelector("#oldModelSelect");
const newModelSelect = document.querySelector("#newModelSelect");
const matchGames = document.querySelector("#matchGames");
const matchDepth = document.querySelector("#matchDepth");
const matchTimeLimit = document.querySelector("#matchTimeLimit");
const matchPolicyOrderPly = document.querySelector("#matchPolicyOrderPly");
const matchMaxPlies = document.querySelector("#matchMaxPlies");
const matchAdjudicateScore = document.querySelector("#matchAdjudicateScore");
const runModelMatchBtn = document.querySelector("#runModelMatchBtn");
const matchNewWins = document.querySelector("#matchNewWins");
const matchOldWins = document.querySelector("#matchOldWins");
const matchDraws = document.querySelector("#matchDraws");
const matchScoreRate = document.querySelector("#matchScoreRate");
const matchAveragePlies = document.querySelector("#matchAveragePlies");
const matchGameCount = document.querySelector("#matchGameCount");
const matchGameList = document.querySelector("#matchGameList");
const matchReplayTitle = document.querySelector("#matchReplayTitle");
const matchReplayStatus = document.querySelector("#matchReplayStatus");
const matchBoard = document.querySelector("#matchBoard");
const matchBlackLabel = document.querySelector("#matchBlackLabel");
const matchWhiteLabel = document.querySelector("#matchWhiteLabel");
const matchBlackHands = document.querySelector("#matchBlackHands");
const matchWhiteHands = document.querySelector("#matchWhiteHands");
const matchFirstBtn = document.querySelector("#matchFirstBtn");
const matchPrevBtn = document.querySelector("#matchPrevBtn");
const matchNextBtn = document.querySelector("#matchNextBtn");
const matchLastBtn = document.querySelector("#matchLastBtn");
const matchPlyStatus = document.querySelector("#matchPlyStatus");
const matchLastMove = document.querySelector("#matchLastMove");
const matchMoveList = document.querySelector("#matchMoveList");

// 功能：全域 UI 狀態。瀏覽棋譜、自行對弈與 AI 對弈各自保存目前局面與選取狀態。
let activeMode = "browser";
let currentGameId = "";
let currentPly = 0;
let maxPly = 0;
let latestState = null;
const GAME_PAGE_SIZE = 50;
let loadedGames = [];
let nextGamesOffset = 0;
let gamesHasMore = false;
let gamesLoading = false;

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

let modelMatchLoaded = false;
let modelMatchRunning = false;
let modelMatchResult = null;
let selectedMatchGameIndex = -1;
let matchReplayPly = 0;

// 功能：處理 fetchJson 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

// 功能：處理 postJson 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 sideLabel 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function sideLabel(color) {
  return color === "+" ? "先手" : "後手";
}

// 功能：處理 formatNumber 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-TW");
}

// 功能：處理 renderDbStats 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderDbStats(stats) {
  dbSource.textContent = stats.database ? `${stats.source} / ${stats.database}` : stats.source;
  dbGameCount.textContent = formatNumber(stats.games);
  dbPlayerCount.textContent = formatNumber(stats.players);
  dbMoveCount.textContent = formatNumber(stats.moves);
  dbPositionCount.textContent = formatNumber(stats.positions);
  dbDuplicateCount.textContent = formatNumber(stats.duplicateGroups);
}

// 功能：處理 loadDbStats 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 formatMoveNotation 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function formatMoveNotation(move) {
  if (!move || !move.to || !move.label) {
    return move?.text || "";
  }
  const origin = move.from || "打";
  return `${move.ply}手目 ${sideLabel(move.color)}${move.to}${move.label}(${origin})`;
}

// 功能：處理 pieceClass 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function pieceClass(piece) {
  const classes = ["piece", piece.color === "+" ? "black" : "white"];
  if (piece.promoted) {
    classes.push("promoted");
  }
  return classes.join(" ");
}

// 功能：處理 setActiveMode 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function setActiveMode(mode) {
  activeMode = mode;
  browserTab.classList.toggle("active", mode === "browser");
  selfPlayTab.classList.toggle("active", mode === "self-play");
  aiPlayTab.classList.toggle("active", mode === "ai-play");
  modelMatchTab.classList.toggle("active", mode === "model-match");
  browserView.classList.toggle("active", mode === "browser");
  selfPlayView.classList.toggle("active", mode === "self-play");
  aiPlayView.classList.toggle("active", mode === "ai-play");
  modelMatchView.classList.toggle("active", mode === "model-match");
}

// 功能：處理 markerStorageKey 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function markerStorageKey() {
  return `csa-browser-markers:${currentGameId}`;
}

// 功能：處理 getMarkedPlies 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function getMarkedPlies() {
  try {
    const raw = localStorage.getItem(markerStorageKey());
    const values = raw ? JSON.parse(raw) : [];
    return new Set(values.map(Number).filter((value) => Number.isInteger(value) && value >= 0));
  } catch {
    return new Set();
  }
}

// 功能：處理 saveMarkedPlies 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function saveMarkedPlies(markedPlies) {
  localStorage.setItem(markerStorageKey(), JSON.stringify([...markedPlies].sort((a, b) => a - b)));
}

// 功能：處理 toggleMarkedPly 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 searchParams 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 clearBoardState 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderBoardInto 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderHandsInto 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderMeta 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderMeta(state) {
  const game = state.game;
  blackName.textContent = game.black || "先手";
  whiteName.textContent = game.white || "後手";
  gameMeta.textContent = [game.event, game.opening, game.startTime, game.result ? `結果 ${game.result}` : ""]
    .filter(Boolean)
    .join(" · ") || game.name;
}

// 功能：處理 renderStatus 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 createMoveListItem 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 keepActiveMoveVisible 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderMoveList 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderState 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderState(state) {
  latestState = state;
  renderMeta(state);
  renderBoardInto(boardEl, state);
  renderHandsInto(blackHands, state.hands["+"] || {}, state);
  renderHandsInto(whiteHands, state.hands["-"] || {}, state);
  renderStatus(state);
  renderMoveList(state);
}

// 功能：處理 loadPosition 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function loadPosition(ply) {
  if (!currentGameId) {
    return;
  }
  const boundedPly = Math.max(0, Math.min(maxPly || ply, ply));
  const state = await fetchJson(`/api/games/${encodeURIComponent(currentGameId)}?ply=${boundedPly}`);
  renderState(state);
}

// 功能：處理 loadGames 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function gamesPageUrl(offset) {
  const params = searchParams();
  params.set("limit", String(GAME_PAGE_SIZE));
  params.set("offset", String(offset));
  return `/api/games?${params.toString()}`;
}

function updateGamePageStatus() {
  if (!gamePageStatus || !loadMoreGamesBtn) {
    return;
  }
  gamePageStatus.textContent = loadedGames.length
    ? `已載入 ${loadedGames.length} 筆棋局`
    : "";
  loadMoreGamesBtn.hidden = !gamesHasMore;
  loadMoreGamesBtn.disabled = gamesLoading;
  loadMoreGamesBtn.textContent = gamesLoading ? "載入中..." : "載入更多";
}

function appendGameOptions(games) {
  for (const game of games) {
    const option = document.createElement("option");
    option.value = game.id;
    option.textContent = game.error ? `${game.name} - 讀取失敗` : `${game.name} (${game.moves} 手)`;
    option.disabled = Boolean(game.error);
    gameSelect.appendChild(option);
  }
}

async function loadGames(options = {}) {
  const append = Boolean(options.append);
  if (gamesLoading) {
    return;
  }
  gamesLoading = true;
  updateGamePageStatus();
  try {
    if (!append) {
      await loadDbStats();
      loadedGames = [];
      nextGamesOffset = 0;
      gamesHasMore = false;
      gameSelect.innerHTML = "";
    }

    const data = await fetchJson(gamesPageUrl(nextGamesOffset));
    const pageGames = data.games || [];
    loadedGames = [...loadedGames, ...pageGames];
    nextGamesOffset = Number(data.nextOffset ?? (nextGamesOffset + pageGames.length));
    gamesHasMore = Boolean(data.hasMore);
    appendGameOptions(pageGames);

    if (loadedGames.length === 0) {
      clearBoardState("找不到符合條件的棋局");
      return;
    }

    if (!append) {
      const firstPlayable = loadedGames.find((game) => !game.error);
      if (!firstPlayable) {
        clearBoardState(gamesHasMore ? "目前批次沒有可讀取的棋局，請載入更多" : "沒有可讀取的棋局");
        return;
      }
      currentGameId = firstPlayable.id;
      gameSelect.value = currentGameId;
      await loadPosition(0);
    } else if (currentGameId) {
      gameSelect.value = currentGameId;
    }
  } finally {
    gamesLoading = false;
    updateGamePageStatus();
  }
}

// 功能：處理 legalMovesForSelection 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function legalMovesForSelection() {
  if (!selfState || !selectedSelfSource) {
    return [];
  }
  if (selectedSelfSource.type === "board") {
    return selfState.legalMoves.filter((move) => move.from === selectedSelfSource.square);
  }
  return selfState.legalMoves.filter((move) => move.isDrop && move.piece === selectedSelfSource.piece);
}

// 功能：處理 legalDropPiecesForColor 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function legalDropPiecesForColor(color) {
  if (!selfState || selfState.turn !== color) {
    return [];
  }
  return selfState.legalMoves.filter((move) => move.isDrop).map((move) => move.piece);
}

// 功能：處理 aiLegalMovesForSelection 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function aiLegalMovesForSelection() {
  if (!aiState || !aiSelectedSource) {
    return [];
  }
  if (aiSelectedSource.type === "board") {
    return aiState.legalMoves.filter((move) => move.from === aiSelectedSource.square);
  }
  return aiState.legalMoves.filter((move) => move.isDrop && move.piece === aiSelectedSource.piece);
}

// 功能：處理 aiLegalDropPiecesForColor 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function aiLegalDropPiecesForColor(color) {
  if (!aiState || aiState.turn !== color || aiState.turn !== aiState.playerSide || aiThinking || aiState.isGameOver) {
    return [];
  }
  return aiState.legalMoves.filter((move) => move.isDrop).map((move) => move.piece);
}

// 功能：處理 renderSelfPlayState 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 aiResultLabel 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderAiSearch 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderAiSearch(search, valueEstimate) {
  if (search?.source === "openingBook") {
    aiScore.textContent = `Book ${Math.round((search.bookRate || 0) * 100)}%`;
    aiSearchDepth.textContent = "Book";
    aiNodes.textContent = `${search.bookCount || 0}/${search.bookTotal || 0}`;
  } else {
    aiScore.textContent = search ? String(search.score) : "-";
    aiSearchDepth.textContent = search ? String(search.depth) : "-";
    aiNodes.textContent = search ? String(search.nodes) : "-";
  }
  aiValue.textContent = valueEstimate == null ? "-" : valueEstimate.toFixed(3);
  aiPv.textContent = search?.pv?.length ? search.pv.join(" ") : "-";
}

// 功能：處理 renderAiCandidates 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderAiPlayState 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 syncAutomaticSelfPlayResult 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 createPlainMoveListItem 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderSelfMoveList 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderSelfMoveList(state) {
  selfMoveList.innerHTML = "";
  selfMoveListCount.textContent = `${selfMoves.length} 手 · 可還原 ${selfRedoMoves.length}`;
  selfMoveList.appendChild(createPlainMoveListItem({ color: "+", text: "開始局面" }, 0, selfMoves.length));
  state.moves.forEach((move, index) => {
    selfMoveList.appendChild(createPlainMoveListItem(move, index + 1, selfMoves.length));
  });
  keepActiveMoveVisible(selfMoveList, selfMoveList.querySelector(".move-row.active"));
}

// 功能：處理 renderAiMoveList 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderAiMoveList(state) {
  aiMoveList.innerHTML = "";
  aiMoveListCount.textContent = `${aiMoves.length} 手`;
  aiMoveList.appendChild(createPlainMoveListItem({ color: "+", text: "開始局面" }, 0, aiMoves.length));
  state.moves.forEach((move, index) => {
    aiMoveList.appendChild(createPlainMoveListItem(move, index + 1, aiMoves.length));
  });
  keepActiveMoveVisible(aiMoveList, aiMoveList.querySelector(".move-row.active"));
}

// 功能：處理 loadSelfPlayState 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function loadSelfPlayState() {
  const state = await postJson("/api/self-play/state", { moves: selfMoves });
  selectedSelfSource = null;
  selfPlayLoaded = true;
  renderSelfPlayState(state);
}

// 功能：處理 loadAiPlayState 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 undoSelfPlay 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function undoSelfPlay(count = 1) {
  for (let index = 0; index < count && selfMoves.length > 0; index += 1) {
    selfRedoMoves.unshift(selfMoves.pop());
  }
  await loadSelfPlayState();
}

// 功能：處理 redoSelfPlay 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function redoSelfPlay(count = 1) {
  for (let index = 0; index < count && selfRedoMoves.length > 0; index += 1) {
    selfMoves.push(selfRedoMoves.shift());
  }
  await loadSelfPlayState();
}

// 功能：處理 rewindSelfPlayTo 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function rewindSelfPlayTo(ply) {
  const targetPly = Math.max(0, Math.min(selfMoves.length, ply));
  await undoSelfPlay(selfMoves.length - targetPly);
}

// 功能：處理 commitSelfMove 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function commitSelfMove(usi) {
  selfMoves.push(usi);
  selfRedoMoves = [];
  await loadSelfPlayState();
}

// 功能：處理 maybeRequestAiMove 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 commitAiMove 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
async function commitAiMove(usi) {
  aiMoves.push(usi);
  aiSelectedSource = null;
  await loadAiPlayState();
  await maybeRequestAiMove();
}

// 功能：處理 chooseMoveCandidate 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 selfBoardPieceAt 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 aiBoardPieceAt 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
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

// 功能：處理 renderSelfSelection 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderSelfSelection() {
  if (selfState) {
    renderSelfPlayState(selfState);
  }
}

// 功能：處理 renderAiSelection 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function renderAiSelection() {
  if (aiState) {
    renderAiPlayState(aiState);
  }
}

// 功能：處理 downloadTextFile 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function downloadTextFile(fileName, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

// 功能：處理 selfPlayFileName 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function selfPlayFileName() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `self-play-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.csa`;
}

// 功能：處理 isFormControl 前端流程，負責狀態讀寫、API 互動或 DOM 畫面更新。
function isFormControl(element) {
  return element instanceof HTMLInputElement
    || element instanceof HTMLTextAreaElement
    || element instanceof HTMLSelectElement;
}

// 功能：事件綁定區：把使用者在分頁、棋盤、持駒、按鈕與鍵盤上的操作轉成狀態更新或 API 呼叫。
function fillModelSelect(select, models, preferredName) {
  if (!select) {
    return;
  }
  select.innerHTML = "";
  const noneOption = document.createElement("option");
  noneOption.value = "";
  noneOption.textContent = "不使用模型";
  select.appendChild(noneOption);
  for (const model of models) {
    const option = document.createElement("option");
    option.value = model.path;
    option.textContent = model.name;
    select.appendChild(option);
  }
  const preferred = models.find((model) => model.name === preferredName);
  if (preferred) {
    select.value = preferred.path;
  }
}

async function loadModelMatchModels() {
  const data = await fetchJson("/api/model-match/models");
  const models = data.models || [];
  fillModelSelect(oldModelSelect, models, "policy_model.prev.pt");
  fillModelSelect(newModelSelect, models, "policy_model.pt");
  fillModelSelect(engineAModelSelect, models, "policy_model.pt");
  fillModelSelect(engineBModelSelect, models, "");
  modelMatchLoaded = true;
  if (engineMatchMeta) {
    engineMatchMeta.textContent = models.length
      ? `已找到 ${models.length} 個 policy model，也可以選擇不使用模型。`
      : "目前沒有 policy model，可先用純傳統搜尋參數互打。";
  }
  modelMatchMeta.textContent = models.length
    ? `已找到 ${models.length} 個 policy model。`
    : "找不到 out/policy_model*.pt。";
}

function renderMatchSummary(match) {
  matchNewWins.textContent = String(match?.new_wins ?? "-");
  matchOldWins.textContent = String(match?.old_wins ?? "-");
  matchDraws.textContent = String(match?.draws ?? "-");
  matchScoreRate.textContent = match ? `${Math.round(match.new_score_rate * 1000) / 10}%` : "-";
  matchAveragePlies.textContent = match ? Math.round(match.average_plies * 10) / 10 : "-";
}

function resultText(game) {
  if (!game) {
    return "";
  }
  return game.winner ? `${game.winner} 勝` : "和棋";
}

function engineResultText(game) {
  if (!game) {
    return "";
  }
  if (game.result === "running") {
    return "對戰中";
  }
  return game.winner ? `${game.winner} 勝` : "和棋";
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function buildModelMatchPayload() {
  return {
    engineA: {
      name: engineAName.value.trim() || "Engine A",
      model: engineAModelSelect.value,
      depth: Number(engineADepth.value),
      timeLimitMs: Number(engineATimeLimit.value),
      policyOrderPly: Number(engineAPolicyOrderPly.value),
    },
    engineB: {
      name: engineBName.value.trim() || "Engine B",
      model: engineBModelSelect.value,
      depth: Number(engineBDepth.value),
      timeLimitMs: Number(engineBTimeLimit.value),
      policyOrderPly: Number(engineBPolicyOrderPly.value),
    },
    games: Number(engineMatchGames.value),
    maxPlies: Number(engineMatchMaxPlies.value),
    adjudicateScore: Number(engineMatchAdjudicateScore.value),
  };
}

function refreshLiveMatchSummary() {
  if (!modelMatchResult) {
    return;
  }
  const completed = modelMatchResult.results.filter((game) => game.result !== "running");
  const newWins = completed.filter((game) => game.winner === modelMatchResult.new).length;
  const oldWins = completed.filter((game) => game.winner === modelMatchResult.old).length;
  const draws = completed.filter((game) => game.result === "draw").length;
  modelMatchResult.new_wins = newWins;
  modelMatchResult.old_wins = oldWins;
  modelMatchResult.draws = draws;
  modelMatchResult.new_score_rate = completed.length
    ? (newWins + draws * 0.5) / completed.length
    : 0;
  modelMatchResult.average_plies = completed.length
    ? completed.reduce((total, game) => total + game.plies, 0) / completed.length
    : 0;
  renderMatchSummary(modelMatchResult);
}

function renderMatchGameList() {
  const games = modelMatchResult?.results || [];
  matchGameCount.textContent = `${games.length} 盤`;
  matchGameCount.textContent = `${games.length} 盤`;
  matchGameList.innerHTML = "";
  games.forEach((game, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "match-game-row";
    if (index === selectedMatchGameIndex) {
      button.classList.add("active");
    }
    button.dataset.index = String(index);
    button.innerHTML = `
      <strong>第 ${game.game} 盤：${resultText(game)}</strong>
      <span>${game.black} 先手 / ${game.white} 後手</span>
      <span>${game.plies} 手，${game.reason}</span>
    `;
    button.innerHTML = `
      <strong>第 ${game.game} 盤：${engineResultText(game)}</strong>
      <span>先手 ${game.black} / 後手 ${game.white}</span>
      <span>${game.plies} 手，${game.reason}</span>
    `;
    matchGameList.appendChild(button);
  });
}

async function renderMatchReplay() {
  const game = modelMatchResult?.results?.[selectedMatchGameIndex];
  if (!game) {
    matchBoard.innerHTML = "";
    matchBlackHands.innerHTML = "";
    matchWhiteHands.innerHTML = "";
    matchReplayTitle.textContent = "尚未選擇對局";
    matchReplayStatus.textContent = "0 / 0";
    matchPlyStatus.textContent = "0 / 0";
    matchLastMove.textContent = "尚未開始";
    matchMoveList.innerHTML = "";
    return;
  }
  matchReplayPly = Math.max(0, Math.min(matchReplayPly, game.moves.length));
  const state = await postJson("/api/self-play/state", {
    moves: game.moves.slice(0, matchReplayPly),
  });
  matchReplayTitle.textContent = `第 ${game.game} 盤：${engineResultText(game)}`;
  matchReplayStatus.textContent = `${matchReplayPly} / ${game.moves.length}`;
  matchBlackLabel.textContent = game.black;
  matchWhiteLabel.textContent = game.white;
  renderBoardInto(matchBoard, state);
  renderHandsInto(matchBlackHands, state.hands["+"] || {}, state);
  renderHandsInto(matchWhiteHands, state.hands["-"] || {}, state);
  matchPlyStatus.textContent = `${matchReplayPly} / ${game.moves.length}`;
  matchLastMove.textContent = state.lastMove ? formatMoveNotation(state.lastMove) : "初始局面";
  matchFirstBtn.disabled = matchReplayPly === 0;
  matchPrevBtn.disabled = matchReplayPly === 0;
  matchNextBtn.disabled = matchReplayPly >= game.moves.length;
  matchLastBtn.disabled = matchReplayPly >= game.moves.length;
  matchMoveList.innerHTML = "";
  state.moves.forEach((move) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "move-row";
    row.dataset.ply = String(move.ply);
    row.innerHTML = `<span class="move-jump">${formatMoveNotation(move)}</span>`;
    matchMoveList.appendChild(row);
  });
}

function setMatchRunButtons(disabled, text) {
  for (const button of [runModelMatchBtn, runEngineMatchBtn]) {
    if (!button) {
      continue;
    }
    button.disabled = disabled;
    button.textContent = text;
  }
}

async function runModelMatch() {
  if (modelMatchRunning) {
    return;
  }
  const matchPayload = buildModelMatchPayload();
  const engineA = matchPayload.engineA.name;
  const engineB = matchPayload.engineB.name;
  modelMatchRunning = true;
  setMatchRunButtons(true, "對戰中...");
  if (engineMatchMeta) {
    engineMatchMeta.textContent = "正在讓兩組引擎對奕，棋盤會逐手更新。";
  }
  runModelMatchBtn.disabled = true;
  runModelMatchBtn.textContent = "對戰中...";
  modelMatchMeta.textContent = "模型正在對弈，棋盤會同步顯示目前局面。";
  modelMatchResult = {
    games: matchPayload.games,
    new: engineA,
    old: engineB,
    new_wins: 0,
    old_wins: 0,
    draws: 0,
    new_score_rate: 0,
    average_plies: 0,
    results: [],
    settings: matchPayload,
  };
  selectedMatchGameIndex = -1;
  matchReplayPly = 0;
  refreshLiveMatchSummary();
  renderMatchGameList();
  await renderMatchReplay();
  try {
    for (let gameIndex = 1; gameIndex <= matchPayload.games; gameIndex += 1) {
      const black = gameIndex % 2 === 1 ? engineA : engineB;
      const white = gameIndex % 2 === 1 ? engineB : engineA;
      let game = {
        game: gameIndex,
        black,
        white,
        result: "running",
        winner: null,
        winner_side: null,
        plies: 0,
        reason: "playing",
        moves: [],
        new_score: 0,
        old_score: 0,
      };
      let scores = { [engineA]: 0, [engineB]: 0 };
      modelMatchResult.results.push(game);
      const resultIndex = modelMatchResult.results.length - 1;
      selectedMatchGameIndex = resultIndex;
      matchReplayPly = 0;
      refreshLiveMatchSummary();
      renderMatchGameList();
      await renderMatchReplay();

      while (game.result === "running") {
        const data = await postJson("/api/model-match/step", {
          ...matchPayload,
          game: gameIndex,
          moves: game.moves,
          scores,
        });
        game = data.game;
        scores = data.scores || scores;
        modelMatchResult.results[resultIndex] = game;
        selectedMatchGameIndex = resultIndex;
        matchReplayPly = game.moves.length;
        refreshLiveMatchSummary();
        renderMatchGameList();
        await renderMatchReplay();
        if (engineMatchMeta) {
          engineMatchMeta.textContent = `第 ${gameIndex} / ${matchPayload.games} 盤，第 ${game.plies} 手：${game.reason}`;
        }
        modelMatchMeta.textContent = `第 ${gameIndex} / ${matchPayload.games} 盤，第 ${game.plies} 手。`;
        await sleep(80);
      }
    }
    if (engineMatchMeta) {
      engineMatchMeta.textContent = `完成 ${modelMatchResult.results.length} 盤對戰。`;
    }
    modelMatchMeta.textContent = `完成 ${modelMatchResult.results.length} 盤。`;
  } catch (error) {
    if (error.message === "not found") {
      if (engineMatchMeta) {
        engineMatchMeta.textContent = "目前執行中的後端是舊版，沒有逐手對戰 API。請關掉黑窗後重新開 start_csa_browser.bat。";
      }
      modelMatchMeta.textContent = "後端尚未載入即時對戰功能，所以棋盤只會停在初始局面。";
      return;
    }
    if (engineMatchMeta) {
      engineMatchMeta.textContent = error.message;
    }
    modelMatchMeta.textContent = error.message;
  } finally {
    modelMatchRunning = false;
    setMatchRunButtons(false, "開始對戰");
    runModelMatchBtn.disabled = false;
    runModelMatchBtn.textContent = "開始對戰";
  }
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

modelMatchTab.addEventListener("click", async () => {
  setActiveMode("model-match");
  if (!modelMatchLoaded) {
    await loadModelMatchModels();
  }
});

gameSelect.addEventListener("change", async () => {
  currentGameId = gameSelect.value;
  await loadPosition(0);
});

loadMoreGamesBtn.addEventListener("click", async () => {
  await loadGames({ append: true });
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

runModelMatchBtn.addEventListener("click", async () => {
  await runModelMatch();
});

if (runEngineMatchBtn) {
  runEngineMatchBtn.addEventListener("click", async () => {
    await runModelMatch();
  });
}

matchGameList.addEventListener("click", async (event) => {
  const row = event.target.closest(".match-game-row");
  if (!row) {
    return;
  }
  selectedMatchGameIndex = Number(row.dataset.index);
  matchReplayPly = 0;
  renderMatchGameList();
  await renderMatchReplay();
});

matchMoveList.addEventListener("click", async (event) => {
  const row = event.target.closest(".move-row");
  if (!row) {
    return;
  }
  matchReplayPly = Number(row.dataset.ply);
  await renderMatchReplay();
});

matchFirstBtn.addEventListener("click", async () => {
  matchReplayPly = 0;
  await renderMatchReplay();
});

matchPrevBtn.addEventListener("click", async () => {
  matchReplayPly -= 1;
  await renderMatchReplay();
});

matchNextBtn.addEventListener("click", async () => {
  matchReplayPly += 1;
  await renderMatchReplay();
});

matchLastBtn.addEventListener("click", async () => {
  const game = modelMatchResult?.results?.[selectedMatchGameIndex];
  matchReplayPly = game ? game.moves.length : 0;
  await renderMatchReplay();
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

  if (activeMode === "model-match") {
    const game = modelMatchResult?.results?.[selectedMatchGameIndex];
    if (!game) {
      return;
    }
    if (event.key === "ArrowLeft" && matchReplayPly > 0) {
      matchReplayPly -= 1;
      await renderMatchReplay();
    }
    if (event.key === "ArrowRight" && matchReplayPly < game.moves.length) {
      matchReplayPly += 1;
      await renderMatchReplay();
    }
    if (event.key === "Home") {
      matchReplayPly = 0;
      await renderMatchReplay();
    }
    if (event.key === "End") {
      matchReplayPly = game.moves.length;
      await renderMatchReplay();
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
