# DESIGN_NOTES.md — De-AI-ify the Disaster Response GUI (rev. 2)

Working branch: `gui-testing`. Every change on this branch must satisfy the brief
below. Commit messages must name the principle each change serves; do not squash
the UX reasoning out of history.

## Step 1 — The message

North star: **"You are safe here. When the moment comes, this system will not fail you."**

- The screen's job is to get a person to safety and make the system feel *dependable
  during an actual emergency* — not to impress anyone with design.
- First thing a user must grasp, in under 2 seconds: **where to go / what to do now.**
- The emotional bar is a **well-run municipal emergency operations center** — calm
  competence, professional and presentable. Not a hazard sign, not a startup
  dashboard, not an AI/social-app look. Every decision is judged by: "does this make
  someone trust this system in a crisis, or does it make them think 'some app'?"

## Step 2 — User and context

- Users: Metro Manila residents, barangay officials, and responders during flooding,
  typhoons, and earthquakes — plus the same people reading it calmly beforehand.
- Prior knowledge: mixed literacy and tech familiarity, teens to elderly. No
  onboarding, no tutorial, one glance and go.
- Constraints: mobile-first, one-handed, old/low-end Android, weak signal, low light
  or a cracked screen, high stress, low battery. Avoid animation-heavy / GPU-heavy UI.
  Must hold contrast under glare and at reduced brightness (WCAG AA).

## Step 3 — Message → UI principles

Need: reassurance + urgency + authority. Landing zone: calm competence, not sterility,
not fear.

- **Typography** — no default AI/SaaS faces (Inter, Poppins, Manrope, Nunito,
  "system-ui"). Use a confident structured grotesk/humanist sans with presence:
  IBM Plex Sans / Archivo (regular cut) / Public Sans / Source Sans / Barlow.
  Headers carry more weight than body; **no all-caps everywhere**; no stencil or
  military faces. Legibility and quiet authority over decoration. IBM Plex Mono
  reserved for data, codes, and labels (control-room convention).
- **Color** — navy / slate / graphite foundation, **one warm accent**
  (measured amber-orange) for primary actions and status. **True red only for live
  alerts** — never for everyday buttons or navigation. No pastels, no gradient
  meshes, no oversaturation, no all-dark/all-red menace. Semantic status keeps its
  own quiet colors (green = open/safe, amber = near-full, red = full/alert).
- **Shape & structure** — moderate corner radii (not exaggerated "AI app" rounding,
  not military-sharp), light hairline borders/dividers, clear grid alignment, strong
  hierarchy. The primary emergency action must visually dominate every screen it
  appears on without the rest feeling barren or aggressive.
- **Frosted glass — restrained, purposeful** — at most 1–2 elevated surface types
  per screen where a surface floats over busy content: the sticky nav/header and the
  map's bottom dock. Subtle blur + translucency + hairline border; text stays fully
  legible without a drop-shadow crutch. Never on every card/button.
- **Motion** — short, snappy, simple easing; no bouncy springs, no decorative
  fade-ins. If something moves it communicates status (live indicator, state change).
- **Copy** — calm, direct, like a competent dispatcher or safety briefing. No emoji,
  no "You're all set!", and no clipped all-caps commands except in genuine alerts.
  Primary CTA labels may carry more weight; the rest speaks normally.
- **Density & spacing** — balanced: organized and scannable like a dashboard. Big,
  obvious tap targets for primary actions; tighter, efficient layout for lists/tables.
- **Icons** — plain geometric line/solid glyphs (lucide, Material Symbols in line
  weight). Not playful, not 3D, not hazard-stencil.

## Implementation mapping

1. Type: Oswald + Archivo Narrow (condensed) + IBM Plex Mono → **IBM Plex Sans**
   (400/500/600/700) body+headers, **IBM Plex Mono** for data/labels.
2. Palette: red CTA/nav → **amber-orange primary buttons + accent**; navy/slate
   surfaces; red only on the danger strip, Full badges, and alert flashes.
3. Surfaces: dark navy nav + slate-light panels; **hairline** borders; shadows
   softened to dashboard level.
4. Radius: 2px (military-sharp) → **moderate 8px**; no fully-rounded pill builds.
5. Glass: only the **sticky nav** and the **map turn-by-turn dock / tile-fallback
   pill** — subtle blur + translucency.
6. Motion: snappy (≤~150 ms) transitions on buttons/cards; the rest already minimal.
7. Copy/weight: sentence-case headers; the one emergency CTA is the only shout.
8. Dark mode: default via `prefers-color-scheme: dark`, no toggle.

## Step 5 — checklist before committing

- [ ] The one action is obvious on each screen within 2 seconds.
- [ ] Nothing reads as a default AI/SaaS kit (type, spacing, pastel gradients,
      rounded-everything).
- [ ] Professional and presentable — at home in a municipal ops dashboard,
      not harsh, sparse, or alarming.
- [ ] Glass on ≤2 surface types, with legible text; not everywhere.
- [ ] Contrast legible in sunlight and on a dim/cracked screen (AA).
- [ ] Copy is calm dispatcher; intensity reserved for genuine alerts.
- [ ] Feels specific to this system, not a reskinned template.
- [ ] Offline/graceful-degradation behavior untouched.