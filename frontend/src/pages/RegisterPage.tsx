import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function RegisterPage() {
  const { register, error, user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await register(email, password, displayName);
    } catch {
      // error is set in context
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <h1 className="mb-8 text-center font-heading text-3xl font-bold text-accent">
          Fantasy Manager
        </h1>
        <form
          onSubmit={handleSubmit}
          className="rounded-xl border border-border bg-surface p-6"
        >
          <h2 className="mb-6 font-heading text-xl font-semibold text-text-primary">
            Create Account
          </h2>

          {error && (
            <p className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <label className="mb-1 block text-sm text-text-secondary">
            Display Name
          </label>
          <input
            type="text"
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mb-4 w-full rounded-md border border-border bg-surface px-3 py-2 text-text-primary outline-none focus:ring-2 focus:ring-accent"
          />

          <label className="mb-1 block text-sm text-text-secondary">
            Email
          </label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mb-4 w-full rounded-md border border-border bg-surface px-3 py-2 text-text-primary outline-none focus:ring-2 focus:ring-accent"
          />

          <label className="mb-1 block text-sm text-text-secondary">
            Password
          </label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mb-6 w-full rounded-md border border-border bg-surface px-3 py-2 text-text-primary outline-none focus:ring-2 focus:ring-accent"
          />

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-accent px-4 py-2 font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Creating account…" : "Create Account"}
          </button>

          <p className="mt-4 text-center text-sm text-text-secondary">
            Already have an account?{" "}
            <Link to="/login" className="text-accent hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
