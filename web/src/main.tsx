import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import { NoSuchPage, NotFound, Shell } from "./components/Shell";
import { Cases } from "./pages/Cases";
import { Method } from "./pages/Method";
import { Story } from "./pages/Story";
import "./styles.css";

// Hash routes so the built site works from any static host or straight from disk.
const router = createHashRouter([
  {
    element: <Shell />,
    errorElement: <NotFound />,
    children: [
      { path: "/", element: <Story /> },
      { path: "/cases", element: <Cases /> },
      { path: "/cases/:id", element: <Cases /> },
      { path: "/method", element: <Method /> },
      { path: "*", element: <NoSuchPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
