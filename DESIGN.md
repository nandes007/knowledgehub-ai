# Design

<!-- impeccable:design-schema 1 -->

## World

**The Vault.** KnowledgeHub AI is presented as a company's private vault: documents are assets deposited and catalogued, a question is a request at the teller window, and every answer returns as a stamped receipt naming exactly which holdings back it. Turnover-proofing is literal: the vault outlives the teller.

Mode: **Operate**. Expression never outranks task, state, or a familiar affordance. The metaphor lives in accents — status pills, gold highlights, one wordmark — never in relabeling core actions (buttons keep their plain verbs: Send, Upload, Delete, Log in).

## Color

Strategy: **Dark-first** with warm charcoal surfaces (never pure black) to reduce eye strain for extended reading. Structural chrome (shell, nav, content) all lives on the same dark surface hierarchy. Accent color is polished gold — the same vault continuity, luminous on dark surfaces.

| Role | Token | Value | Use |
|---|---|---|---|
| Surface primary | `--surface-primary` | `#0F0F11` | page background |
| Surface raised | `--surface-raised` | `#18181B` | cards, panels |
| Surface overlay | `--surface-overlay` | `#1E1E23` | sidebar, modals |
| Surface input | `--surface-input` | `#131316` | text inputs, textareas |
| Text primary | `--text-primary` | `#EDEDEF` | primary text (near-white) |
| Text secondary | `--text-secondary` | `#8B8B8E` | secondary text |
| Text tertiary | `--text-tertiary` | `#5A5A5D` | disabled, placeholder |
| Gold | `--gold` | `#D4A745` | primary actions, active nav, focus, wordmark |
| Gold hover | `--gold-hover` | `#E8BE5A` | hover state for gold accent |
| Gold muted | `--gold-muted` | `rgba(212,167,69,0.15)` | accent tint for backgrounds |
| Border | `--border` | `rgba(255,255,255,0.08)` | default hairlines |
| Border hover | `--border-hover` | `rgba(255,255,255,0.14)` | hover-state hairlines |
| User bubble | `--user-bubble` | `#2A2520` | user message background — warm dark brown, a deliberate break from surface colors, retaining "your request going into the vault" |
| Status ready | `--status-ready` | `#4ADE80` | "Filed" status foreground |
| Status ready bg | `--status-ready-bg` | `rgba(74,222,128,0.12)` | "Filed" badge background |
| Status pending | `--status-pending` | `#FBBF24` | "Processing" status foreground |
| Status pending bg | `--status-pending-bg` | `rgba(251,191,36,0.12)` | "Processing" badge background |
| Status void | `--status-void` | `#F87171` | "Void"/failed/destructive |
| Status void bg | `--status-void-bg` | `rgba(248,113,113,0.12)` | "Void" badge background |

Tailwind `@theme inline` maps `--gold` values to both `--color-gold-*` and backward-compatible `--color-accent-*` aliases.

No light mode. No OS-level dark mode toggle. The app is dark-first.

## Type

Two families serving distinct optical roles:

- **Inter** — body copy, headings, labels, buttons, navigation, the wordmark. The modern SaaS standard: clean, highly legible at all sizes, excellent rendering across platforms.
- **JetBrains Mono** — citation tabs, timestamps, document metadata, code blocks, status pills. Reserved for real reference numbers and data, never decoration.

Serif usage is eliminated entirely — headings use Inter semibold instead.

Font loading uses `next/font/google` with CSS variables `--font-inter` and `--font-jetbrains`.

## Components

- **Button** — primary: gold fill, dark text, no gradient; secondary: border-only on dark; ghost: text-secondary, used for low-emphasis actions (logout, cancel).
- **Card / Panel** — surface-raised background, 1px border at 8% opacity, deep shadow. Rounded-xl for modern feel. No nested cards.
- **Input** — surface-primary background, full-border rounded style, gold focus ring.
- **StatusPill** — rounded-full pill shape, colored background-tint + colored text, mono uppercase, tracked. No border.
- **CitationTab** — rounded-full pill with gold-muted bg and gold text; expands (existing `<details>` pattern kept) to the chunk preview on surface-raised background.
- **Wordmark** — an Inter semibold span with a gold-colored "K" followed by "nowledgeHub" in text-primary. Replaces the SealMark SVG seal. Used on auth screens and the sidebar header.
- **Message layout** — the assistant's answer renders as plain text directly on the surface (no card/bubble). The user's message is a right-aligned warm dark pill (`--user-bubble`), capped at 80% width. The "Thinking..." state is three animated dots pulsing in sequence.

## Sidebar

The sidebar supports two states controlled by an `isCollapsed` boolean:

- **Expanded**: 260px width, icon + text labels for all nav items, full conversation list.
- **Collapsed**: 56px width (icon strip), icons only with title-attribute tooltips, conversation list hidden.
- **Transition**: 200ms ease CSS transition on width.
- **Active conversation**: 3px gold left-border accent instead of background highlight.
- **Mobile**: slide-in overlay with backdrop-blur, unchanged behavior.

## Chat Input

The input area uses a floating `<textarea>` with auto-resize behavior:

- JavaScript `scrollHeight` measurement on input event, clamped to 5 rows.
- Circular gold send button inside the textarea container.
- Enter to send, Shift+Enter for newline.
- Container styled as a rounded card with subtle shadow.

## Motion

- **Message entry**: 150ms fade-in with 4px upward translate (`@keyframes fade-in`).
- **Citation stamp-in**: 180ms scale/opacity settle, exponential ease-out, staggered per tab.
- **Sidebar collapse/expand**: 200ms ease CSS transition on width.
- **Thinking dots**: 1.2s pulsing animation, staggered by 150ms per dot.
- **Button/nav hover**: 120ms `transition-colors`.
- `prefers-reduced-motion` collapses all to 1ms / static state.

## What this is not

No light mode variant. No landing/marketing page (out of scope, tracked separately). No literal skeuomorphic textures — the vault reads through warm surfaces, gold accents, status pills, and one wordmark, not through texture images.
