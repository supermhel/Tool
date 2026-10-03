import { Loader2, AlertCircle } from "lucide-react";

export const GRADE_COLOR = { A: "#34c47a", B: "#7ed957", C: "#f0a742", D: "#f07042", E: "#e05555" };
export const GRADE_BG = { A: "#34c47a18", B: "#7ed95718", C: "#f0a74218", D: "#f0704218", E: "#e0555518" };

export function gradeFor(score) {
  return score >= 85 ? "A" : score >= 70 ? "B" : score >= 55 ? "C" : score >= 40 ? "D" : "E";
}

export function GradeBadge({ grade, score, title, size = 56 }) {
  const color = GRADE_COLOR[grade] || "#4f7eff";
  return (
    <div className="shrink-0 grid place-items-center rounded-2xl"
         style={{ width: size, height: size, background: GRADE_BG[grade] || "#4f7eff18", border: `1px solid ${color}44` }}
         title={title}>
      <div className="text-center leading-none">
        <div className="font-black" style={{ color, fontSize: size * 0.43 }}>{grade}</div>
        {score !== undefined && <div className="font-semibold mt-0.5 tabular-nums" style={{ color, fontSize: 11 }}>{score}</div>}
      </div>
    </div>
  );
}

export function Btn({ variant, size, busy, icon: Icon, children, className = "", ...props }) {
  const cls = ["btn", variant === "primary" && "btn-primary", variant === "danger" && "btn-danger",
    size === "sm" && "btn-sm", className].filter(Boolean).join(" ");
  return (
    <button type="button" className={cls} disabled={busy || props.disabled} {...props}>
      {busy ? <Loader2 size={14} className="animate-spin" /> : Icon && <Icon size={14} />}
      {children}
    </button>
  );
}

export function ErrorNote({ children }) {
  if (!children) return null;
  return (
    <p role="alert" className="flex items-start gap-1.5 text-xs text-bad mt-2">
      <AlertCircle size={13} className="mt-0.5 shrink-0" />{children}
    </p>
  );
}

export function Empty({ icon: Icon, title, children }) {
  return (
    <div className="rounded-2xl border border-dashed border-line p-8 text-center">
      {Icon && <Icon size={26} className="text-faint mx-auto mb-2" />}
      <p className="text-sm font-semibold text-muted">{title}</p>
      {children && <p className="text-sm text-faint mt-1 max-w-md mx-auto">{children}</p>}
    </div>
  );
}

export function Field({ label, hint, htmlFor, children }) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <p className="hint mt-1">{hint}</p>}
    </div>
  );
}

export function Skeleton({ className = "h-16" }) {
  return <div className={`rounded-2xl bg-panel border border-line animate-pulse ${className}`} />;
}

export function SectionTitle({ children, aside }) {
  return (
    <div className="flex items-center justify-between mb-3 gap-3">
      <h2 className="font-semibold text-sm text-muted uppercase tracking-wider">{children}</h2>
      {aside}
    </div>
  );
}
