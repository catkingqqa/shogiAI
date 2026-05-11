const gameSelect = document.querySelector("#gameSelect");
const boardEl = document.querySelector("#board");
const prevBtn = document.querySelector("#prevBtn");
const nextBtn = document.querySelector("#nextBtn");
const plyStatus = document.querySelector("#plyStatus");
const lastMove = document.querySelector("#lastMove");
const gameMeta = document.querySelector("#gameMeta");
const blackName = document.querySelector("#blackName");
const whiteName = document.querySelector("#whiteName");
const blackHands = document.querySelector("#blackHands");
const whiteHands = document.querySelector("#whiteHands");

let currentGameId = "";
let currentPly = 0;
let maxPly = 0;

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function pieceClass(piece) {
  const classes = ["piece", piece.color === "+" ? "black" : "white"];
  if (piece.promoted) {
    classes.push("promoted");
  }
  return classes.join(" ");
}

function renderBoard(state) {
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
        piece.title = `${cell.square} ${cell.piece.color === "+" ? "先手" : "後手"} ${cell.piece.label}`;
        square.appendChild(piece);
      }
      boardEl.appendChild(square);
    }
  }
}

function renderHands(container, hands, state) {
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
  const game = state.game;
  blackName.textContent = game.black || "先手";
  whiteName.textContent = game.white || "後手";
  gameMeta.textContent = [game.event, game.startTime, game.result ? `結果 ${game.result}` : ""]
    .filter(Boolean)
    .join(" · ") || game.name;
}

function renderStatus(state) {
  currentPly = state.ply;
  maxPly = state.maxPly;
  plyStatus.textContent = `${currentPly} / ${maxPly}`;
  lastMove.textContent = state.lastMove
    ? `${state.lastMove.ply}. ${state.lastMove.color === "+" ? "先手" : "後手"} ${state.lastMove.text}`
    : "開始局面";
  prevBtn.disabled = currentPly <= 0;
  nextBtn.disabled = currentPly >= maxPly;
}

function renderState(state) {
  renderMeta(state);
  renderBoard(state);
  renderHands(blackHands, state.hands["+"] || {}, state);
  renderHands(whiteHands, state.hands["-"] || {}, state);
  renderStatus(state);
}

async function loadPosition(ply) {
  if (!currentGameId) {
    return;
  }
  const state = await fetchJson(`/api/games/${encodeURIComponent(currentGameId)}?ply=${ply}`);
  renderState(state);
}

async function loadGames() {
  const data = await fetchJson("/api/games");
  gameSelect.innerHTML = "";

  if (data.games.length === 0) {
    gameMeta.textContent = "data 資料夾裡沒有 .csa 棋譜";
    prevBtn.disabled = true;
    nextBtn.disabled = true;
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
    gameMeta.textContent = "找不到可讀取的 CSA 棋譜";
    return;
  }

  currentGameId = firstPlayable.id;
  gameSelect.value = currentGameId;
  await loadPosition(0);
}

gameSelect.addEventListener("change", async () => {
  currentGameId = gameSelect.value;
  await loadPosition(0);
});

prevBtn.addEventListener("click", async () => {
  await loadPosition(Math.max(0, currentPly - 1));
});

nextBtn.addEventListener("click", async () => {
  await loadPosition(Math.min(maxPly, currentPly + 1));
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "ArrowLeft" && currentPly > 0) {
    await loadPosition(currentPly - 1);
  }
  if (event.key === "ArrowRight" && currentPly < maxPly) {
    await loadPosition(currentPly + 1);
  }
});

loadGames().catch((error) => {
  gameMeta.textContent = error.message;
  prevBtn.disabled = true;
  nextBtn.disabled = true;
});
