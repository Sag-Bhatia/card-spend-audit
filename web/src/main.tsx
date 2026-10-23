import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import { Loading, NoSuchPage, NotFound, Shell } from "./components/Shell";
import { Story } from "./pages/Story";

// Findings is the landing page; the other two load when first visited.
const Cases = lazy(() => import("./pages/Cases").then((m) => ({ default: m.Cases })));
const Method = lazy(() => import("./pages/Method").then((m) => ({ default: m.Method })));
const later = (el: React.ReactNode) => <Suspense fallback={<Loading error={null} />}>{el}</Suspense>;
import "./styles.css";

// Hash routes so the built site works from any static host or straight from disk.
const router = createHashRouter([
  {
    element: <Shell />,
    errorElement: <NotFound />,
    children: [
      { path: "/", element: <Story /> },
      { path: "/cases", element: later(<Cases />) },
      { path: "/cases/:id", element: later(<Cases />) },
      { path: "/method", element: later(<Method />) },
      { path: "*", element: <NoSuchPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
