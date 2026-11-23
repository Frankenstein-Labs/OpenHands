/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import type { PropsWithChildren, ReactNode } from "react";
import { describeCortexError } from "#/api/cortex/cortex-api";

export function CortexCard({
  title,
  children,
  actions,
}: PropsWithChildren<{ title?: ReactNode; actions?: ReactNode }>) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title ? (
            <h2 className="text-sm font-semibold text-content">{title}</h2>
          ) : (
            <span />
          )}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function CortexState({
  isLoading,
  error,
  onRetry,
  isEmpty,
  emptyLabel,
  children,
}: PropsWithChildren<{
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  isEmpty?: boolean;
  emptyLabel?: string;
}>) {
  if (isLoading) {
    return <p className="text-sm text-tertiary-light">{"Loading..."}</p>;
  }
  if (error) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-danger">
          {"Error"}: {describeCortexError(error)}
        </p>
        {onRetry && (
          <button type="button" className="text-sm underline" onClick={onRetry}>
            {"Retry"}
          </button>
        )}
      </div>
    );
  }
  if (isEmpty) {
    return <p className="text-sm text-tertiary-light">{emptyLabel}</p>;
  }
  return <>{children}</>;
}

export function CortexInput(
  props: React.InputHTMLAttributes<HTMLInputElement>,
) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-content outline-none focus:border-primary ${props.className ?? ""}`}
    />
  );
}

export function CortexTextarea(
  props: React.TextareaHTMLAttributes<HTMLTextAreaElement>,
) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm text-content outline-none focus:border-primary ${props.className ?? ""}`}
    />
  );
}

export function CortexButton({
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  const styles =
    variant === "primary"
      ? "bg-primary text-white hover:opacity-90"
      : variant === "danger"
        ? "border border-danger text-danger hover:bg-danger/10"
        : "border border-border text-content hover:bg-surface-raised";
  return (
    <button
      {...props}
      className={`rounded-lg px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${props.className ?? ""}`}
    />
  );
}

export function CortexLabel({ children }: PropsWithChildren) {
  return (
    <span className="mb-1 block text-xs font-medium text-tertiary-light">
      {children}
    </span>
  );
}
