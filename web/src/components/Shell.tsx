import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCore } from "../data";
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

export const REPO = "https://github.com/Sag-Bhatia/card-spend-audit";
const TITLES: Record<string, string> = { "": "Findings", cases: "Case review", method: "Method" };

const link = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-11 items-center whitespace-nowrap px-1 text-sm font-semibold border-b-2 ${
    isActive ? "border-ink text-ink font-extrabold" : "border-transparent text-ink-2 hover:text-ink"
  }`;

export function Shell({ children }: { children?: ReactNode }) {
  const { data } = useCore();
  // A new page starts at its top; moving between cases inside Case review handles its own scroll.
  const path = useLocation().pathname;
  const section = path.split("/")[1];
  useEffect(() => window.scrollTo(0, 0), [section]);
  useEffect(() => {
    const id = section === "cases" ? path.split("/")[2] : undefined;
    document.title = `${id ? `Case ${id}` : (TITLES[section] ?? "No such page")} · Card Spend Audit`;
  }, [path, section]);
  return (
    <div className="min-h-screen flex flex-col">
      <a
        href="#main"
        onClick={(e) => {
          e.preventDefault(); // hash routing: don't navigate, just move focus
          document.getElementById("main")?.focus();
        }}
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:bg-paper focus:px-3 focus:py-2 focus:font-semibold"
      >
        Skip to content
      </a>
      <header className="border-b-2 border-ink">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 sm:h-16 flex flex-wrap items-center gap-x-3 sm:gap-x-5">
          <NavLink to="/" aria-label="Card Spend Audit" className="heading flex min-h-11 min-w-11 items-center gap-2 mr-auto">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <rect width="16" height="16" fill="var(--series-2)" />
            </svg>
            <span>Card Spend Audit</span>
          </NavLink>
          <nav className="order-last w-full sm:order-none sm:w-auto flex flex-wrap items-center gap-x-4" aria-label="Main">
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
      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        {children ?? <Outlet />}
      </main>
      <footer className="border-t-2 border-ink mt-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 text-sm text-ink-2 grid gap-2 sm:grid-cols-2">
          <p>
            Data: State of Oklahoma purchase card transactions, published on{" "}
            <a href="https://data.ok.gov" className="underline underline-offset-4 hover:text-ink">
              data.ok.gov
            </a>
            . Policy: OMES P-Card procedures and FAQ (74 O.S. § 85.5a). Cardholder names were replaced with salted
            hashes on load and never stored.
          </p>
          <p className="sm:text-right">
            {data ? `Numbers generated ${day(data.summary.generated)}. ` : ""}Built by{" "}
            <a href="https://github.com/Sag-Bhatia" className="underline underline-offset-4 hover:text-ink">
              Sagar Bhatia
            </a>
            .{" "}
            <a href={REPO} className="font-semibold text-ink underline decoration-2 underline-offset-4 hover:decoration-s2">
              Code and data pipeline on GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}

/** A numbered report section: the number hangs in column 1 and the section is set from column 2.
 *  On phones the number moves inline into the heading, so it never sits above it as a label. */
export function Section({ title, children, id, n }: { title: string; children: ReactNode; id?: string; n: number }) {
  return (
    <section id={id} className="mx-auto max-w-6xl px-4 sm:px-6 mt-20">
      <div className="border-t-2 border-ink pt-3 sm:grid sm:grid-cols-12 sm:gap-x-6">
        <p className="hidden sm:block pt-2 text-sm font-extrabold text-s2" aria-hidden="true">
          {n}
        </p>
        <div className="min-w-0 sm:col-span-11">
          <h2 className="heading text-[1.5rem] sm:text-[1.75rem]">
            <span className="sm:hidden mr-2 text-s2" aria-hidden="true">
              {n}
            </span>
            {title}
          </h2>
          <div className="mt-5">{children}</div>
        </div>
      </div>
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

/** Unknown routes and render errors: stay inside the report, say what happened, offer the way back. */
export function NotFound() {
  return (
    <Shell>
      <NoSuchPage />
    </Shell>
  );
}

export function NoSuchPage() {
  return (
      <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-10">
        <h1 className="heading text-[1.75rem] sm:text-[2rem] border-t-2 border-ink pt-3">No such page</h1>
        <p className="mt-3 text-ink-2 max-w-[62ch]">
          This link doesn't point to a page in the audit. It may be mistyped or from an older version of the site.
        </p>
        <p className="mt-4">
          <Link to="/" className="inline-flex min-h-11 items-center font-semibold underline decoration-2 underline-offset-4 hover:decoration-s2">
            Back to Findings
          </Link>
        </p>
      </div>
  );
}
