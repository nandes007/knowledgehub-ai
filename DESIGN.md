# Design

<!-- impeccable:design-schema 1 -->

## World

**The Vault.** KnowledgeHub AI is presented as a company's private vault: documents are assets deposited and catalogued, a question is a request at the teller window, and every answer returns as a stamped receipt naming exactly which holdings back it. Turnover-proofing is literal: the vault outlives the teller.

The interface uses a modern dark-mode palette with warm charcoal surfaces and polished gold accents.

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
| User bubble | `--user-bubble` | `#2A2520` | user message background — warm dark brown pill |
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

- **Inter** (`--font-inter`, `--font-sans`) — body copy, headings, labels, buttons, navigation, the wordmark. The modern SaaS standard: clean, highly legible at all sizes, excellent rendering across platforms. Headings use Inter semibold with no serifs.
- **JetBrains Mono** (`--font-jetbrains`, `--font-mono`) — citation tabs, timestamps, document metadata, file extension icons, code blocks, status pills. Reserved for real reference numbers and data, never decoration.

Font loading uses `next/font/google` with CSS variables `--font-inter` and `--font-jetbrains`.

## Components

- **Button** — primary: gold fill (`--gold`), dark text (`--surface-primary`), no gradient; secondary: border-only (`--border`) on dark; ghost: text-secondary, used for low-emphasis actions (logout, cancel, delete); danger: status-void text (`--status-void`). All buttons include gold focus-visible ring, disabled opacity (50%), and 120ms hover transitions.
- **Card / Panel** — surface-raised background (`--surface-raised`), 1px border at 8% opacity (`--border`), deep shadow (`0 2px 12px -4px rgba(0,0,0,0.5)`). Rounded-xl (12px) for modern feel. No nested cards.
- **Input** — surface-input background (`--surface-input`), full-border rounded-lg (`--border`), gold focus ring and border (`--gold`), taller (h-10) height.
- **Label** — text-secondary color (`--text-secondary`), Inter font-medium.
- **StatusStamp / StatusPill** — rounded-full pill shape, colored background-tint (`--status-*-bg`) + colored text (`--status-*`), uppercase JetBrains Mono, letter-spaced (`0.08em`). No border.
- **Wordmark** — an Inter semibold span with a gold-colored "K" followed by "nowledgeHub" in text-primary. Supports `collapsed` prop rendering just gold "K". Used on auth screens and the sidebar header.
- **BarChart** — horizontal gold bars (`--gold`) on dark track (`--border`), text-secondary truncated labels, tabular numbers.
- **Message layout** — the assistant's answer renders as plain text directly on the surface (no card/bubble) with markdown formatting. The user's message is a right-aligned warm dark pill (`--user-bubble`), capped at 80% width. The "Thinking..." state is three animated dots pulsing in sequence.
- **CitationTab / SourceList** — rounded-full pill with gold-muted bg (`--gold-muted`) and gold text (`--gold`); expands to the chunk preview on surface-raised background (`--surface-raised`) with stamp-in animation.
- **Chat Layout & Input** — centered column layout (`max-w-3xl`), floating auto-resizing `<textarea>` measuring `scrollHeight` clamped to 5 rows, with a circular gold send button inside the input container.
- **Document List (DocumentTable)** — card-based document rows with extension-colored inline SVG icons (red for PDF, blue for DOCX, orange for PPTX, gray for MD), client-side search filter, hover-reveal ghost delete button, and JetBrains Mono timestamps.
- **Upload Dropzone (UploadDropzone)** — rounded-xl container with dashed border (`--border`), centered cloud-upload icon, drag-over highlight with gold border (`--gold`) and gold-muted background (`--gold-muted`), dark-styled visibility selector, and inline upload progress text (`Uploading file 1 of N...`).

## Sidebar

The sidebar supports two states controlled by an `isCollapsed` boolean:

- **Expanded**: 260px width, icon + text labels for all nav items, full conversation list.
- **Collapsed**: 56px width (icon strip), icons only with title-attribute tooltips, conversation list hidden.
- **Transition**: 200ms ease CSS transition on width.
- **Active conversation**: 3px gold left-border accent (`border-l-gold bg-gold-muted/50`) instead of background highlight.
- **Mobile**: slide-in overlay with backdrop-blur, unchanged behavior.

## Motion

- **Message entry**: 150ms fade-in with 4px upward translate (`@keyframes fade-in`).
- **Citation stamp-in**: 180ms scale/opacity settle (`@keyframes stamp-in`, exponential cubic-bezier(0.16, 1, 0.3, 1)).
- **Sidebar collapse/expand**: 200ms ease CSS transition on width.
- **Thinking dots**: 1.2s pulsing animation, staggered by 150ms per dot.
- **Button/nav hover**: 120ms `transition-colors`.
- `prefers-reduced-motion` collapses all animation/transition durations and delays to 1ms / static state.

## What this is not

No light mode variant. No OS-level dark mode toggle. No landing/marketing page (out of scope, tracked separately). No literal skeuomorphic textures — the vault reads through warm surfaces, gold accents, status pills, and one wordmark, not through texture images.
