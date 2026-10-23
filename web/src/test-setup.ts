import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; Radix (shadcn Slider/Select) measures with it.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
