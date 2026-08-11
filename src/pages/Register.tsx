import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "@/hooks/useAuth";

function AegisLogo() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
      <path d="M14 2L4 6.5V13.5C4 19.2 8.4 24.5 14 26C19.6 24.5 24 19.2 24 13.5V6.5L14 2Z" fill="currentColor" fillOpacity="0.12" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx="14" cy="14" r="3" fill="currentColor" />
      <circle cx="9" cy="11" r="1.5" fill="currentColor" fillOpacity="0.6" />
      <circle cx="19" cy="11" r="1.5" fill="currentColor" fillOpacity="0.6" />
      <circle cx="14" cy="19" r="1.5" fill="currentColor" fillOpacity="0.6" />
      <line x1="14" y1="14" x2="9" y2="11" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4" />
      <line x1="14" y1="14" x2="19" y2="11" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4" />
      <line x1="14" y1="14" x2="14" y2="19" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4" />
    </svg>
  );
}

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '', terms: false });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'Full name is required';
    if (!form.email) e.email = 'Work email is required';
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Enter a valid email address';
    if (!form.password || form.password.length < 8) e.password = 'Password must be at least 8 characters';
    if (form.password !== form.confirm) e.confirm = 'Passwords do not match';
    if (!form.terms) e.terms = 'You must accept the terms to continue';
    return e;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setLoading(true);
    try {
      await register({
        name: form.name.trim(),
        email: form.email,
        password: form.password,
      });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setErrors({
        email: err instanceof Error ? err.message : "Registration failed",
      });
    } finally {
      setLoading(false);
    }
  };

  const strength = (() => {
    if (!form.password) return 0;
    let s = 0;
    if (form.password.length >= 8) s++;
    if (/[A-Z]/.test(form.password)) s++;
    if (/[0-9]/.test(form.password)) s++;
    if (/[^A-Za-z0-9]/.test(form.password)) s++;
    return s;
  })();

  const strengthLabel = ['', 'Weak', 'Fair', 'Good', 'Strong'];
  const strengthColor = ['', 'bg-red-400', 'bg-amber-400', 'bg-blue-400', 'bg-green-500'];

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--background)] p-6">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-8 text-[var(--primary)]">
          <AegisLogo />
          <span className="text-sm font-semibold text-[var(--foreground)]">Aegis Swarm</span>
        </div>

        <h1 className="text-xl font-semibold text-[var(--foreground)] mb-1">Create account</h1>
        <p className="text-sm text-[var(--muted-foreground)] mb-7">Set up your investigator account to get started.</p>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Full name</label>
            <input
              type="text"
              autoComplete="name"
              placeholder="Alex Johnson"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={`w-full px-3 py-2.5 text-sm bg-[var(--card)] border rounded-[var(--radius)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] ${errors.name ? 'border-red-400' : 'border-[var(--border)]'}`}
            />
            {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Work email</label>
            <input
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className={`w-full px-3 py-2.5 text-sm bg-[var(--card)] border rounded-[var(--radius)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] ${errors.email ? 'border-red-400' : 'border-[var(--border)]'}`}
            />
            {errors.email && <p className="text-xs text-red-500 mt-1">{errors.email}</p>}
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Password</label>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className={`w-full px-3 py-2.5 text-sm bg-[var(--card)] border rounded-[var(--radius)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] ${errors.password ? 'border-red-400' : 'border-[var(--border)]'}`}
            />
            {form.password && (
              <div className="mt-1.5 flex items-center gap-2">
                <div className="flex gap-1 flex-1">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= strength ? strengthColor[strength] : 'bg-[var(--border)]'}`} />
                  ))}
                </div>
                <span className="text-[10px] text-[var(--muted-foreground)]">{strengthLabel[strength]}</span>
              </div>
            )}
            {errors.password && <p className="text-xs text-red-500 mt-1">{errors.password}</p>}
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Confirm password</label>
            <input
              type="password"
              autoComplete="new-password"
              placeholder="Repeat your password"
              value={form.confirm}
              onChange={(e) => setForm({ ...form, confirm: e.target.value })}
              className={`w-full px-3 py-2.5 text-sm bg-[var(--card)] border rounded-[var(--radius)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] ${errors.confirm ? 'border-red-400' : 'border-[var(--border)]'}`}
            />
            {errors.confirm && <p className="text-xs text-red-500 mt-1">{errors.confirm}</p>}
          </div>

          <div>
            <div className="flex items-start gap-2">
              <input
                id="terms"
                type="checkbox"
                checked={form.terms}
                onChange={(e) => setForm({ ...form, terms: e.target.checked })}
                className="w-3.5 h-3.5 mt-0.5 rounded accent-[var(--primary)] flex-shrink-0"
              />
              <label htmlFor="terms" className="text-xs text-[var(--muted-foreground)] cursor-pointer leading-relaxed">
                I agree to the{' '}
                <button type="button" className="text-[var(--primary)] hover:underline">Terms of Service</button>{' '}
                and{' '}
                <button type="button" className="text-[var(--primary)] hover:underline">Privacy Policy</button>
              </label>
            </div>
            {errors.terms && <p className="text-xs text-red-500 mt-1">{errors.terms}</p>}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-[var(--primary)] text-white text-sm font-semibold rounded-[var(--radius)] hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed mt-1"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="text-xs text-[var(--muted-foreground)] text-center mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-[var(--primary)] hover:underline font-medium">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
