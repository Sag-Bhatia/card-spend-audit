import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
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
  // Follow a live OS theme change while no choice is saved, so the button never shows a stale state.
  const [osDark, setOsDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const on = (e: MediaQueryListEvent) => setOsDark(e.matches);
    mq?.addEventListener?.("change", on);
    return () => mq?.removeEventListener?.("change", on);
  }, []);
  const dark = theme === "dark" || (theme === null && osDark);
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="size-11 text-ink-2 hover:text-ink"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {dark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  );
}

const link = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-11 items-center whitespace-nowrap px-1 text-sm font-semibold border-b-2 ${
    isActive ? "border-ink text-ink" : "border-transparent text-ink-2 hover:text-ink"
  }`;

export function Shell() {
  const { data } = useData();
  // A new page starts at its top; moving between cases inside Case review handles its own scroll.
  const section = useLocation().pathname.split("/")[1];
  useEffect(() => window.scrollTo(0, 0), [section]);
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-rule">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 h-16 flex items-center gap-3 sm:gap-5">
          <NavLink to="/" aria-label="Card Spend Audit" className="heading flex min-h-11 min-w-11 items-center gap-2 mr-auto">
            <svg width="26" height="18" viewBox="0 0 26 18" aria-hidden="true">
              <rect width="26" height="18" rx="3" fill="var(--ink)" />
              <rect y="4" width="26" height="3" fill="var(--paper)" />
              <path d="M5 13h7" stroke="var(--series-2)" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <span className="hidden sm:inline">Card Spend Audit</span>
          </NavLink>
          <nav className="flex items-center gap-3 sm:gap-4" aria-label="Main">
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
            procedures and FAQ (74 O.S. § 85.5a). Cardholder names were replaced with salted hashes on load and never stored.
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
      <h2 className="heading text-[1.5rem] sm:text-[1.75rem] max-w-3xl">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function Loading({ error }: { error: string | null }) {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-24 text-ink-2">
      {error ? (
        <p role="alert">
          The audit data didn't load ({error}). Reload the page; if it keeps failing, this copy of the site is missing
          its data files.
        </p>
      ) : (
        <p>Loading the audit…</p>
      )}
    </div>
  );
}
