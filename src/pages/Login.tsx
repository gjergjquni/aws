import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router";
import { useAuth } from "@/hooks/useAuth";
import LoadingState from "@/components/LoadingState";

function ShieldIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
      <path
        d="M14 2L4 6.5V13.5C4 19.2 8.4 24.5 14 26C19.6 24.5 24 19.2 24 13.5V6.5L14 2Z"
        fill="currentColor"
        fillOpacity="0.15"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="14" cy="13.5" r="3" fill="currentColor" />
      <circle cx="9.5" cy="10.5" r="1.5" fill="currentColor" fillOpacity="0.5" />
      <circle cx="18.5" cy="10.5" r="1.5" fill="currentColor" fillOpacity="0.5" />
      <circle cx="14" cy="18.5" r="1.5" fill="currentColor" fillOpacity="0.5" />
      <line x1="14" y1="13.5" x2="9.5" y2="10.5" stroke="currentColor" strokeWidth="1" strokeOpacity="0.35" />
      <line x1="14" y1="13.5" x2="18.5" y2="10.5" stroke="currentColor" strokeWidth="1" strokeOpacity="0.35" />
      <line x1="14" y1="13.5" x2="14" y2="18.5" stroke="currentColor" strokeWidth="1" strokeOpacity="0.35" />
    </svg>
  );
}

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, isLoading } = useAuth();
  const [form, setForm] = useState({ email: "", password: "", remember: false });
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate, from]);

  const validate = (field?: string) => {
    const e: Record<string, string> = {};
    if ((!field || field === "email") && touched.email) {
      if (!form.email) e.email = "Email is required";
      else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = "Enter a valid email address";
    }
    if ((!field || field === "password") && touched.password) {
      if (!form.password) e.password = "Password is required";
    }
    return e;
  };

  const handleBlur = (field: string) => {
    setTouched((t) => ({ ...t, [field]: true }));
    setErrors(validate(field));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ email: true, password: true });
    const allErrors: Record<string, string> = {};
    if (!form.email) allErrors.email = "Email is required";
    else if (!/\S+@\S+\.\S+/.test(form.email)) allErrors.email = "Enter a valid email address";
    if (!form.password) allErrors.password = "Password is required";
    setErrors(allErrors);
    if (Object.keys(allErrors).length > 0) return;

    setSubmitting(true);
    try {
      await login({
        email: form.email,
        password: form.password,
        remember: form.remember,
      });
      navigate(from, { replace: true });
    } catch (err) {
      setErrors({
        password: err instanceof Error ? err.message : "Sign in failed",
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) {
    return <LoadingState fullScreen label="Checking session…" />;
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[var(--background)] px-4 py-12">
      <div className="w-full max-w-[420px]">
        <div className="flex flex-col items-center mb-8">
          <div className="text-[var(--primary)] mb-3">
            <ShieldIcon />
          </div>
          <h1 className="text-base font-semibold tracking-tight text-[var(--foreground)]">Aegis Swarm</h1>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">AI-powered return fraud investigation</p>
        </div>

        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-sm px-8 py-8">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-[var(--foreground)]">Welcome back</h2>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">Sign in to continue your investigations.</p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-[var(--foreground)] mb-1.5">
                Work email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                autoFocus
                placeholder="investigator@company.com"
                value={form.email}
                onChange={(e) => {
                  setForm({ ...form, email: e.target.value });
                  if (touched.email) setErrors((prev) => ({ ...prev, email: "" }));
                }}
                onBlur={() => handleBlur("email")}
                className={`w-full px-3.5 py-2.5 text-sm rounded-lg border bg-[var(--card)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none transition-shadow focus:ring-2 focus:ring-[var(--ring)] ${
                  errors.email ? "border-red-400 dark:border-red-600" : "border-[var(--border)]"
                }`}
              />
              {errors.email && <p className="text-xs text-red-500 mt-1.5">{errors.email}</p>}
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="password" className="text-xs font-medium text-[var(--foreground)]">
                  Password
                </label>
                <button type="button" className="text-xs text-[var(--primary)] hover:underline">
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••••"
                  value={form.password}
                  onChange={(e) => {
                    setForm({ ...form, password: e.target.value });
                    if (touched.password) setErrors((prev) => ({ ...prev, password: "" }));
                  }}
                  onBlur={() => handleBlur("password")}
                  className={`w-full px-3.5 py-2.5 pr-10 text-sm rounded-lg border bg-[var(--card)] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:ring-2 focus:ring-[var(--ring)] ${
                    errors.password ? "border-red-400 dark:border-red-600" : "border-[var(--border)]"
                  }`}
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              {errors.password && <p className="text-xs text-red-500 mt-1.5">{errors.password}</p>}
            </div>

            <div className="flex items-center gap-2 pt-0.5">
              <input
                id="remember"
                type="checkbox"
                checked={form.remember}
                onChange={(e) => setForm({ ...form, remember: e.target.checked })}
                className="w-3.5 h-3.5 rounded accent-[var(--primary)] cursor-pointer"
              />
              <label htmlFor="remember" className="text-xs text-[var(--muted-foreground)] cursor-pointer">
                Remember me for 30 days
              </label>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full mt-2 py-2.5 bg-[var(--primary)] text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-all disabled:opacity-60"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-[var(--muted-foreground)] mt-5">
          Don&apos;t have an account?{" "}
          <Link to="/register" className="text-[var(--foreground)] font-medium hover:text-[var(--primary)]">
            Create account
          </Link>
        </p>
      </div>
    </div>
  );
}
