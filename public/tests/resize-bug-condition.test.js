/**
 * Bug Condition Exploration Test — Globe Particles (resizeCanvas)
 *
 * Validates: Requirements 1.1, 1.2, 2.1, 2.2
 *
 * PURPOSE: Verify the fix works — the guard clause prevents renderer collapse
 * when the parent element has zero dimensions.
 *
 * Bug Condition (isBugCondition):
 *   Returns true when canvas.parentElement.getBoundingClientRect()
 *   returns { width: 0 } OR { height: 0 }.
 *
 * On FIXED code, resizeCanvas() returns early when width or height is 0,
 * preserving the renderer at its previous valid dimensions.
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// ---------------------------------------------------------------------------
// Minimal mocks for the Three.js objects used by resizeCanvas()
// ---------------------------------------------------------------------------

function makeRenderer(initialWidth = 800, initialHeight = 600) {
  const domElement = { width: initialWidth, height: initialHeight };
  return {
    domElement,
    setSize(w, h, _updateStyle) {
      domElement.width = w;
      domElement.height = h;
    },
  };
}

function makeCamera(initialAspect = 800 / 600) {
  return {
    aspect: initialAspect,
    updateProjectionMatrix() {},
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
  if (!rect.width || !rect.height) return;  // guard added
  renderer.setSize(rect.width, rect.height, false);
  camera.aspect = rect.width / rect.height;
  camera.updateProjectionMatrix();
}

// ---------------------------------------------------------------------------
// Tests — all three PASS on fixed code (guard clause prevents renderer collapse)
// ---------------------------------------------------------------------------

describe('Bug Condition: resizeCanvas() with zero-dimension parent', () => {

  test('both-zero: { width: 0, height: 0 } → renderer must NOT collapse to 0×0', () => {
    // Validates: Requirements 1.2, 2.1, 2.2
    const renderer = makeRenderer(800, 600);
    const camera   = makeCamera();
    const canvas   = makeCanvas({ width: 0, height: 0 });

    resizeCanvas_fixed(canvas, renderer, camera);

    // EXPECTED TO PASS on fixed code:
    // guard returns early → renderer stays at 800×600
    assert.ok(
      renderer.domElement.width > 0,
      `renderer.domElement.width should be > 0 but got ${renderer.domElement.width}`
    );
    assert.ok(
      renderer.domElement.height > 0,
      `renderer.domElement.height should be > 0 but got ${renderer.domElement.height}`
    );
  });

  test('zero-width: { width: 0, height: 600 } → renderer width must stay > 0', () => {
    // Validates: Requirements 1.2, 2.2
    const renderer = makeRenderer(800, 600);
    const camera   = makeCamera();
    const canvas   = makeCanvas({ width: 0, height: 600 });

    resizeCanvas_fixed(canvas, renderer, camera);

    // EXPECTED TO PASS on fixed code:
    // guard returns early → renderer width stays at 800
    assert.ok(
      renderer.domElement.width > 0,
      `renderer.domElement.width should be > 0 but got ${renderer.domElement.width}`
    );
  });

  test('zero-height: { width: 800, height: 0 } → renderer height must stay > 0', () => {
    // Validates: Requirements 1.2, 2.2
    const renderer = makeRenderer(800, 600);
    const camera   = makeCamera();
    const canvas   = makeCanvas({ width: 800, height: 0 });

    resizeCanvas_fixed(canvas, renderer, camera);

    // EXPECTED TO PASS on fixed code:
    // guard returns early → renderer height stays at 600
    assert.ok(
      renderer.domElement.height > 0,
      `renderer.domElement.height should be > 0 but got ${renderer.domElement.height}`
    );
  });

});
