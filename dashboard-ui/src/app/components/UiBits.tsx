import { ReactNode } from "react";

export function NavItem({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button onClick={onClick} className={`nav-item ${active ? "nav-item-active" : ""}`}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

export function StepRow({ n, text }: { n: string; text: string }) {
  return (
    <div className="step-row">
      <span className="step-badge">{n}</span>
      <span className="text-sm">{text}</span>
    </div>
  );
}

export function InfoRow({ title, value }: { title: string; value: string }) {
  return (
    <div className="info-row">
      <span className="text-white/70">{title}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

export function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="metric">
      <p className="text-[11px] uppercase tracking-wide text-white/55">{title}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}
