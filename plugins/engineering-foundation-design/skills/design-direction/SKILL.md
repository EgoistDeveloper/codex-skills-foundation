---
name: design-direction
description: Establish one implementation-ready interface direction with content hierarchy, typography, spacing, color, component geometry, responsive behavior, states, accessibility, and performance constraints. Use before creating or substantially redesigning a web or product interface. Do not generate unsolicited variants or replace an existing design system without an explicit redesign request.
---


# Design Direction

## Read before inventing

Inspect the product, brand assets, content, existing components, CSS/tokens, screenshots, audience, and any `DESIGN.md`. Existing product truth outranks fashionable defaults.

When a Google-style `DESIGN.md` exists, consume its tokens and rationale and run its linter when available. Treat that format as an optional evolving project contract, not a universal dependency. Create or replace one only when requested or when durable design decisions are part of the accepted task.

## Commit to one direction

Define:

- audience, job, and content hierarchy;
- one-sentence visual premise;
- typefaces, weights, fallbacks, glyph coverage, and loading budget;
- spacing, grid, density, radii, borders, shadows, and motion;
- semantic color tokens and contrast intent for light/dark surfaces;
- component and icon geometry;
- breakpoints and responsive behavior;
- loading, empty, error, validation, success, disabled, permission, and overflow states;
- accessibility and performance constraints.

For Turkish products, verify `İ ı Ş ş Ğ ğ Ç ç Ö ö Ü ü` in every selected font and required weight.

Avoid giant empty heroes, nested card mosaics, arbitrary glass, decorative blobs, gratuitous gradients, inconsistent icon strokes, and copy written merely to fill rectangles. These are symptoms, not a design system. Make each choice serve hierarchy, trust, usability, or brand.

Start from `assets/DESIGN.template.md` when a durable contract is appropriate.
