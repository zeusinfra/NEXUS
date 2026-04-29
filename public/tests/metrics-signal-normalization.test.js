import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

function makePulseOrbState() {
  return {
    orbEnergy: 0.18,
    focusBias: 0,
    orbDriftX: 0,
    orbDriftY: 0,
  };
}

function pulseOrb(state, power = 0.2, tiltX = 0, tiltY = 0) {
  state.orbEnergy = Math.min(1.5, state.orbEnergy + power);
  state.focusBias = Math.min(0.8, state.focusBias + power * 0.45);
  state.orbDriftX += tiltX;
  state.orbDriftY += tiltY;
}

function normalizeCpuLoad(value) {
  if (Array.isArray(value)) {
    if (!value.length) return 0;
    const numeric = value.filter(item => Number.isFinite(Number(item))).map(Number);
    if (!numeric.length) return 0;
    return numeric.reduce((sum, item) => sum + item, 0) / numeric.length;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function reactToMetrics(state, payload = {}) {
  const cpu = normalizeCpuLoad(payload.cpu);
  const ram = Number.isFinite(Number(payload.ram)) ? Number(payload.ram) : 0;
  const load = Math.max(cpu, ram) / 100;
  pulseOrb(state, 0.08 + load * 0.18, load * 0.03, -load * 0.015);
}

describe('Metrics signal normalization', () => {
  test('cpu array should not contaminate orb state with NaN', () => {
    const state = makePulseOrbState();

    reactToMetrics(state, { cpu: [12.5, 30, 57.5, 20], ram: 48 });

    assert.ok(Number.isFinite(state.orbEnergy), `orbEnergy should be finite, got ${state.orbEnergy}`);
    assert.ok(Number.isFinite(state.focusBias), `focusBias should be finite, got ${state.focusBias}`);
    assert.ok(Number.isFinite(state.orbDriftX), `orbDriftX should be finite, got ${state.orbDriftX}`);
    assert.ok(Number.isFinite(state.orbDriftY), `orbDriftY should be finite, got ${state.orbDriftY}`);
  });
});
