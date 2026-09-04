# DESIGN_NOTES.md — De-AI-ify the Disaster Response GUI

Working branch: `gui-testing`. These notes are the written rationale (brief) that every
change on this branch must satisfy. Keep them verbatim reasons in commit messages.

## Step 1 — The message

North star: **"You are safe here. When the moment comes, this system will not fail you."**

- The screen's job is to get a person to safety and make the system feel *dependable
  during an actual emergency*, not to impress anyone with design.
- The first thing a user must grasp, in under 2 seconds, is: **where to go / what to do now.**
- This is a disaster-response and evacuation-center tool, not a consumer product. Every
  decision is judged against: *does this make someone trust the system in a crisis, or
  does it make them think "some app"?*

## Step 2 — User and context

- Users: Metro Manila residents, barangay officials, and responders during flooding,
  typhoons, and earthquakes — plus the same people checking calmly beforehand to learn
  where their evacuation center is.
- Prior knowledge: mixed literacy and tech skill, teenagers to elderly. No onboarding,
  no tutorial — one glance and go.
- Constraints: mobile-first, often one-handed, on old/low-end Android phones, weak or
  intermittent signal, sometimes low light or a damaged screen, high stress and time
  pressure. Low battery — avoid animation-heavy or GPU-intensive UI.

## Step 3 — Message → UI principles

Need: **reassurance + urgency + authority/trust**, simultaneously. Not softness, not delight.

- **Typography** — no AI/SaaS default faces (Inter, Poppins, Manrope, Nunito,
  "system-ui"). Use the character of official signage and field equipment:
  - Display/headers: `Oswald` (condensed, uppercase, heavy) — hazard-sign weight.
  - Body: `Archivo Narrow`, plain and legible under glare.
  - Data/codes/timestamps: `IBM Plex Mono`, terminal/equipment feel.
  - Uppercase labels and alerts, tight tracking, heavy weights.
- **Color** — no pastel/gradient AI palettes.
  - Deep navy/near-black surfaces (`--night`, `--ink`), concrete/steel grey structure.
  - Safety orange (`--amber`), alert red (`--red`), safety green (`--green`) as accents
    *only* for actual alerts and calls to action — never decoration.
  - No soft shadows, no glassmorphism, no blur, no gradient meshes.
- **Shape & structure** — sharp or near-sharp corners, visible borders/rules like a
  printed form or control panel; clear grid divisions, not floating cards.
  - The emergency action (find nearest center / call for help) must *visually dominate*
    every screen it appears on.
- **Motion** — minimal. Keep only functional indicators (pulsing LIVE dot, quake
  pulse, skeleton loading). No spring/fade/hover choreography.
- **Copy** — direct, short, imperative. Emergencies and signage, not chat.
  No emoji, no "You're all set!", no pill badges that chat at the user.
- **Density & speed** — bias toward density and big obvious tap targets over whitespace.

## Implementation (mapped to the checks below)

1. Font stack: Oswald / Archivo Narrow / IBM Plex Mono (removed Inter + system-ui).
2. Color: navy/steel/safety-orange/red tokens; accents only on alerts + CTAs.
3. Flatness: 2px radii, hard borders, no blur/backdrop-filter anywhere.
4. Motion: only status/alert motion; skeleton reduced.
5. Copy: imperative, dispatcher tone, no friendliness.
6. Primary action weight: `.btn-lg` emergency CTAs on home, directory, hotlines.
7. Dark mode: `prefers-color-scheme: dark` token overrides — low-light field use
   works by default (no toggle, no JS).

## Step 5 checklist (run before every commit)

- [ ] 2-second test: the one action is obvious on each screen.
- [ ] No AI/SaaS residue: font, spacing rhythm, shadows, pills, pastel gradients.
- [ ] Contrast holds in bright sun / reduced brightness / damaged screen.
- [ ] Copy reads like a dispatcher, not an assistant.
- [ ] Feels specific to this system — not a reskinned template.