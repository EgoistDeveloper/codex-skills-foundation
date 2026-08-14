---
version: "0.1"
name: "Project design system"
description: "One coherent visual and interaction contract."
colors:
  background: "#F7F7F5"
  surface: "#FFFFFF"
  text-primary: "#17191C"
  text-muted: "#60656D"
  border: "#D9DCE1"
  accent: "#2F5C8F"
  on-accent: "#FFFFFF"
typography:
  display:
    fontFamily: "REPLACE_WITH_VERIFIED_FONT"
    fontSize: "3rem"
    fontWeight: 650
    lineHeight: 1.05
  body:
    fontFamily: "REPLACE_WITH_VERIFIED_FONT"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "REPLACE_WITH_VERIFIED_FONT"
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.3
rounded:
  sm: "4px"
  md: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.sm}"
    padding: "12px 18px"
---

## Overview

Describe the audience, brand character, product narrative, and the single selected visual direction.

## Colors

Explain semantic roles, light/dark mapping, contrast requirements, and prohibited uses.

## Typography

Record verified font sources, licenses, supported glyphs, fallback metrics, hierarchy, and line-length rules.

## Layout

Define container widths, grid, spacing rhythm, responsive recomposition, and information density.

## Elevation & Depth

Use the minimum depth needed for hierarchy and interactive separation.

## Shapes

Define radius and icon geometry. Avoid arbitrary variation.

## Components

Define only recurring component rules and all interactive states.

## Do's and Don'ts

List project-specific visual invariants and anti-patterns.
