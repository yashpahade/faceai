import { describe, expect, it } from "vitest";

import { nameError, passwordChecks, passwordError, phoneError, rollError, sanitizeName, sanitizePhone, sanitizeRoll } from "./validate";

describe("name", () => {
  it("accepts letters in any script", () => {
    expect(nameError("Asha Rao")).toBeNull();
    expect(nameError("D'Souza-Pinto")).toBeNull();
    expect(nameError("अमित कुमार")).toBeNull();
  });
  it("rejects digits, symbols, too short", () => {
    expect(nameError("Asha123")).toMatch(/numbers/);
    expect(nameError("Asha@Rao")).toMatch(/Only letters/);
    expect(nameError("A")).toMatch(/2 letters/);
  });
  it("typing filter drops digits and symbols", () => {
    expect(sanitizeName("As1ha@ Rao")).toBe("Asha Rao");
  });
});

describe("mobile", () => {
  it("accepts valid Indian mobiles with prefixes/spaces", () => {
    for (const v of ["9876543210", "98765 43210", "+919876543210", "09876543210"]) expect(phoneError(v)).toBeNull();
  });
  it("rejects bad numbers", () => {
    expect(phoneError("12345")).toMatch(/10-digit/);
    expect(phoneError("5876543210")).toMatch(/10-digit/);
    expect(phoneError("", true)).toMatch(/required/);
  });
  it("typing filter keeps only digits (and leading +)", () => {
    expect(sanitizePhone("+91 98a76-54")).toBe("+919876 54".replace(" ", ""));
  });
});

describe("password", () => {
  it("needs 8+ chars, a letter and a number", () => {
    expect(passwordError("asha2026")).toBeNull();
    expect(passwordError("password")).not.toBeNull();
    expect(passwordError("12345678")).not.toBeNull();
    expect(passwordChecks("ab1").map(([, ok]) => ok)).toEqual([false, true, true]);
  });
});

describe("roll no", () => {
  it("uppercases and filters", () => {
    expect(sanitizeRoll("r-01@a")).toBe("R-01A");
    expect(rollError("R-01")).toBeNull();
  });
});
