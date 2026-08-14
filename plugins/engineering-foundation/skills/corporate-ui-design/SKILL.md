---
name: corporate-ui-design
description: Define and implement one coherent professional UI direction with design tokens, responsive behavior, light/dark quality, accessibility, and visual verification. Use for websites and product UI; avoid unsolicited variants and generic agent aesthetics.
---

# Corporate UI Design

## Establish direction

1. Inspect existing brand assets, UI, component library, content, audience, and visual references.
2. Preserve an existing design system unless redesign is requested.
3. If none exists, define one direction before code:
   - brand character and narrative;
   - color roles;
   - typography roles;
   - spacing and grid;
   - shape/elevation rules;
   - component behavior;
   - light and dark theme intent.
4. Save or update `DESIGN.md` when the project needs a durable contract.

## Quality rules

- Produce one composition, not several guesses.
- Use typography deliberately; verify all required language glyphs, including Turkish.
- Use one clear accent unless the brand requires more.
- Prefer hierarchy, whitespace, alignment, imagery, and type over decorative containers.
- Cards exist only when they clarify an interaction or grouped object.
- Avoid generic dashboard mosaics, glassmorphism, random gradients, neon green dark themes, excessive radius, floating badges, and empty oversized heroes.
- Light and dark themes need independent contrast, surfaces, borders, imagery, and state checks.
- Use real content density and complete empty/loading/error/success states.
- Keep semantic HTML, keyboard navigation, focus, reduced motion, contrast, and responsive behavior first-class.
- Add metadata, canonical URLs, and structured data only when they match actual page content.

## Verification

Use the project's browser/Playwright tooling when available:

- target viewport matrix;
- keyboard and focus path;
- interactive states;
- console and network errors;
- layout overflow;
- visual comparison to references;
- light/dark screenshots;
- performance checks appropriate to the surface.

If visual tools are unavailable, say so. Do not claim a polished result from source inspection alone.

## Completion lock

After the accepted direction and verification pass, do not create a new palette, font pairing, layout, or variant unless the user requests a redesign or evidence exposes a defect.

Read `references/design-quality.md` and start from `assets/DESIGN.template.md` when appropriate.
