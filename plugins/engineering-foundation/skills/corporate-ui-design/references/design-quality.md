# Design quality checklist

## Typography

- Confirm license and web delivery format.
- Confirm language glyphs: `İ ı Ş ş Ğ ğ Ç ç Ö ö Ü ü`.
- Limit the number of families and weights.
- Define display, headline, body, label, caption, and numeric roles.
- Check line length, line height, heading wraps, and fallback metrics.
- Do not use a default font stack merely because it is familiar; an existing brand system may still require one.

## Layout

- One primary composition per viewport.
- Clear content order and section purpose.
- Stable grid, spacing scale, and container widths.
- Mobile is recomposed, not just compressed.
- Dense product UI remains readable; marketing UI remains purposeful.

## Color and themes

- Semantic tokens, not raw colors scattered through components.
- One dominant action accent.
- Contrast checked for text, icons, borders, focus, disabled, and hover states.
- Dark mode is not a color inversion.
- Do not use brand-inconsistent green or cyan as a generic “dark tech” accent.

## Components

- Complete interactive states.
- Notifications have one owner, are accessible, and can be dismissed when persistent.
- Tables support scanning, overflow, empty state, loading, and mobile alternatives.
- Modals and drawers trap focus appropriately and restore it on close.
- Destructive actions are visually distinct and require suitable confirmation.

## Anti-pattern test

Remove every shadow, border, radius, badge, gradient, and container that does not improve interaction, hierarchy, or brand expression.
