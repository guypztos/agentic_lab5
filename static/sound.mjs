// Game sounds, synthesized with the Web Audio API, and the mute setting.
// Kept free of the page so it can be tested in Node with a stand-in AudioContext.

const MUTE_KEY = 'chess-sound-muted';

// Which sounds an action's result should make, base sound first. A move is a piece landing
// (a capture is a heavier strike); check, the end of the game and promotion add a chime.
export function soundsFor(action, result) {
  if (action === 'new') return ['start'];
  if (action === 'undo') return ['undo'];
  if (action !== 'move' && action !== 'computer-move') return [];
  const label = result?.moves?.at(-1);
  if (!label) return [];
  const sounds = [label.includes('x') ? 'capture' : 'move'];
  if (result.status === 'checkmate' || result.status === 'stalemate') sounds.push('end');
  else if (result.status === 'check') sounds.push('check');
  else if (label.includes('=')) sounds.push('promote');
  return sounds;
}

// A felted piece landing on a solid board: decaying resonances (frequency Hz, level,
// decay s) plus a short contact tick.
const RESONANCES = [[90, 0.5, 0.13], [180, 0.6, 0.1], [390, 0.45, 0.07], [850, 0.2, 0.046], [1425, 0.08, 0.03]];

function strike(audio, out, now, random, {pitch = 1, length = 1, gain = 1} = {}) {
  const level = audio.createGain();
  level.gain.value = gain;
  level.connect(out);
  pitch *= 1 + (random() - 0.5) * 0.06;
  for (const [frequency, peak, decay] of RESONANCES) {
    const tone = audio.createOscillator(), envelope = audio.createGain();
    tone.frequency.value = frequency * pitch;
    envelope.gain.setValueAtTime(0, now);
    envelope.gain.linearRampToValueAtTime(peak, now + 0.0015);
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + decay * length);
    tone.connect(envelope).connect(level); tone.start(now); tone.stop(now + decay * length + 0.02);
  }
  const noise = audio.createBuffer(1, Math.ceil(audio.sampleRate * 0.007), audio.sampleRate);
  const samples = noise.getChannelData(0);
  for (let i = 0; i < samples.length; i++) samples[i] = (random() * 2 - 1) * (1 - i / samples.length) ** 3;
  const tick = audio.createBufferSource(), band = audio.createBiquadFilter(), tickLevel = audio.createGain();
  tick.buffer = noise; band.type = 'bandpass'; band.frequency.value = 1000 * pitch; band.Q.value = 0.9;
  tickLevel.gain.value = 0.2;
  tick.connect(band).connect(tickLevel).connect(level); tick.start(now);
}

// Soft bell-like notes: [frequency Hz, start offset s, length s].
function chime(audio, out, now, notes, gain = 0.18) {
  for (const [frequency, offset, length] of notes) {
    const tone = audio.createOscillator(), envelope = audio.createGain(), at = now + offset;
    tone.type = 'triangle';
    tone.frequency.value = frequency;
    envelope.gain.setValueAtTime(0, at);
    envelope.gain.linearRampToValueAtTime(gain, at + 0.01);
    envelope.gain.exponentialRampToValueAtTime(0.0001, at + length);
    tone.connect(envelope).connect(out); tone.start(at); tone.stop(at + length + 0.02);
  }
}

// The chime follows the piece landing, so it starts a little later.
const VOICES = {
  move: (audio, out, now, random) => strike(audio, out, now, random),
  capture: (audio, out, now, random) => strike(audio, out, now, random, {pitch: 0.78, length: 1.4, gain: 1.45}),
  undo: (audio, out, now, random) => strike(audio, out, now, random, {pitch: 1.3, length: 0.7, gain: 0.6}),
  start: (audio, out, now) => chime(audio, out, now, [[523, 0, 0.35], [659, 0.1, 0.35], [784, 0.2, 0.6]]),
  check: (audio, out, now) => chime(audio, out, now + 0.08, [[988, 0, 0.12], [988, 0.14, 0.2]], 0.22),
  promote: (audio, out, now) => chime(audio, out, now + 0.08, [[659, 0, 0.2], [880, 0.08, 0.2], [1047, 0.16, 0.45]]),
  end: (audio, out, now) => chime(audio, out, now + 0.1, [[784, 0, 0.3], [659, 0.18, 0.3], [523, 0.36, 0.3], [392, 0.54, 0.9]]),
};
export const SOUNDS = Object.keys(VOICES);

// storage: localStorage or a stand-in; makeContext: () => new AudioContext().
export function createSound({storage, makeContext, random = Math.random} = {}) {
  let muted = false, audio, master;
  try { muted = storage?.getItem(MUTE_KEY) === 'true'; } catch { /* Storage may be blocked. */ }

  function context() {
    if (!audio) {
      audio = makeContext();
      master = audio.createDynamicsCompressor();
      master.threshold.value = -10; master.ratio.value = 4;
      master.connect(audio.destination);
    }
    if (audio.state === 'suspended') audio.resume?.();
    return audio;
  }

  return {
    get muted() { return muted; },
    setMuted(value) {
      muted = Boolean(value);
      try { storage?.setItem(MUTE_KEY, String(muted)); } catch { /* Not remembered, still applied. */ }
      return muted;
    },
    toggle() { return this.setMuted(!muted); },
    // Returns whether anything was played.
    play(sounds) {
      if (muted || !sounds.length) return false;
      try {
        const now = context().currentTime + 0.01;
        for (const name of sounds) VOICES[name](audio, master, now, random);
        return true;
      } catch { return false; /* Sound is decoration; the game works without audio. */ }
    },
  };
}
