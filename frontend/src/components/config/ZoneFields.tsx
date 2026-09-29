import type { ChangeEvent } from "react";
import type { ZoneDraft } from "./configHelpers";

interface Props {
  draft: ZoneDraft;
  onChange: (draft: ZoneDraft) => void;
  disabled?: boolean;
}

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none disabled:bg-slate-100";

export function ZoneFields({ draft, onChange, disabled = false }: Props) {
  const set = (field: keyof ZoneDraft) => (e: ChangeEvent<HTMLInputElement>) =>
    onChange({ ...draft, [field]: e.target.value });

  return (
    <div className="grid gap-3 sm:grid-cols-4">
      <label className="text-xs font-medium text-slate-600">
        Zone name
        <input className={inputClass} value={draft.name} onChange={set("name")} disabled={disabled} placeholder="e.g. North bed" />
      </label>
      <label className="text-xs font-medium text-slate-600">
        Moisture low (0–1)
        <input className={inputClass} type="number" step="0.01" min="0" max="1" value={draft.low} onChange={set("low")} disabled={disabled} />
      </label>
      <label className="text-xs font-medium text-slate-600">
        Moisture high (0–1)
        <input className={inputClass} type="number" step="0.01" min="0" max="1" value={draft.high} onChange={set("high")} disabled={disabled} />
      </label>
      <label className="text-xs font-medium text-slate-600">
        Watering time (optional)
        <input className={inputClass} type="time" value={draft.waterAt} onChange={set("waterAt")} disabled={disabled} />
      </label>
    </div>
  );
}