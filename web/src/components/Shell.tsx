import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useData } from "../data";
import { day } from "../format";

function readTheme(): string | null {
  try {
    return localStorage.getItem("theme");
  } catch {
    return null;
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState<string | null>(readTheme);
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    try {
      if (theme) localStorage.setItem("theme", theme);
      else localStorage.removeItem("theme");
    } catch {
      /* private mode: theme just isn't remembered */
    }
  }, [theme]);
  const dark =
    theme === "dark" || (theme === null && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="rounded-md px-2 py-1 text-sm text-ink-2 hover:text-ink hover:bg-paper-2"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {dark ? "Light" : "Dark"}
    </button>
  );
}

const link = ({ isActive }: { isActive: boolean }) =>
  `px-1 py-1 text-sm font-semibold border-b-2 ${
    isActive ? "border-ink text-ink" : "border-transparent text-ink-2 hover:text-ink"
  }`;

export function Shell() {
  const { data } = useData();
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-rule">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 h-14 flex items-center gap-5">
          <NavLink to="/" className="flex items-center gap-2 font-extrabold tracking-tight mr-auto">
            <svg width="26" height="18" viewBox="0 0 26 18" aria-hidden="true">
              <rect width="26" height="18" rx="3" fill="var(--ink)" />
              <rect y="4" width="26" height="3" fill="var(--paper)" />
              <path d="M5 13h7" stroke="var(--series-2)" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <span>Card Spend Audit</span>
          </NavLink>
          <nav className="flex items-center gap-4" aria-label="Main">
            <NavLink to="/" end className={link}>
              Findings
            </NavLink>
            <NavLink to="/cases" className={link}>
              Case review
            </NavLink>
            <NavLink to="/method" className={link}>
              Method
            </NavLink>
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-rule mt-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 text-sm text-ink-2 grid gap-2 sm:grid-cols-2">
          <p>
            Data: State of Oklahoma purchase card transactions, published on data.ok.gov. Policy: OMES P-Card
            procedures and FAQ (74 O.S. § 85.5a). Cardholder names were dropped on load.
          </p>
          <p className="sm:text-right">
            {data ? `Numbers generated ${day(data.summary.generated)}. ` : ""}Built by Sagar Bhatia.
          </p>
        </div>
      </footer>
    </div>
  );
}

export function Section({ title, children, id }: { title: string; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="mx-auto max-w-6xl px-4 sm:px-6 mt-20">
      <h2 className="text-2xl sm:text-[1.75rem] font-bold tracking-tight leading-tight max-w-3xl">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function Loading({ error }: { error: string | null }) {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-24 text-ink-2">
      {error ? (
        <p role="alert">
          The data files didn't load ({error}). Run <code>uv run python -m spendaudit export</code>, then rebuild
          the site.
        </p>
      ) : (
        <p>Loading the audit…</p>
      )}
    </div>
  );
}
