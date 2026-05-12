// 取得頁面上的主要元件，後面所有渲染與按鈕操作都會使用這些 DOM。
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

// 瀏覽器端目前狀態：目前棋局、目前手數、最大手數與最近一次 API 回傳資料。
let currentGameId = "";
let currentPly = 0;
let maxPly = 0;
let latestState = null;

async function fetchJson(url) {
  // 包裝 fetch：統一解析 JSON，若後端回錯誤就丟出例外給畫面顯示。
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function sideLabel(color) {
  // 將後端使用的 + / - 轉成畫面上的先手 / 後手。
  return color === "+" ? "先手" : "後手";
}

function pieceClass(piece) {
  // 依棋子所屬方與是否升變決定 CSS class。
  const classes = ["piece", piece.color === "+" ? "black" : "white"];
  if (piece.promoted) {
    classes.push("promoted");
  }
  return classes.join(" ");
}

function markerStorageKey() {
  // 每一盤棋使用不同 localStorage key，避免標記互相混在一起。
  return `csa-browser-markers:${currentGameId}`;
}

function getMarkedPlies() {
  // 讀取使用者在這盤棋標記過的手數；資料壞掉時回傳空集合。
  try {
    const raw = localStorage.getItem(markerStorageKey());
    const values = raw ? JSON.parse(raw) : [];
    return new Set(values.map(Number).filter((value) => Number.isInteger(value) && value >= 0));
  } catch {
    return new Set();
  }
}

function saveMarkedPlies(markedPlies) {
  // 將標記手數存回 localStorage，重新整理網頁後仍會保留。
  localStorage.setItem(markerStorageKey(), JSON.stringify([...markedPlies].sort((a, b) => a - b)));
}

function toggleMarkedPly(ply) {
  // 切換某一手是否被標記，並重新渲染手順列表。
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
  // 將搜尋欄位轉成 query string；空白欄位不送給後端。
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
  // 沒有棋局或載入失敗時清空畫面，避免留下上一盤棋的資料。
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

function renderBoard(state) {
  // 根據後端回傳的 9x9 board 資料畫出棋盤，並標示上一手來源與落點。
  boardEl.innerHTML = "";
  const last = state.lastMove;
  for (const row of state.board) {
    for (const cell of row) {
      const square = document.createElement("div");
      square.className = "square";
      square.dataset.square = cell.square;
      if (last?.from === cell.square) {
        square.classList.add("last-from");
      }
      if (last?.to === cell.square) {
        square.classList.add("last-to");
      }

      if (cell.piece) {
        const piece = document.createElement("div");
        piece.className = pieceClass(cell.piece);
        piece.textContent = cell.piece.label;
        piece.title = `${cell.square} ${sideLabel(cell.piece.color)} ${cell.piece.label}`;
        square.appendChild(piece);
      }
      boardEl.appendChild(square);
    }
  }
}

function renderHands(container, hands, state) {
  // 渲染先手/後手持有的手駒；沒有手駒時顯示空狀態。
  container.innerHTML = "";
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
    const chip = document.createElement("span");
    chip.className = "hand-piece";
    chip.textContent = `${state.pieceNames[item.piece]}×${item.count}`;
    container.appendChild(chip);
  }
}

function renderMeta(state) {
  // 更新棋手、賽事、戰型、日期與結果等棋局資訊。
  const game = state.game;
  blackName.textContent = game.black || "先手";
  whiteName.textContent = game.white || "後手";
  gameMeta.textContent = [game.event, game.opening, game.startTime, game.result ? `結果 ${game.result}` : ""]
    .filter(Boolean)
    .join(" · ") || game.name;
}

function renderStatus(state) {
  // 更新目前手數、上一手資訊與控制按鈕可用狀態。
  currentPly = state.ply;
  maxPly = state.maxPly;
  plyStatus.textContent = `${currentPly} / ${maxPly}`;
  lastMove.textContent = state.lastMove
    ? `${state.lastMove.ply}. ${sideLabel(state.lastMove.color)} ${state.lastMove.text}`
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
  // 建立手順列表的一列，包含跳到該手與標記按鈕。
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
  jump.textContent = ply === 0 ? "0. 開始局面" : `${ply}. ${sideLabel(move.color)} ${move.text}`;

  const marker = document.createElement("button");
  marker.type = "button";
  marker.className = "move-marker";
  marker.dataset.ply = String(ply);
  marker.textContent = markedPlies.has(ply) ? "★" : "☆";
  marker.title = markedPlies.has(ply) ? "取消標記" : "標記此手";
  marker.setAttribute("aria-label", marker.title);
  marker.setAttribute("aria-pressed", markedPlies.has(ply) ? "true" : "false");

  row.appendChild(jump);
  row.appendChild(marker);
  return row;
}

function renderMoveList(state) {
  // 重新產生完整手順列表，並自動捲到目前所在手數。
  moveList.innerHTML = "";
  const markedPlies = getMarkedPlies();
  moveListCount.textContent = `${state.maxPly} 手 · 標記 ${markedPlies.size}`;
  moveList.appendChild(createMoveListItem({ ply: 0, color: "+", text: "開始局面" }, markedPlies));
  for (const move of state.moves) {
    moveList.appendChild(createMoveListItem(move, markedPlies));
  }
  const activeItem = moveList.querySelector(".move-row.active");
  activeItem?.scrollIntoView({ block: "nearest", inline: "nearest" });
}

function renderState(state) {
  // 統一渲染一個局面需要更新的所有區塊。
  latestState = state;
  renderMeta(state);
  renderBoard(state);
  renderHands(blackHands, state.hands["+"] || {}, state);
  renderHands(whiteHands, state.hands["-"] || {}, state);
  renderStatus(state);
  renderMoveList(state);
}

async function loadPosition(ply) {
  // 向後端請求指定手數的局面，並限制手數不能超出 0~maxPly。
  if (!currentGameId) {
    return;
  }
  const boundedPly = Math.max(0, Math.min(maxPly || ply, ply));
  const state = await fetchJson(`/api/games/${encodeURIComponent(currentGameId)}?ply=${boundedPly}`);
  renderState(state);
}

async function loadGames() {
  // 依目前搜尋條件讀取棋局清單，並自動載入第一盤可播放棋局。
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
    option.textContent = game.error ? `${game.name} - 讀取失敗` : `${game.name} (${game.moves}手)`;
    option.disabled = Boolean(game.error);
    gameSelect.appendChild(option);
  }

  const firstPlayable = data.games.find((game) => !game.error);
  if (!firstPlayable) {
    clearBoardState("找不到可讀取的棋局");
    return;
  }

  currentGameId = firstPlayable.id;
  gameSelect.value = currentGameId;
  await loadPosition(0);
}

gameSelect.addEventListener("change", async () => {
  // 使用者切換棋局時，從初始局面開始播放。
  currentGameId = gameSelect.value;
  await loadPosition(0);
});

searchBtn.addEventListener("click", async () => {
  // 搜尋按鈕：用目前輸入條件重新載入棋局清單。
  await loadGames();
});

clearSearchBtn.addEventListener("click", async () => {
  // 清除按鈕：清空所有搜尋欄位並回到預設日期排序。
  eventFilter.value = "";
  dateFromFilter.value = "";
  dateToFilter.value = "";
  playerFilter.value = "";
  openingFilter.value = "";
  await loadGames();
});

for (const input of [eventFilter, dateFromFilter, dateToFilter, playerFilter, openingFilter]) {
  input.addEventListener("keydown", async (event) => {
    // 搜尋欄位支援 Enter 直接送出，演示時不用一定要點按鈕。
    if (event.key === "Enter") {
      await loadGames();
    }
  });
}

firstBtn.addEventListener("click", async () => {
  // 回到初始局面。
  await loadPosition(0);
});

prevBtn.addEventListener("click", async () => {
  // 上一手。
  await loadPosition(currentPly - 1);
});

nextBtn.addEventListener("click", async () => {
  // 下一手。
  await loadPosition(currentPly + 1);
});

lastBtn.addEventListener("click", async () => {
  // 跳到最後一手。
  await loadPosition(maxPly);
});

moveList.addEventListener("click", async (event) => {
  // 手順列表事件代理：可點手順跳轉，也可點星號加入/取消標記。
  const marker = event.target.closest(".move-marker");
  if (marker) {
    toggleMarkedPly(Number(marker.dataset.ply));
    return;
  }

  const jump = event.target.closest(".move-jump");
  if (!jump) {
    return;
  }
  await loadPosition(Number(jump.dataset.ply));
});

document.addEventListener("keydown", async (event) => {
  // 鍵盤快捷操作：左右鍵上一手/下一手，Home/End 到初始或最後。
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
});

loadGames().catch((error) => {
  // 初次載入失敗時，在畫面上顯示錯誤訊息。
  clearBoardState(error.message);
});
