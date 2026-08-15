---
name: design-direction
description: Establish one implementation-ready interface direction with content hierarchy, typography, spacing, color, component geometry, responsive behavior, states, accessibility, and performance constraints. Use before creating or substantially redesigning a web/product interface. Do not generate multiple visual directions unless the user explicitly requests alternatives.
license: MIT
metadata:
  author: EgoistDeveloper
  version: "0.2.0"
---

# Design Direction

## Read before inventing

Inspect the existing product, brand assets, components, content, CSS/tokens, screenshots, and any `DESIGN.md`. Existing product truth outranks fashionable defaults.

When a Google-style `DESIGN.md` exists, consume its tokens and rationale and run its linter when available. Treat the format as an optional evolving project contract, not a universal dependency. Create or replace one only when explicitly requested.

## Commit to one direction

Define:

- audience, job, and content hierarchy;
- visual premise in one sentence;
- typefaces, weights, fallback strategy, and loading budget;
- spacing, grid, density, radii, borders, shadows, and motion rules;
- semantic color tokens and contrast intent;
- component and icon geometry;
- breakpoints and responsive behavior;
- loading, empty, error, validation, success, disabled, and permission states;
- accessibility and performance constraints.

For Turkish products, verify `İ ı Ş ş Ğ ğ Ç ç Ö ö Ü ü` across selected fonts and weights.

Avoid generic visual noise: giant empty heroes, nested cards, arbitrary glass, decorative blobs, gratuitous gradients, inconsistent icon strokes, and copy that exists only to fill rectangles. These are symptoms, not a design system. Make every choice serve hierarchy, trust, usability, or brand.
