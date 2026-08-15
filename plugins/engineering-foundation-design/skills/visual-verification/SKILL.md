---
name: visual-verification
description: Verify a rendered interface against its design direction across representative viewports, interaction states, keyboard use, accessibility, content density, and runtime behavior. Use after UI implementation or when diagnosing visual regressions. Do not approve a design from source code alone when a rendered surface can be inspected.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Visual Verification

Inspect the rendered result, not merely the component tree.

## Evidence set

- screenshots at representative narrow, medium, and wide viewports;
- critical states: loading, empty, error, validation, success, disabled, overflow, and long localized content;
- keyboard traversal, visible focus, escape/dismiss behavior, and modal focus containment;
- heading order, labels, semantic controls, and accessible names;
- contrast and non-color cues;
- clipping, horizontal overflow, layout shift, image/font loading, and motion preferences;
- browser console and relevant network/runtime failures;
- comparison with the accepted design direction or `DESIGN.md` tokens.

## Review rule

Report deviations with viewport, state, element, expected behavior, observed behavior, and evidence. Fix material defects, rerender, and perform one final comparison. Do not redesign the product during visual QA unless the contract itself is wrong.
