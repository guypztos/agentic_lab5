import {createSound, soundsFor} from '/sound.mjs';

// Filled glyphs for both sides; CSS colours them white or black.
const glyphs = {K:'♚\uFE0E', Q:'♛\uFE0E', R:'♜\uFE0E', B:'♝\uFE0E', N:'♞\uFE0E', P:'♟\uFE0E'};
const names = {K:'king', Q:'queen', R:'rook', B:'bishop', N:'knight', P:'pawn'};
let state, selected = null, targets = [], promotions = [], busy = false;
const message = document.querySelector('#message');
const sound = createSound({storage: globalThis.localStorage, makeContext: () => new AudioContext()});

// Errors are shown in red; a notice such as "Game saved" in the muted text colour.
function say(text, notice = false) {
  message.textContent = text;
  message.classList.toggle('notice', notice);
}

async function request(action) {
  const response = await fetch('/api/action', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(action)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  sound.play(soundsFor(action.action, result));
  return result;
}

function render() {
  const board = document.querySelector('#board');
  board.replaceChildren();
  for (let rank = 8; rank >= 1; rank--) {
    for (let file = 0; file < 8; file++) {
      const square = 'abcdefgh'[file] + rank, piece = state.board[square];
      const button = document.createElement('button');
      button.className = 'square ' + ((file + rank) % 2 ? 'dark' : 'light');
      button.classList.toggle('selected', selected === square);
      button.classList.toggle('target', targets.includes(square));
      button.classList.toggle('occupied', Boolean(piece));
      button.classList.toggle('checked', piece === state.turn + 'K'
        && (state.status === 'check' || state.status === 'checkmate'));
      button.dataset.square = square;
      button.setAttribute('aria-label', square + (piece ? ` ${piece[0] === 'w' ? 'White' : 'Black'} ${names[piece[1]]}` : ' empty'));
      button.setAttribute('aria-pressed', String(selected === square));
      if (piece) button.append(pieceGlyph(piece));
      if (file === 0) button.append(coordinate('rank', rank));
      if (rank === 1) button.append(coordinate('file', square[0]));
      button.onclick = () => clickSquare(square);
      board.append(button);
    }
  }
  const computer = state.opponent === 'computer';
  const side = computer ? (state.turn === 'w' ? 'Your move' : 'The computer is thinking')
                        : `${state.turn === 'w' ? 'White' : 'Black'} to move`;
  const winner = computer ? (state.winner === 'White' ? 'You win' : 'The computer wins')
                          : `${state.winner} wins`;
  document.querySelector('#turn').textContent =
    state.status === 'checkmate' ? `Checkmate. ${winner}`
    : state.status === 'stalemate' ? 'Stalemate. Draw'
    : state.status === 'check' ? `${side}. Check` : side;
  const pairs = [];
  for (let i = 0; i < state.moves.length; i += 2) pairs.push(state.moves.slice(i, i + 2));
  document.querySelector('#moves').replaceChildren(...pairs.map(pair => {
    const item = document.createElement('li');
    for (const move of pair) {
      const cell = document.createElement('span'); cell.textContent = move; item.append(cell);
    }
    return item;
  }));
  document.querySelector('#undo').disabled = !state.can_undo;
  document.querySelector('#redo').disabled = !state.can_redo;
  document.querySelector('#captured-panel').hidden = !Object.hasOwn(state, 'captured');
  const captured = state.captured || [];
  document.querySelector('#captured').replaceChildren(...captured.map(pieceGlyph));
  if (!captured.length) document.querySelector('#captured').textContent = 'None';
}

function pieceGlyph(piece) {
  const glyph = document.createElement('span');
  glyph.className = 'piece ' + (piece[0] === 'w' ? 'white' : 'black');
  glyph.textContent = glyphs[piece[1]];
  return glyph;
}

function coordinate(kind, text) {
  const label = document.createElement('small');
  label.className = kind; label.textContent = text;
  return label;
}

// Against the computer, it answers after a short pause so each move is seen and heard.
async function computerReply() {
  const over = state.status === 'checkmate' || state.status === 'stalemate';
  if (state.opponent !== 'computer' || state.turn !== 'b' || over) return;
  await new Promise(resolve => setTimeout(resolve, 500));
  state = await request({action: 'computer-move'});
  render();
}

function choosePromotion(side) {
  const dialog = document.querySelector('#promotion');
  document.querySelector('#promotion-choices').replaceChildren(...['Q', 'R', 'B', 'N'].map(kind => {
    const button = document.createElement('button');
    button.value = kind;
    button.setAttribute('aria-label', names[kind]);
    button.append(pieceGlyph(side + kind));
    return button;
  }));
  dialog.returnValue = '';
  dialog.showModal();
  return new Promise(resolve => dialog.addEventListener(
    'close', () => resolve(dialog.returnValue || null), {once: true}));
}

async function clickSquare(square) {
  if (busy) return;
  busy = true;
  say('');
  try {
    if (selected && targets.includes(square)) {
      const promotion = promotions.includes(square) ? await choosePromotion(state.turn) : undefined;
      if (promotion !== null) state = await request({action:'move', source:selected, target:square, promotion});
      selected = null; targets = []; promotions = [];
    } else if (selected === square) {
      selected = null; targets = [];
    } else {
      ({targets, promotions = []} = await request({action:'legal', source:square}));
      selected = state.board[square]?.[0] === state.turn ? square : null;
    }
    render();
    await computerReply();
  } catch (error) { say(error.message); }
  finally { busy = false; }
}

document.querySelector('#controls').onclick = async event => {
  const button = event.target.closest('button');
  if (!button?.dataset.action || busy) return;
  busy = true;
  try {
    state = await request({action: button.dataset.action, opponent: button.dataset.opponent});
    selected = null; targets = [];
    say({save: 'Game saved', load: 'Game loaded'}[button.dataset.action] ?? '', true);
    render();
    await computerReply();  // A loaded game may be waiting on the computer.
  } catch (error) { say(error.message); }
  finally { busy = false; }
};

const muteButton = document.querySelector('#mute');
function renderMute() {
  muteButton.textContent = sound.muted ? 'Sound: off' : 'Sound: on';
  muteButton.setAttribute('aria-pressed', String(sound.muted));
}
muteButton.onclick = () => { sound.toggle(); renderMute(); };
renderMute();

try {
  const response = await fetch('/api/state');
  if (!response.ok) throw new Error('Could not load the game');
  state = await response.json(); render();
} catch (error) { say(error.message); }
