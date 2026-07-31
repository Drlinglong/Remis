# Remis Design System

## Product context

Remis is a local-first desktop localization workspace. Its UI must make project
identity, task state, current evidence, the next safe action, and output location
easy to understand without exposing internal implementation details.

Remis is an application UI, not a collection of themed landing pages. Themes may
change materials, typography, decoration, and accent colors. They must not change
information hierarchy, workflow meaning, readability, or safety boundaries.

## Design direction

- **Aesthetic:** restrained, theme-aware workbench
- **Layout:** grid-disciplined and task-focused
- **Density:** compact but readable
- **Color:** one accent per screen; semantic colors only for status and risk
- **Motion:** minimal and functional
- **Primary rule:** the user's current object and next action must be identifiable
  in one scan

## Semantic surfaces

Every visible text container belongs to one material contract:

| Surface | Purpose | Typical examples |
| --- | --- | --- |
| `canvas` | Page background and orientation | Page title, transparent page copy |
| `surface` | Primary work area | Toolbars, task workspaces, decision panels |
| `paper` | Readable material inside a workspace | Evidence, reports, task summaries |
| `elevated` | Temporary content above the page | Drawers, modals, menus |

Components declare the material they occupy with `data-remis-surface`. They use
semantic tokens such as `--surface-text-main`; they do not branch on theme names.

Every theme must define:

- background, main text, muted text, and border for every surface;
- interactive accent and text on that accent;
- focus-ring, menu, success, warning, and error roles;
- token pairs that meet WCAG AA for normal text.

Raw theme colors belong in the theme token definitions. New feature components
must not introduce theme-specific hex, RGB, or RGBA text/background colors.

## Visual hierarchy

1. Each workspace has one strong visual anchor: the selected task, term, project,
   or document.
2. Each screen has one primary action. Secondary and dangerous-secondary actions
   must not compete with it.
3. Evidence and supporting explanation are quieter than the current object and
   action.
4. Borders and cards communicate grouping. They are not decoration to be applied
   to every element.
5. A theme may amplify the visual anchor, but must not give every panel equal glow,
   border weight, or saturation.

## Typography

- Page title: one line where practical; never consume the working viewport.
- Section title: names the area's job, not its implementation module.
- Body: readable at normal desktop scaling with a minimum 1.5 line height for
  paragraphs.
- Labels: use the current surface's main text.
- Descriptions and metadata: use the current surface's muted text.
- Technical identifiers and paths: use a monospace face, remain selectable, and
  wrap with `overflow-wrap: anywhere`.

## Spacing and layout

- Base spacing unit: 4 px.
- Primary rhythm: 8 / 12 / 16 / 24 / 32 px.
- Use `min-width: 0` on grid and flex children that contain user data.
- Long names and paths must have an explicit wrap or truncation policy.
- Truncated user data must expose the full value with a title, tooltip, or detail
  view.
- Responsive layouts preserve the action order and information hierarchy instead
  of merely stacking every panel.

## Scrolling

- Each pane has one vertical scroll owner.
- Fixed orientation and action areas remain outside the scroll owner.
- Nested vertical scrolling requires a documented interaction need and a browser
  regression test.
- Page-level and pane-level scrolling must not compete.

## Interaction states

Every reusable component is reviewed in:

- default, hover, focus-visible, active, selected, and disabled states;
- loading, empty, success, warning, error, partial-failure, and blocked states;
- long Chinese and English content;
- long Windows paths and unbroken identifiers;
- all five supported product themes.

Paid, destructive, deploy, export, overwrite, and repair actions retain explicit
approval regardless of theme.

## Visual reliability gates

1. Token and WCAG contrast tests run in Vitest.
2. The visual contract fixture renders deterministic content without a backend.
3. Playwright captures all five themes in a real browser.
4. Browser tests reject console errors, horizontal overflow, escaped long paths,
   and duplicate scroll ownership in the fixture.
5. Approved screenshots are versioned. Intentional visual changes update them in
   a dedicated, reviewable commit.
6. Critical real pages are added to the browser matrix incrementally with stable,
   local fixtures; no paid model call is required.
7. Any new or changed page, component, modal, or menu must pass an actual
   readability check in all five supported themes before commit or completion:
   Byzantine, Victorian, Sci-Fi, WWII, and Medieval.
8. The semantic surface declaration must match the background material the
   component actually paints. Checking tokens or `data-remis-surface` alone is
   not evidence of material correctness.
9. jsdom tests and static contract checks may support the review, but do not
   count as five-theme visual acceptance.

### Running the browser gate

From `scripts/react-ui`:

```powershell
# One-time browser runtime setup on a new checkout
npx playwright install chromium

# Compare against the committed Windows desktop and compact baselines
npm run test:visual

# Only after reviewing an intentional design change
npm run test:visual:update
```

The fixture does not connect to the backend, load a project database, or call a
model. A baseline update is not proof that a change is correct; the updated
images must be reviewed before they are committed.

## Theme acceptance

A theme is complete only when:

- every semantic token is present;
- contrast tests pass;
- the visual fixture passes at desktop and compact widths;
- menus and overlays remain readable;
- layout, focus, disabled, error, and empty states are visually verified;
- the theme preserves the same workflow hierarchy as every other theme.
- Any new or changed page, component, modal, or menu has been visually checked
  for actual readability in Byzantine, Victorian, Sci-Fi, WWII, and Medieval
  before commit or completion.
- White text on a white background, light text on a light background, black
  text on a black background, and dark text on a dark background are prohibited.
- The rendered background material matches the component's declared semantic
  surface; token presence or a `data-remis-surface` attribute alone is not
  sufficient.
- Completion reports for page changes list evidence for each of the five theme
  checks. If any theme cannot be verified, the report must state the gap and
  must not claim the change is complete.
- jsdom and static contract checks are supporting evidence only and do not
  satisfy the five-theme visual acceptance gate.

## Decisions log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-07-26 | Adopt semantic surface and action contracts | Mixed light and dark materials cannot safely inherit one global theme text color |
| 2026-07-26 | Add deterministic five-theme browser fixtures | Real layout, overflow, and CSS cascade failures are not visible to jsdom tests |
| 2026-07-26 | Keep themes expressive but hierarchy invariant | Users should learn one Remis workflow rather than five different products |
| 2026-07-31 | Make five-theme rendered readability evidence a completion gate | Token presence, static contracts, and jsdom cannot prove the painted material or actual readability; page-change reports must expose every theme check and any verification gap |
