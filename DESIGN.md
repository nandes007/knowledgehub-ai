# Design

<!-- impeccable:design-schema 1 -->

## World

**The Vault.** KnowledgeHub AI is presented as a company's private vault: documents are assets deposited and catalogued, a question is a request at the teller window, and every answer returns as a stamped receipt naming exactly which holdings back it. Turnover-proofing is literal: the vault outlives the teller.

Mode: **Operate**. Expression never outranks task, state, or a familiar affordance. The metaphor lives in accents — stamps, serials, ruled lines, one seal mark — never in relabeling core actions (buttons keep their plain verbs: Send, Upload, Delete, Log in).

## Color

Strategy: **Restrained** (neutrals plus one committed accent). Scene: an office employee at a laptop through the workday, reading dense text repeatedly — content surfaces stay light or reads worse across a full day. Structural chrome (shell, nav) is dark, like a vault's interior; content (the ledger, the receipt) is paper-toned.

| Role | Token | Value | Use |
|---|---|---|---|
| Paper | `--paper` | `#F6F1E4` | content surface (cards, page background) |
| Paper raised | `--paper-raised` | `#FBF8F0` | inputs, elevated panels |
| Ink | `--ink` | `#241F1A` | primary text on paper |
| Ink muted | `--ink-muted` | `#6B5F4F` | secondary text on paper |
| Ledger (dark ground) | `--ledger` | `#16332B` | shell, nav, footer, dark chrome |
| Ledger ink | `--ledger-ink` | `#EFE7D4` | text on ledger ground |
| Ledger ink muted | `--ledger-ink-muted` | `#A9B8AE` | secondary text on ledger ground (tinted, never gray) |
| Brass | `--brass` | `#B8863E` | primary actions, active nav, focus, the seal |
| Brass strong | `--brass-strong` | `#8F6526` | brass text/icons needing more contrast |
| Rule | `--rule` | `rgba(36,31,26,0.14)` | hairlines on paper |
| Rule on dark | `--rule-dark` | `rgba(239,231,212,0.16)` | hairlines on ledger ground |
| Void, on dark | `--stamp-void-on-dark` | `#E8927A` | error/void text on the ledger ground — `--stamp-void` itself is tuned for paper and fails contrast there |
| Stamp ready | `--stamp-ready` | `#2F6B4F` | "FILED"/ready status |
| Stamp pending | `--stamp-pending` | `#7D5422` | "PROCESSING" status (darkened from an initial `#A97634`, which measured 3.12:1 against its badge background — below the 4.5:1 floor) |
| Stamp void | `--stamp-void` | `#A6402F` | "VOID"/failed status, destructive actions, errors |

Dark mode is not a literal color-inversion of this system: the ledger/paper split already supplies the dark-surface need (nav, shell) without an OS-level dark theme. No separate dark palette is defined for v1.

## Type

Single family (IBM Plex) carrying three optical roles — a systemic choice, not a decorative pairing:

- **IBM Plex Serif** — headings, the wordmark, page titles. Ledger-book gravity.
- **IBM Plex Sans** — body copy, labels, buttons, nav, everything a user reads to act.
- **IBM Plex Mono** — citation serials, stamp codes, timestamps, document metadata, chunk counts. Reserved for real reference numbers and data, never decoration.

Tracking floor -0.04em on display sizes. Mono labels are the one earned tracking exception — a stamp's die-cut lettering is tracked in life: status stamps (Filed/Processing/Void) use +0.08em, citation tabs use +0.04em (a smaller badge reads better slightly tighter).

## Components

- **Button** — primary: brass fill, ink text, no gradient; secondary: ink outline on paper; ghost: text-only, used for low-emphasis actions (logout, cancel).
- **Card / Panel** — paper-raised surface, 1px `--rule` border, soft offset shadow (never a zero-offset glow). No nested cards.
- **Input** — paper-raised surface, bottom-weighted rule instead of a full box border (a ledger form-field feel), brass focus ring.
- **StatusStamp** — rectangular badge, mono uppercase, tracked, double-ruled border, colored by status role (ready/pending/void). Never rotated in data-table context (scanability first); the one place a stamp gets a physical "landing" motion is the chat citation moment below.
- **CitationTab** — small tab-shaped chip in mono type; expands (existing `<details>` pattern kept) to the chunk preview. Shows the source filename — the API's `Source` type has no separate serial/reference number to display, and inventing one would be exactly the kind of fabricated specificity the product must not show. Revisit if the backend ever adds a real per-citation reference.
- **SealMark** — a simple circular brass seal with a monogram, used as the wordmark anchor on auth screens and the sidebar header, and as the browser favicon (`app/icon.svg`, same mark as a static SVG since favicons render outside the page's component tree). The only illustrative asset in v1; not a full logo system.
- **Message bubbles** — the assistant's answer is a paper receipt (paper-raised, ruled, shadowed), per the Color table above. The user's own message intentionally breaks the paper/ledger split and uses the dark ledger tone instead — read as "your request going into the vault," and the clearest way to separate the two speakers at a glance. This is a deliberate exception, not a slip.

## Motion

One authored moment: when a streamed answer completes, its citation tabs "stamp" in — a quick scale/opacity settle timed like an ink stamp landing, exponential ease-out, ~180ms, staggered slightly per tab. `prefers-reduced-motion` cuts straight to the settled state. No other scripted entrance animation exists; hover/focus/disabled use ordinary instant or 120ms transitions.

## What this is not

No dark mode variant yet (see Color). No landing/marketing page (out of scope, tracked separately). No literal skeuomorphic textures (leather grain, embossed paper) — the vault reads through color, rule lines, stamps, and one seal mark, not through texture images.
