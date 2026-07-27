import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes } from "react";
import type { DocumentStatus } from "@/lib/api";

// Shared primitives for the Vault design system (see DESIGN.md). Kept as one
// small file, not a component library — four screens reuse these directly.

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-brass text-ink hover:bg-brass-strong hover:text-paper",
  secondary: "border border-ink/25 text-ink hover:bg-ink/5",
  ghost: "text-ink-muted hover:bg-ink/5 hover:text-ink",
  danger: "text-stamp-void hover:underline",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-sm px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass focus-visible:ring-offset-2 focus-visible:ring-offset-paper disabled:pointer-events-none disabled:opacity-50 ${BUTTON_STYLES[variant]} ${className}`}
    />
  );
}

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      className={`rounded-sm border border-rule bg-paper-raised shadow-[0_2px_8px_-2px_rgba(36,31,26,0.14)] ${className}`}
    />
  );
}

export function Label({ className = "", ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`text-sm font-medium text-ink-muted ${className}`} />;
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-t-sm border-0 border-b-2 border-rule bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-brass focus:outline-none disabled:opacity-50 ${className}`}
    />
  );
}

const STAMP_ROLE: Record<DocumentStatus, "ready" | "pending" | "void"> = {
  ready: "ready",
  processing: "pending",
  failed: "void",
};

const STAMP_LABEL: Record<DocumentStatus, string> = {
  ready: "Filed",
  processing: "Processing",
  failed: "Void",
};

const STAMP_STYLES: Record<"ready" | "pending" | "void", string> = {
  ready: "border-stamp-ready text-stamp-ready bg-stamp-ready-bg",
  pending: "border-stamp-pending text-stamp-pending bg-stamp-pending-bg",
  void: "border-stamp-void text-stamp-void bg-stamp-void-bg",
};

export function StatusStamp({ status }: { status: DocumentStatus }) {
  const role = STAMP_ROLE[status];
  return (
    <span
      className={`inline-flex items-center rounded-[2px] border-2 px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.08em] ${STAMP_STYLES[role]}`}
    >
      {STAMP_LABEL[status]}
    </span>
  );
}

export function SealMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeWidth="2" />
      <circle cx="24" cy="24" r="16.5" fill="none" stroke="currentColor" strokeWidth="1" />
      <text
        x="24"
        y="29.5"
        textAnchor="middle"
        className="font-serif"
        fontSize="15"
        fontWeight="600"
        fill="currentColor"
      >
        KH
      </text>
    </svg>
  );
}
