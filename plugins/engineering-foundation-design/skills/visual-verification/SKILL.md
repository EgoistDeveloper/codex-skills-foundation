---
name: visual-verification
description: Verify a rendered interface against its accepted design direction across representative viewports, states, keyboard use, accessibility, content density, and runtime behavior. Use after UI implementation or when diagnosing visual regressions. Do not approve a design from source code alone when a rendered surface can be inspected or redesign during visual QA.
---


# Visual Verification

Inspect the rendered result, not merely the component tree.

## Evidence set

- screenshots at representative narrow, medium, and wide viewports;
- loading, empty, error, validation, success, disabled, permission, overflow, and long localized content states;
- keyboard traversal, visible focus, escape/dismiss behavior, and modal focus containment;
- heading order, labels, semantic controls, and accessible names;
- contrast, non-color cues, reduced-motion behavior, and light/dark surface quality;
- clipping, horizontal overflow, layout shift, image/font loading, and content density;
- browser console and relevant network/runtime failures;
- comparison with the accepted direction or `DESIGN.md` tokens.

Report deviations with viewport, state, element, expected behavior, observed behavior, severity, and evidence. Fix material defects, rerender, and perform one final comparison. Do not quietly change palette, typography, or layout direction during QA unless evidence proves the contract itself is defective.

Use `references/evidence-template.md` for a compact rendered-state report.
