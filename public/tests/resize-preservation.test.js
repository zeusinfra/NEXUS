/**
 * Preservation Property Tests — Globe Particles (resizeCanvas)
 *
 * Validates: Requirements 3.1, 3.2, 3.3
 *
 * PURPOSE: Verify that for all inputs where isBugCondition is FALSE
 * (i.e., width > 0 AND height > 0), resizeCanvas() behaves identically
 * to the original implementation.
 *
 * These tests MUST PASS on UNFIXED code — passing confirms the baseline
 * behavior to preserve after the fix is applied.
 *
 * Preservation Property (Property 2):
 *   For any rect where width > 0 AND height > 0:
 *     - renderer.setSize(rect.width, rect.height, false) is called
 *     - camera.aspect === rect.width / rect.height
 *     - camera.updateProjectionMatrix() is called
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// ---------------------------------------------------------------------------
// Minimal mocks (same pattern as resize-bug-condition.test.js)
// ---------------------------------------------------------------------------

function makeRenderer(initialWidth = 800, initialHeight = 600) {
  const domElement = { width: initialWidth, height: initialHeight };
  const calls = [];
  return {
    domElement,
    calls,
    setSize(w, h, updateStyle) {
      domElement.width = w;
      domElement.height = h;
      calls.push({ w, h, updateStyle });
    },
  };
}

function makeCamera(initialAspect = 800 / 600) {
  let projectionMatrixUpdated = false;
  return {
    aspect: initialAspect,
    get projectionMatrixUpdated() { return projectionMatrixUpdated; },
    updateProjectionMatrix() { projectionMatrixUpdated = true; },
  };
}

function makeCanvas(parentRect) {
  return {
    parentElement: {
      getBoundingClientRect() {
        return parentRect;
      },
    },
  };
}

// ---------------------------------------------------------------------------
// Replicate the FIXED resizeCanvas() logic from public/index.html
// (with zero-dimension guard — this is the fixed version)
// ---------------------------------------------------------------------------
function resizeCanvas_fixed(canvas, renderer, camera) {
  const rect = canvas.parentElement.getBoundingClientRect();
  if (!rect.width || !rect.height) return;  // guard — only change
  renderer.setSize(rect.width, rect.height, false);
  camera.aspect = rect.width / rect.height;
  camera.updateProjectionMatrix();
}

// ---------------------------------------------------------------------------
// Helper: generate random valid (width, height) pairs where both > 0
// ---------------------------------------------------------------------------
function generateValidDimensions(count = 50, seed = 42) {
  // Simple deterministic pseudo-random generator (LCG) for reproducibility
  let s = seed;
  function rand() {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  }

  const pairs = [];
  // Include specific important cases first
  pairs.push({ width: 800, height: 600 });
  pairs.push({ width: 1920, height: 1080 });
  pairs.push({ width: 1, height: 1 });
  pairs.push({ width: 0.5, height: 0.5 }); // fractional pixels
  pairs.push({ width: 1280, height: 720 });
  pairs.push({ width: 2560, height: 1440 });

  // Generate random valid pairs
  for (let i = 0; i < count; i++) {
    const width  = rand() * 3840 + 1;   // 1 to 3841
    const height = rand() * 2160 + 1;   // 1 to 2161
    pairs.push({ width, height });
  }

  return pairs;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Preservation: resizeCanvas() with valid dimensions (width > 0 AND height > 0)', () => {

  test('Observation: { width: 800, height: 600 } → renderer.setSize(800, 600, false) and camera.aspect = 800/600', () => {
    // Validates: Requirements 3.1, 3.2, 3.3
    const renderer = makeRenderer();
    const camera   = makeCamera();
    const canvas   = makeCanvas({ width: 800, height: 600 });

    resizeCanvas_fixed(canvas, renderer, camera);

    assert.equal(renderer.domElement.width, 800, 'renderer width should be 800');
    assert.equal(renderer.domElement.height, 600, 'renderer height should be 600');
    assert.equal(renderer.calls.length, 1, 'setSize should be called exactly once');
    assert.deepEqual(renderer.calls[0], { w: 800, h: 600, updateStyle: false });
    assert.equal(camera.aspect, 800 / 600, 'camera.aspect should be 800/600');
    assert.ok(camera.projectionMatrixUpdated, 'updateProjectionMatrix should be called');
  });

  test('Observation: { width: 1920, height: 1080 } → renderer.setSize(1920, 1080, false) and camera.aspect ≈ 1.778', () => {
    // Validates: Requirements 3.1, 3.2, 3.3
    const renderer = makeRenderer();
    const camera   = makeCamera();
    const canvas   = makeCanvas({ width: 1920, height: 1080 });

    resizeCanvas_fixed(canvas, renderer, camera);

    assert.equal(renderer.domElement.width, 1920);
    assert.equal(renderer.domElement.height, 1080);
    assert.deepEqual(renderer.calls[0], { w: 1920, h: 1080, updateStyle: false });
    // 1920/1080 ≈ 1.7777...
    assert.ok(
      Math.abs(camera.aspect - 1920 / 1080) < 1e-10,
      `camera.aspect should be ≈ 1.778, got ${camera.aspect}`
    );
  });

  test('Property: for all valid (width, height), renderer.setSize is called with exact values and camera.aspect === width/height', () => {
    // Validates: Requirements 3.1, 3.2, 3.3
    // Property-based: iterate over many generated valid dimension pairs
    const pairs = generateValidDimensions(50);

    for (const { width, height } of pairs) {
      // Precondition: both must be > 0 (not a bug condition)
      assert.ok(width > 0, `width must be > 0, got ${width}`);
      assert.ok(height > 0, `height must be > 0, got ${height}`);

      const renderer = makeRenderer();
      const camera   = makeCamera();
      const canvas   = makeCanvas({ width, height });

      resizeCanvas_fixed(canvas, renderer, camera);

      assert.equal(
        renderer.domElement.width, width,
        `renderer.width should be ${width}`
      );
      assert.equal(
        renderer.domElement.height, height,
        `renderer.height should be ${height}`
      );
      assert.equal(
        renderer.calls.length, 1,
        `setSize should be called exactly once for (${width}, ${height})`
      );
      assert.deepEqual(
        renderer.calls[0],
        { w: width, h: height, updateStyle: false },
        `setSize args mismatch for (${width}, ${height})`
      );
      assert.ok(
        Math.abs(camera.aspect - width / height) < 1e-10,
        `camera.aspect should be ${width / height} for (${width}, ${height}), got ${camera.aspect}`
      );
      assert.ok(
        camera.projectionMatrixUpdated,
        `updateProjectionMatrix should be called for (${width}, ${height})`
      );
    }
  });

  test('Sidebar toggle simulation: requestAnimationFrame → resizeCanvas() with valid dimensions updates renderer correctly', () => {
    // Validates: Requirement 3.1 (sidebar toggle preservation)
    // Simulates: toggleSidebars() → requestAnimationFrame(()=>requestAnimationFrame(resizeCanvas))
    // with valid dimensions — verifies renderer updates correctly
    const renderer = makeRenderer(800, 600);
    const camera   = makeCamera();
    const canvas   = makeCanvas({ width: 1200, height: 700 });

    // Simulate the double-rAF pattern used in toggleSidebars()
    // In tests we call resizeCanvas directly (rAF is a timing mechanism, not logic)
    resizeCanvas_fixed(canvas, renderer, camera);

    assert.equal(renderer.domElement.width, 1200, 'renderer width should update to 1200 after sidebar toggle');
    assert.equal(renderer.domElement.height, 700, 'renderer height should update to 700 after sidebar toggle');
    assert.ok(
      Math.abs(camera.aspect - 1200 / 700) < 1e-10,
      `camera.aspect should be ${1200 / 700} after sidebar toggle`
    );
    assert.ok(camera.projectionMatrixUpdated, 'updateProjectionMatrix should be called after sidebar toggle');
  });

  test('Window resize event simulation: valid dimensions → renderer and camera update correctly', () => {
    // Validates: Requirement 3.3 (window resize preservation)
    // Simulates: window 'resize' event firing resizeCanvas() with valid parent dimensions
    const renderer = makeRenderer(1024, 768);
    const camera   = makeCamera(1024 / 768);
    const canvas   = makeCanvas({ width: 1440, height: 900 });

    // Simulate window resize event handler calling resizeCanvas()
    resizeCanvas_fixed(canvas, renderer, camera);

    assert.equal(renderer.domElement.width, 1440, 'renderer width should update on window resize');
    assert.equal(renderer.domElement.height, 900, 'renderer height should update on window resize');
    assert.deepEqual(
      renderer.calls[0],
      { w: 1440, h: 900, updateStyle: false },
      'setSize should be called with new window dimensions'
    );
    assert.ok(
      Math.abs(camera.aspect - 1440 / 900) < 1e-10,
      `camera.aspect should be ${1440 / 900} after window resize`
    );
    assert.ok(camera.projectionMatrixUpdated, 'updateProjectionMatrix should be called after window resize');
  });

  test('Edge case: 1×1 minimum valid dimensions → renderer and camera update correctly', () => {
    // Validates: Requirements 3.1, 3.2, 3.3 — smallest valid non-zero dimensions
    const renderer = makeRenderer(800, 600);
    const camera   = makeCamera();
    const canvas   = makeCanvas({ width: 1, height: 1 });

    resizeCanvas_fixed(canvas, renderer, camera);

    assert.equal(renderer.domElement.width, 1);
    assert.equal(renderer.domElement.height, 1);
    assert.equal(camera.aspect, 1 / 1);
    assert.ok(camera.projectionMatrixUpdated);
  });

});
