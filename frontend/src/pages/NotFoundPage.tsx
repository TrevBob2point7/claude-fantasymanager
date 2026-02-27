import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background">
      <h1 className="font-heading text-6xl font-bold text-accent">404</h1>
      <p className="mt-4 text-text-secondary">Page not found</p>
      <Link
        to="/"
        className="mt-6 rounded-md bg-accent px-4 py-2 font-semibold text-background hover:opacity-90"
      >
        Go Home
      </Link>
    </div>
  );
}
