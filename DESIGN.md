---
name: Tool
description: A dark, dense instrument panel for scoring evaluations and running tenders.
colors:
  ink: "#080b12"
  surface: "#0e1220"
  panel: "#131929"
  panel-raised: "#192034"
  border: "#1e2b42"
  border-strong: "#2a3d5c"
  text: "#dde4f0"
  text-muted: "#9aa8c4"
  text-faint: "#7586a8"
  signal-blue: "#4f7eff"
  signal-teal: "#34d1b0"
  state-good: "#34c47a"
  state-warn: "#f0a742"
  state-bad: "#e05555"
  grade-a: "#34c47a"
  grade-b: "#7ed957"
  grade-c: "#f0a742"
  grade-d: "#f07042"
  grade-e: "#e05555"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
  section:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.05em"
rounded:
  input: "12px"
  card: "14px"
  chip: "999px"
spacing:
  card-padding: "20px"
  gap: "24px"
components:
  button-primary:
    backgroundColor: "{colors.signal-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.input}"
    padding: "8px 14px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.input}"
    padding: "8px 14px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.input}"
    padding: "9px 12px"
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.card}"
    padding: "20px"
  chip:
    textColor: "{colors.text-muted}"
    rounded: "{rounded.chip}"
    padding: "1px 8px"
---

# Design System: Tool

## Overview

**Creative North Star: "The Instrument Panel"**

A working surface for people reading numbers carefully: precise, dense where the task needs it, quiet everywhere else. Panels sit on a near-black ground; colour is reserved for state and for the A to E grade, so a coloured thing always means something. The interface is used for long scoring sessions at a desk, so contrast and legibility outrank flourish.

The system stays in Operate mode: familiar controls, consistent vocabulary, and live recalculation. The slider is the signature control: it moves, and the estimated score and grade respond at once.

**Key Characteristics:**
- Dark, tonal layering (ink, surface, panel, raised panel); no decorative shadows.
- One accent (signal blue) for primary actions, selection and focus; teal appears only as a secondary data accent.
- Grade colour is semantic and never decorative.
- System font stack; hierarchy through weight and size, not typeface.
- Tabular numerals wherever numbers align.

## Colors

A restrained dark palette with one accent and a semantic state set.

### Primary
- **Signal Blue** (#4f7eff): primary buttons, selected tab underline, focus ring, active template outline, scored-slider fill.

### Secondary
- **Signal Teal** (#34d1b0): assistant avatar and blind-scoring reassurance only. Never on a button.

### Neutral
- **Ink** (#080b12): page ground, with two faint radial washes at the top right and bottom left.
- **Surface** (#0e1220): inputs and recessed wells inside cards.
- **Panel** (#131929) and **Panel Raised** (#192034): cards and their hover or selected state.
- **Border** (#1e2b42) and **Border Strong** (#2a3d5c): hairlines; the strong one for hover and control edges.
- **Text** (#dde4f0), **Text Muted** (#9aa8c4, about 7.6:1 on panel), **Text Faint** (#7586a8, about 4.8:1 on panel): the three text tiers. Faint is the floor for any readable text.

### State and grade
- **Good** (#34c47a), **Warn** (#f0a742), **Bad** (#e05555) for success, divergence and errors. Grades A to E run #34c47a, #7ed957, #f0a742, #f07042, #e05555.

### Named Rules
**The Colour Means Something Rule.** If an element is coloured, it communicates state, grade or the single primary action. Nothing is coloured to be pretty.
**The Faint Floor Rule.** No text is dimmer than Text Faint. Placeholders and hints use it; nothing goes lower.

## Typography

**Display / Body / Label Font:** the platform system stack (-apple-system, Segoe UI, Roboto, Helvetica, Arial). One family throughout.

**Character:** neutral and quick to read; the product's voice lives in the numbers, not the letterforms.

### Hierarchy
- **Page title** (800, 18-20px, tight tracking): the wordmark and a tender's name.
- **Section heading** (600, 14px, uppercase, 0.05em tracking, Text Muted): panel groupings such as "Templates" and "Tickets".
- **Card heading** (600, 16px): a ticket subject, a form title.
- **Body** (400, 14px, 1.6): all running text; prose capped near 65ch.
- **Label** (600, 12px, Text Muted): field labels. **Hint** (400, 12px, Text Faint): helper text.

### Named Rules
**The Tabular Rule.** Numbers that align or change live use tabular numerals.

## Layout

A centred column up to 72rem with 20px side padding. Content sits on a 12-column-style grid of 24px gaps: a two-thirds main column beside a one-third assistant column on Evaluate, a one-quarter list beside a three-quarter workbench on Tenders, and a three-fifths input table beside a two-fifths result on Sensitivity. Below the large breakpoint everything stacks. Grid children use `min-width: 0` so wide tables scroll inside their card instead of stretching the page. Dense data lives in tables with 10px cell padding; cards use 20px.

## Elevation & Depth

Flat by default; depth comes from tone (ink, surface, panel, raised), not shadow. The only shadow is a faint 20px coloured glow under the selected template card. The header is sticky with a light backdrop blur over a translucent ink fill, which is a functional separation rather than decoration.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. Hover raises a card by tone (panel to panel raised) and strengthens its border.

## Shapes

Rounded but not soft: 12px on controls, 14px on cards, 10px on small buttons, full pills for chips and status. Hairline 1px borders define every container; no coloured side stripes.

## Components

### Buttons
- **Shape:** 12px radius (10px small), 13px semibold text, 8px by 14px padding.
- **Primary:** signal blue fill, white text; hover brightens.
- **Ghost (default):** transparent with a Border Strong edge; hover turns edge and text signal blue.
- **Danger:** same as ghost; hover turns edge and text red.
- **Disabled:** 50% opacity, not-allowed cursor.

### Chips
Pill, 11px semibold, Border Strong edge, Text Muted. Variants add a tinted fill and matching edge for good, warn, bad and accent states.

### Cards / Containers
Panel fill, 1px Border, 14px radius, 20px padding. Selectable cards raise to Panel Raised on hover.

### Inputs / Fields
Surface fill, 1px Border, 12px radius. Focus shifts the border to signal blue; keyboard focus adds a 2px signal-blue outline with a 2px offset. Placeholders use Text Faint.

### Navigation
A tab strip under the header: 14px semibold, Text Muted, with a 2px signal-blue underline on the selected tab. Tabs scroll horizontally on narrow screens.

### Data tables
Header row in 11px uppercase Text Faint, hairline row dividers, right-aligned tabular numerals.

### Grade badge (signature)
A rounded square tinted with the grade colour, holding the letter and score. It is the one place colour carries the headline.

## Do's and Don'ts

### Do:
- **Do** keep colour semantic: state, grade or the primary action.
- **Do** use tabular numerals for scores, weights and spreads.
- **Do** give every control a visible label and a visible keyboard focus.
- **Do** keep copy in English, with controls named for their action.

### Don't:
- **Don't** use gradient text, bounce or elastic easing, or glass as decoration (the detector flags them).
- **Don't** add coloured side borders thicker than 1px to cards or alerts.
- **Don't** show another evaluator's scores anywhere while scoring is open.
- **Don't** let text fall below Text Faint contrast, or use colour alone to convey state.
- **Don't** add decorative motion; transitions are 150ms ease-out and only convey state.
