import assert from 'node:assert/strict';
import test from 'node:test';

import {SOUNDS, createSound, soundsFor} from '../../static/sound.mjs';

// A stand-in AudioContext that records the oscillators it is asked to play.
function fakeContext() {
  const param = () => ({value: 0, setValueAtTime() {}, linearRampToValueAtTime() {},
                        exponentialRampToValueAtTime() {}});
  const node = extra => ({connect: target => target, ...extra});
  const context = {
    currentTime: 0, sampleRate: 8000, state: 'suspended', destination: node(), tones: [], resumed: 0,
    resume() { this.resumed++; this.state = 'running'; },
    createDynamicsCompressor: () => node({threshold: param(), ratio: param()}),
    createGain: () => node({gain: param()}),
    createOscillator: () => {
      const tone = node({frequency: param(), start() {}, stop() {}});
      context.tones.push(tone);
      return tone;
    },
    createBuffer: (channels, length) => ({getChannelData: () => new Float32Array(length)}),
    createBufferSource: () => node({start() {}}),
    createBiquadFilter: () => node({frequency: param(), Q: param()}),
  };
  return context;
}

function fakeStorage(initial = {}) {
  const values = {...initial};
  return {values, getItem: key => values[key] ?? null, setItem: (key, value) => { values[key] = value; }};
}

function setup(storage = fakeStorage()) {
  const contexts = [];
  const sound = createSound({storage, random: () => 0.5,
                             makeContext: () => { const c = fakeContext(); contexts.push(c); return c; }});
  return {sound, contexts, storage};
}

test('a plain move, a capture and a new game each have their own sound', () => {
  assert.deepEqual(soundsFor('move', {moves: ['e2-e4'], status: null}), ['move']);
  assert.deepEqual(soundsFor('computer-move', {moves: ['e2-e4', 'd7-d5', 'e4xd5'], status: null}), ['capture']);
  assert.deepEqual(soundsFor('new', {moves: []}), ['start']);
  assert.deepEqual(soundsFor('undo', {moves: []}), ['undo']);
});

test('check, the end of the game and promotion add a chime', () => {
  assert.deepEqual(soundsFor('move', {moves: ['a1-a8+'], status: 'check'}), ['move', 'check']);
  assert.deepEqual(soundsFor('move', {moves: ['d8xh4#'], status: 'checkmate'}), ['capture', 'end']);
  assert.deepEqual(soundsFor('move', {moves: ['b6-c7'], status: 'stalemate'}), ['move', 'end']);
  assert.deepEqual(soundsFor('move', {moves: ['b7xa8=Q'], status: null}), ['capture', 'promote']);
});

test('redo sounds like the move it replays', () => {
  assert.deepEqual(soundsFor('redo', {moves: ['e2-e4'], status: null}), ['move']);
  assert.deepEqual(soundsFor('redo', {moves: ['e2-e4', 'd7-d5', 'e4xd5'], status: null}), ['capture']);
  assert.deepEqual(soundsFor('redo', {moves: ['d8xh4#'], status: 'checkmate'}), ['capture', 'end']);
  assert.deepEqual(soundsFor('redo', {moves: [], status: null}), []);
});

test('actions that change nothing on the board are silent', () => {
  for (const action of ['legal', 'save', 'load', undefined]) assert.deepEqual(soundsFor(action, {moves: ['e2-e4']}), []);
  assert.deepEqual(soundsFor('move', {}), []);
});

test('every sound plays tones and wakes a suspended context', () => {
  for (const name of SOUNDS) {
    const {sound, contexts} = setup();
    assert.equal(sound.play([name]), true, name);
    assert.ok(contexts[0].tones.length > 0, name);
    assert.equal(contexts[0].resumed, 1);
  }
});

test('a capture strikes lower than a plain move', () => {
  const lowest = name => {
    const {sound, contexts} = setup();
    sound.play([name]);
    return Math.min(...contexts[0].tones.map(tone => tone.frequency.value));
  };
  assert.ok(lowest('capture') < lowest('move'));
});

test('one audio context is reused across sounds', () => {
  const {sound, contexts} = setup();
  sound.play(['move']); sound.play(['capture', 'check']);
  assert.equal(contexts.length, 1);
});

test('muted plays nothing and creates no audio context', () => {
  const {sound, contexts} = setup();
  assert.equal(sound.muted, false);
  assert.equal(sound.toggle(), true);
  assert.equal(sound.play(['move']), false);
  assert.equal(contexts.length, 0);
  assert.equal(sound.toggle(), false);
  assert.equal(sound.play(['move']), true);
});

test('the mute setting is remembered between visits', () => {
  const storage = fakeStorage();
  setup(storage).sound.setMuted(true);
  assert.equal(setup(storage).sound.muted, true);
  setup(storage).sound.setMuted(false);
  assert.equal(setup(storage).sound.muted, false);
});

test('blocked storage or missing audio never breaks the game', () => {
  const broken = {getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }};
  const sound = createSound({storage: broken, makeContext: () => { throw new Error('no audio'); }});
  assert.equal(sound.muted, false);
  assert.equal(sound.setMuted(true), true);
  assert.equal(sound.muted, true);
  sound.setMuted(false);
  assert.equal(sound.play(['move']), false);
  assert.equal(createSound().play([]), false);
});
