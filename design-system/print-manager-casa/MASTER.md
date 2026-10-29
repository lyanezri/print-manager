# Design System Master File — Neo-Brutalist Print Workshop

**Project:** Print Manager Casa (Taller de Imprenta)
**Style:** Industrial Neo-Brutalism + Bauhaus Print Press
**Design Dials:** Variance 9/10 (Bold/Tactile) | Motion 6/10 (Mechanical Press) | Density 8/10 (POS Console)

---

## 1. Visual Identity & Color Tokens (CMYK + Raw Paper + Ink)

| Role | Light (Raw Paper) | Dark (Carbon Press) | CSS Variable |
|------|-------------------|---------------------|--------------|
| Paper / Background | `#F4EFE6` | `#121210` | `--bg-paper` |
| Card / Surface | `#FFFDF9` | `#1C1B18` | `--bg-card` |
| Muted / Recessed | `#E8E1D5` | `#262521` | `--bg-muted` |
| Ink / Foreground | `#111111` | `#F4EFE6` | `--ink` |
| Secondary Ink | `#4A4740` | `#A8A29E` | `--ink-muted` |
| Hard Border & Shadow | `#111111` | `#000000` (border `#F4EFE6`) | `--border-ink` |
| Press Orange (Primary CTA) | `#FF5500` | `#FF661A` | `--accent-orange` |
| CMYK Cyan | `#0090FF` | `#38BDF8` | `--cmyk-c` |
| CMYK Magenta | `#FF1E66` | `#FB7185` | `--cmyk-m` |
| CMYK Yellow | `#FFD000` | `#FACC15` | `--cmyk-y` |
| Cash Green | `#00C46A` | `#10B981` | `--accent-green` |

## 2. Typography
- **Display & UI Headings:** `Space Grotesk` (700–800 weight, tight tracking, uppercase industrial headers)
- **Numbers, Prices & Ticket Specs:** `JetBrains Mono` (600–800 weight, `tabular-nums`)

## 3. Structural & Mechanical Rules
- **Borders:** `2.5px solid var(--border-ink)` on all cards, inputs, and buttons.
- **Hard Offset Shadows:** `4px 4px 0px var(--shadow-ink)` on cards and primary controls.
- **Mechanical Press Physics:**
  - Hover: `transform: translate(-1px, -1px); box-shadow: 5px 5px 0px var(--shadow-ink);`
  - Active / Click: `transform: translate(3px, 3px); box-shadow: 0px 0px 0px var(--shadow-ink);`
- **Print Shop Motifs:**
  - Registration crop marks (`+`) and CMYK calibration bars in header.
  - Perforated serrated thermal receipt edge on the live quote ticket.
