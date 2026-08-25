import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes } from "react";
import type { DocumentStatus } from "@/lib/api";

// Shared primitives for the dark-mode design system (see DESIGN.md). Kept as one
// small file, not a component library — four screens reuse these directly.

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-gold text-surface-primary hover:bg-gold-hover",
  secondary: "border border-border text-text-primary hover:bg-border",
  ghost: "text-text-secondary hover:bg-border hover:text-text-primary",
  danger: "text-status-void hover:underline",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-120 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-primary disabled:pointer-events-none disabled:opacity-50 ${BUTTON_STYLES[variant]} ${className}`}
    />
  );
}

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      className={`rounded-xl border border-border bg-surface-raised shadow-[0_2px_12px_-4px_rgba(0,0,0,0.5)] ${className}`}
    />
  );
}

export function Label({ className = "", ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`text-sm font-medium text-text-secondary ${className}`} />;
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-10 w-full rounded-lg border border-border bg-surface-input px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold disabled:opacity-50 ${className}`}
    />
  );
}

const STATUS_LABEL: Record<DocumentStatus, string> = {
  ready: "Filed",
  processing: "Processing",
  failed: "Void",
};

const STATUS_STYLES: Record<DocumentStatus, string> = {
  ready: "text-status-ready bg-status-ready-bg",
  processing: "text-status-pending bg-status-pending-bg",
  failed: "text-status-void bg-status-void-bg",
};

export function StatusStamp({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.08em] ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

export const StatusPill = StatusStamp;

// ponytail: horizontal CSS bars instead of a charting dependency — three
// series of one number per label is all the admin dashboard plots. Reach for a
// real chart lib when it needs axes, tooltips, or more than one series.
export function BarChart({
  data,
  formatValue = (value: number) => String(value),
  emptyMessage = "No data yet.",
}: {
  data: { label: string; value: number }[];
  formatValue?: (value: number) => string;
  emptyMessage?: string;
}) {
  if (data.length === 0) return <p className="text-sm text-text-secondary">{emptyMessage}</p>;

  const max = Math.max(...data.map((point) => point.value));

  return (
    <ul className="space-y-1.5">
      {data.map((point) => (
        <li key={point.label} className="flex items-center gap-3 text-sm">
          <span className="w-40 shrink-0 truncate font-mono text-xs text-text-secondary" title={point.label}>
            {point.label}
          </span>
          <span className="h-3 flex-1 rounded-full bg-border" aria-hidden="true">
            <span
              className="block h-full rounded-full bg-gold"
              style={{ width: max > 0 ? `${(point.value / max) * 100}%` : "0%" }}
            />
          </span>
          <span className="w-20 shrink-0 text-right tabular-nums text-text-primary">{formatValue(point.value)}</span>
        </li>
      ))}
    </ul>
  );
}

export function Wordmark({ collapsed = false, className = "" }: { collapsed?: boolean; className?: string }) {
  return (
    <span className={`font-sans text-sm font-semibold text-text-primary ${className}`}>
      <span className="text-gold">K</span>
      {!collapsed && "nowledgeHub"}
    </span>
  );
}

export type ToastVariant = "success" | "error" | "info";

const TOAST_STYLES: Record<ToastVariant, string> = {
  success: "border-status-ready/30 bg-surface-overlay text-status-ready",
  error: "border-status-void/30 bg-surface-overlay text-status-void",
  info: "border-gold/30 bg-surface-overlay text-gold",
};

export function Toast({
  message,
  variant = "success",
  onDismiss,
  duration = 3000,
}: {
  message: string | null;
  variant?: ToastVariant;
  onDismiss?: () => void;
  duration?: number;
}) {
  if (!message) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-lg border px-4 py-2.5 text-sm shadow-lg backdrop-blur-md transition-all duration-200 ${TOAST_STYLES[variant]}`}
    >
      <span>{message}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="ml-2 text-text-tertiary hover:text-text-primary focus:outline-none"
          aria-label="Dismiss"
        >
          ✕
        </button>
      )}
    </div>
  );
}

