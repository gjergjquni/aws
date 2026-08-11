import { useState } from "react";
import { mvpAgents, roadmapAgents } from "@/data/agents";
import { useAuth } from "@/hooks/useAuth";
import { useTheme, type ThemePreference } from "@/hooks/useTheme";

function SectionCard({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border)]">
        <h3 className="text-sm font-semibold text-[var(--foreground)]">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: () => void; label?: string }) {
  return (
    <button role="switch" aria-checked={checked} aria-label={label} onClick={onChange} className={`w-9 h-5 rounded-full transition-colors flex-shrink-0 ${checked ? 'bg-[var(--primary)]' : 'bg-[var(--border)]'}`}>
      <span className={`block w-3.5 h-3.5 bg-white rounded-full shadow transition-transform m-0.5 ${checked ? 'translate-x-4' : 'translate-x-0'}`} />
    </button>
  );
}

function InputField({ label, type = 'text', placeholder, defaultValue }: { label: string; type?: string; placeholder?: string; defaultValue?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">{label}</label>
      <input
        type={type}
        placeholder={placeholder}
        defaultValue={defaultValue}
        className="w-full px-3 py-2.5 text-sm bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] transition-shadow"
      />
    </div>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const { preference, set } = useTheme();
  const [notifications, setNotifications] = useState({ highRisk: true, completed: true, reviewRequired: false });
  const [autoAssign, setAutoAssign] = useState(false);
  const [requireNotes, setRequireNotes] = useState(true);
  const [riskThreshold, setRiskThreshold] = useState("70");
  const initials = user?.initials ?? "IN";

  return (
    <div className="px-6 py-6 max-w-[800px] mx-auto">
      <div className="mb-7">
        <h2 className="text-xl font-semibold text-[var(--foreground)]">Settings</h2>
        <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Manage your account, appearance, notifications, and investigation preferences.</p>
      </div>

      <div className="space-y-5">
        {/* Account */}
        <SectionCard title="Account">
          <div className="flex items-center gap-4 mb-5 pb-5 border-b border-[var(--border)]">
            <div className="w-14 h-14 rounded-full bg-[var(--primary)] flex items-center justify-center text-white text-lg font-semibold flex-shrink-0">
              {initials}
            </div>
            <div>
              <div className="text-sm font-semibold text-[var(--foreground)]">{user?.name ?? "Investigator"}</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-0.5">Investigator</div>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <InputField label="Full name" defaultValue={user?.name ?? "Investigator"} />
            <InputField label="Work email" type="email" defaultValue={user?.email ?? ""} />
            <InputField label="Current password" type="password" placeholder="••••••••" />
            <InputField label="New password" type="password" placeholder="At least 8 characters" />
          </div>
          <div className="mt-4 flex justify-end">
            <button className="px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded-[var(--radius)] hover:opacity-90 transition-opacity">
              Save changes
            </button>
          </div>
        </SectionCard>

        {/* Appearance */}
        <SectionCard title="Appearance">
          <div className="grid grid-cols-3 gap-3">
            {(["light", "dark", "system"] as ThemePreference[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => set(t)}
                className={`p-3 rounded-[var(--radius)] border text-sm font-medium capitalize transition-all ${
                  preference === t
                    ? "border-[var(--primary)] bg-[var(--accent)] text-[var(--accent-foreground)]"
                    : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                }`}
              >
                <div className="flex flex-col items-center gap-1.5">
                  {t === 'light' && <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="4" stroke="currentColor" strokeWidth="1.3" /><line x1="9" y1="1.5" x2="9" y2="3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /><line x1="9" y1="15" x2="9" y2="16.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /><line x1="1.5" y1="9" x2="3" y2="9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /><line x1="15" y1="9" x2="16.5" y2="9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /></svg>}
                  {t === 'dark' && <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M15 10.5A7 7 0 017.5 3a7 7 0 100 12 7 7 0 007.5-4.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" /></svg>}
                  {t === 'system' && <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="3" width="14" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.3" /><line x1="6" y1="15" x2="12" y2="15" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /><line x1="9" y1="13" x2="9" y2="15" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /></svg>}
                  <span className="text-xs">{t}</span>
                </div>
              </button>
            ))}
          </div>
        </SectionCard>

        {/* Notifications */}
        <SectionCard title="Notifications">
          <div className="space-y-4">
            {[
              { key: 'highRisk' as const, label: 'High-risk alerts', desc: 'Alert when a new high-risk investigation is created' },
              { key: 'completed' as const, label: 'Investigation completed', desc: 'Notify when an investigation is resolved' },
              { key: 'reviewRequired' as const, label: 'Human review required', desc: 'Notify when an investigation is escalated for human review' },
            ].map((n) => (
              <div key={n.key} className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-[var(--foreground)]">{n.label}</div>
                  <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{n.desc}</div>
                </div>
                <Toggle checked={notifications[n.key]} onChange={() => setNotifications((p) => ({ ...p, [n.key]: !p[n.key] }))} label={n.label} />
              </div>
            ))}
          </div>
        </SectionCard>

        {/* Investigation Preferences */}
        <SectionCard title="Investigation Preferences">
          <div className="space-y-4 mb-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-medium text-[var(--foreground)]">Auto-assign investigations</div>
                <div className="text-xs text-[var(--muted-foreground)] mt-0.5">Automatically assign new investigations to available investigators</div>
              </div>
              <Toggle checked={autoAssign} onChange={() => setAutoAssign(!autoAssign)} label="Auto-assign" />
            </div>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-medium text-[var(--foreground)]">Require decision notes</div>
                <div className="text-xs text-[var(--muted-foreground)] mt-0.5">Investigators must add notes before saving a decision</div>
              </div>
              <Toggle checked={requireNotes} onChange={() => setRequireNotes(!requireNotes)} label="Require notes" />
            </div>
          </div>
          <div className="pt-4 border-t border-[var(--border)]">
            <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">
              High-risk threshold <span className="text-[var(--muted-foreground)] font-normal">(escalate automatically above this score)</span>
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range" min="50" max="95" step="5"
                value={riskThreshold}
                onChange={(e) => setRiskThreshold(e.target.value)}
                className="flex-1 accent-[var(--primary)]"
              />
              <span className="font-mono text-sm font-semibold text-[var(--foreground)] w-8 text-right">{riskThreshold}</span>
            </div>
          </div>
        </SectionCard>

        {/* AI Configuration */}
        <SectionCard title="AI Configuration">
          <div className="grid grid-cols-2 gap-4 mb-5 pb-5 border-b border-[var(--border)]">
            {[
              { label: 'Model', value: 'Amazon Nova Pro' },
              { label: 'Human-in-the-loop', value: 'Enabled' },
              { label: 'Agent weights', value: 'Equal (50/50)' },
              { label: 'PII removal', value: 'Automatic' },
            ].map((c) => (
              <div key={c.label}>
                <div className="text-xs text-[var(--muted-foreground)] mb-0.5">{c.label}</div>
                <div className="text-sm font-medium text-[var(--foreground)]">{c.value}</div>
              </div>
            ))}
          </div>

          <div className="mb-5">
            <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">Active Agents</div>
            <div className="space-y-2">
              {mvpAgents.map((a) => (
                <div key={a.id} className="flex items-start gap-3 p-3 bg-[var(--muted)] rounded-[var(--radius)]">
                  <span className="w-5 h-5 rounded-full bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400 flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px] font-bold">✓</span>
                  <div>
                    <div className="text-sm font-medium text-[var(--foreground)]">{a.name}</div>
                    <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{a.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">Roadmap</div>
            <div className="space-y-2">
              {roadmapAgents.map((a) => (
                <div key={a.id} className="flex items-start gap-3 p-3 border border-dashed border-[var(--border)] rounded-[var(--radius)] opacity-60">
                  <span className="w-5 h-5 rounded-full bg-[var(--border)] text-[var(--muted-foreground)] flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px]">○</span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--foreground)]">{a.name}</span>
                      <span className="text-[10px] font-medium text-[var(--muted-foreground)] bg-[var(--border)] px-1.5 py-0.5 rounded-full">Roadmap</span>
                    </div>
                    <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{a.description}</div>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-[var(--muted-foreground)] mt-3">
              Future agents are planned for a later release and are not yet implemented.
            </p>
          </div>
        </SectionCard>

        {/* Security & Privacy */}
        <SectionCard title="Security & Privacy">
          <div className="space-y-4">
            {[
              { label: 'PII protection', desc: 'Customer personal information is automatically removed before any AI processing.', active: true },
              { label: 'Audit logging', desc: 'All investigation events are recorded in an immutable audit trail.', active: true },
              { label: 'Human oversight', desc: 'AI recommendations are clearly separated from human final decisions. Investigators always make the final refund determination.', active: true },
            ].map((s) => (
              <div key={s.label} className="flex items-start gap-3 p-3 bg-[var(--muted)] rounded-[var(--radius)]">
                <span className="w-5 h-5 rounded-full bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400 flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px] font-bold">✓</span>
                <div>
                  <div className="text-sm font-medium text-[var(--foreground)]">{s.label}</div>
                  <div className="text-xs text-[var(--muted-foreground)] mt-0.5 leading-relaxed">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
