# ADR-075: Postmodern Theme System

**Status:** In Progress
**Date:** 2025-01-09
**Branch:** `feature/postmodern-theme`

## Context

The current UI uses a standard shadcn/ui theme with blue primary colors and system fonts. We want to implement a warmer, more distinctive "postmodern" design system featuring:

- Warm amber/rust primary accent (hue ~18°)
- Three modes: dark, twilight, light
- HSL-based color system with user-customizable accents
- Typography: JetBrains Mono, Space Grotesk, IBM Plex Sans Condensed
- Optional dither patterns for texture
- Surface hierarchy (surface-1, surface-2, surface-3)

Reference: https://github.com/aaronsb/postmodern-theme/blob/main/postmodern-ui.html

## Decision

Implement the postmodern theme as a progressive enhancement, maintaining compatibility with existing Tailwind classes while adding new capabilities.

## Implementation Checklist

### Phase 1: Core CSS Variables & Fonts
- [ ] Add Google Fonts imports (JetBrains Mono, Space Grotesk, IBM Plex Sans Condensed)
- [ ] Update `index.css` with postmodern CSS variables
  - [ ] Primary accent (HSL components: --primary-h, --primary-s, --primary-l)
  - [ ] Background tone (--bg-h, --bg-s, --bg-l)
  - [ ] Foreground tone (--fg-h, --fg-s, --fg-l)
  - [ ] Border colors
  - [ ] Surface hierarchy (--surface-1, --surface-2, --surface-3)
  - [ ] Status colors (active, warning, info)
- [ ] Update `tailwind.config.js`
  - [ ] Add surface-1/2/3 color tokens
  - [ ] Add font family definitions
  - [ ] Add text size scale (--text-xs through --text-3xl)
  - [ ] Add spacing scale if different from Tailwind defaults
- [ ] Create `.dark`, `.twilight`, `.light` mode classes in CSS

### Phase 2: Theme Store Enhancement
- [ ] Update `themeStore.ts`
  - [ ] Add 'twilight' to ThemePreference type
  - [ ] Update resolveTheme() for twilight
  - [ ] Update applyTheme() to add/remove twilight class
  - [ ] Add color customization state
    - [ ] primaryHue (0-360)
    - [ ] primarySaturation (0-100)
    - [ ] primaryLightness (0-100)
    - [ ] backgroundHue (0-360)
    - [ ] backgroundSaturation (0-100)
  - [ ] Add setPrimaryColor() action
  - [ ] Add setBackgroundTone() action
  - [ ] Persist customizations to localStorage

### Phase 3: Explorer Style Updates
- [ ] Update `web/src/explorers/common/styles.ts`
  - [ ] Add twilight mode colors for canvas3D
  - [ ] Add twilight mode colors for grid3D
  - [ ] Update hex values to warm postmodern palette
    - [ ] Dark: warm dark brown/charcoal
    - [ ] Twilight: golden hour mid-tones
    - [ ] Light: warm cream (not pure white)
- [ ] Update `web/src/explorers/common/labelStyles.ts`
  - [ ] Update LABEL_FONTS.family to postmodern stack
  - [ ] Add twilight mode to LUMINANCE_TRANSFORMS
  - [ ] Update ColorTransform.getLabelColors() for twilight

### Phase 4: Component Audit - Remove Hardcoded Colors
- [ ] Audit NodeInfoBox.tsx
  - [ ] Replace `dark:bg-gray-800` → semantic tokens
  - [ ] Replace `dark:text-gray-400` → `text-muted-foreground`
  - [ ] Replace `dark:border-gray-600` → `border-border`
  - [ ] Add twilight-aware classes where needed
- [ ] Audit EdgeInfoBox.tsx (same as above)
- [ ] Audit ForceGraph2D.tsx
  - [ ] Check theme-dependent color logic
  - [ ] Ensure twilight mode handled
- [ ] Audit ForceGraph3D.tsx (same as above)
- [ ] Audit other components using `dark:gray-*` pattern
  - [ ] AboutInfoBox.tsx
  - [ ] BlockBuilder components
  - [ ] SearchBar
  - [ ] IconRailPanel
  - [ ] Any other sidebar/panel components

### Phase 5: Theme Customization UI (in Preferences)
- [ ] Update PreferencesWorkspace.tsx theme section
  - [ ] Add three-way mode toggle (dark/twilight/light)
  - [ ] Add primary accent color picker
    - [ ] Hue slider or grid (12 steps × 30°)
    - [ ] Saturation slider (40-100%)
    - [ ] Lightness slider (35-65%)
  - [ ] Add background tone picker
    - [ ] Hue slider (match or contrast primary)
    - [ ] Saturation slider (0-30% for subtle tint)
  - [ ] Add preview swatch showing current colors
  - [ ] Add "Reset to defaults" button
- [ ] Consider: Live preview as user adjusts sliders

### Phase 6: Shape & Border Refinements
- [ ] Update border-radius to squared-off aesthetic
  - [ ] Change `--radius` in CSS from 0.5rem to smaller value (2px or 0)
  - [ ] Audit `rounded-lg`, `rounded-md`, `rounded-full` usage
  - [ ] Pill boxes / badges → squared corners (not capsule shape)
  - [ ] Buttons → subtle radius or sharp corners
  - [ ] Cards/panels → sharp or minimal radius
  - [ ] Consider: Keep slight radius (1-2px) for softer feel, or go full brutalist (0px)
- [ ] Update Tailwind config borderRadius values
  - [ ] `lg`: 2px (was ~8px)
  - [ ] `md`: 1px (was ~6px)
  - [ ] `sm`: 0px (was ~4px)
  - [ ] Or create new `sharp` variant

### Phase 7: Optional Enhancements
- [ ] Dither patterns
  - [ ] Add SVG dither pattern definitions
  - [ ] Add utility classes (dither-25, dither-50, dither-75)
  - [ ] Add DPI presets (dpi-fine, dpi-retina)
- [ ] Typography refinements
  - [ ] Ensure monospace used for code/technical content
  - [ ] Display font for headings
  - [ ] Body font for UI text
- [ ] Animation/transition polish
  - [ ] Smooth color transitions on theme change
  - [ ] Respect prefers-reduced-motion

### Phase 8: Future - Server Persistence (Not This PR)
- [ ] Design API endpoint for user preferences
- [ ] Add database table for user theme settings
- [ ] Sync localStorage ↔ API on login
- [ ] Handle offline/online transitions

## Color Reference

### Default Postmodern Palette

**Primary Accent (Amber/Rust)**
- Hue: 18°
- Saturation: 100%
- Lightness: 60%

**Dark Mode**
- Background: hsl(18, 8%, 10%)
- Foreground: hsl(18, 15%, 85%)
- Surface step: +3% lightness

**Twilight Mode**
- Background: hsl(18, 15%, 16%)
- Foreground: hsl(18, 15%, 96%)
- Surface step: +5% lightness
- Saturation multiplier: 1.2×

**Light Mode**
- Background: hsl(18, 8%, 94%)
- Foreground: hsl(18, 15%, 15%)
- Surface step: -3% lightness

**Status Colors (constant across modes)**
- Active/Success: hsl(145, 65%, 45%)
- Warning: hsl(40, 85%, 55%)
- Info: hsl(210, 70%, 55%)

## Typography

| Role | Font Family | Usage |
|------|-------------|-------|
| Monospace | JetBrains Mono | Code, IDs, technical labels |
| Display | Space Grotesk | Headings, titles |
| Body | IBM Plex Sans Condensed | UI text, buttons, descriptions |

## Consequences

### Positive
- Distinctive, warm visual identity
- User customization increases engagement
- Twilight mode provides comfortable viewing option
- HSL-based system makes color math predictable

### Negative
- Additional complexity in theme management
- Font loading adds to initial page weight (~100-200KB)
- Need to maintain three mode variations
- Explorer canvas colors require manual updates (not CSS-driven)

### Risks
- Color contrast may need accessibility testing
- Custom colors could create poor combinations (may need guardrails)
- Twilight mode in 3D explorer needs careful tuning

## Related ADRs
- ADR-067: Workstation UI Architecture (defines workspace structure)
- ADR-074: Platform Admin UI (preferences are part of this)
