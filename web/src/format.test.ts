import { describe, expect, it } from "vitest";
import { day, month, pct, pctSmart, signed, tidy, usd, usdCompact } from "./format";

describe("format", () => {
  it("formats percentages with sensible precision", () => {
    expect(pct(0.2437)).toBe("24%");
    expect(pctSmart(0.0074)).toBe("0.74%");
    expect(pctSmart(0.0236)).toBe("2.4%");
    expect(pctSmart(0.45)).toBe("45%");
  });

  it("formats money", () => {
    expect(usd(5000)).toBe("$5,000");
    expect(usd(105.53, 2)).toBe("$105.53");
    expect(usdCompact(366_522_483)).toBe("$366.5M");
    expect(usdCompact(44_458)).toBe("$44K");
  });

  it("formats dates without timezone drift", () => {
    expect(day("2026-06-25")).toBe("Jun 25, 2026");
    expect(month("2024-07-01")).toBe("Jul 2024");
  });

  it("tidies all-caps source names", () => {
    expect(tidy("DEPARTMENT OF HUMAN SERVICES")).toBe("Department of Human Services");
    expect(tidy("OKLAHOMA STATE UNIVERSITY")).toBe("Oklahoma State University");
  });
});

describe("signed", () => {
  it("always shows the sign", () => {
    expect(signed(0.65)).toBe("+0.65");
    expect(signed(-0.1)).toBe("−0.10");
    expect(signed(0)).toBe("+0.00");
  });
});
