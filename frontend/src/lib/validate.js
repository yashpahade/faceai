// Same rules as the server (src/faceai/attendance/validators.py). Server is the real guard;
// yahan sirf turant feedback (type karte hi) ke liye.

// Letters (any script, incl. Hindi matras = \p{M}), space, . ' -
const NAME_CHAR = /[\p{L}\p{M} .'-]/u;

// Typing filter: name field mein digits/symbols type hi nahi hote
export const sanitizeName = (v) => [...v].filter((ch) => NAME_CHAR.test(ch)).join("").replace(/\s{2,}/g, " ");
// Mobile: sirf digits (aur shuru mein +), max 13
export const sanitizePhone = (v) => v.replace(/(?!^\+)[^\d]/g, "").slice(0, 13);
export const sanitizeRoll = (v) => v.toUpperCase().replace(/[^A-Z0-9/-]/g, "").slice(0, 30);

export function nameError(v) {
  const t = v.trim();
  if (!t) return "Name is required";
  if (/\d/.test(t)) return "Name cannot contain numbers";
  if ([...t].some((ch) => !NAME_CHAR.test(ch))) return "Only letters, spaces and . ' -";
  if ([...t].filter((ch) => /[\p{L}\p{M}]/u.test(ch)).length < 2 || !/^[\p{L}]/u.test(t)) return "At least 2 letters";
  return null;
}

export function phoneError(v, required = false) {
  const d = v.replace(/[\s-]/g, "");
  if (!d) return required ? "Mobile number is required" : null;
  if (/[^\d+]/.test(d)) return "Only digits";
  if (!/^(?:\+?91|0)?[6-9]\d{9}$/.test(d)) return "Enter a valid 10-digit mobile (starts with 6-9)";
  return null;
}

export const passwordChecks = (v) => [
  ["8+ characters", v.length >= 8],
  ["A letter", /\p{L}/u.test(v)],
  ["A number", /\d/.test(v)],
];
export const passwordError = (v) => (passwordChecks(v).every(([, ok]) => ok) ? null : "Password needs 8+ characters with letters and numbers");

export const rollError = (v) => (!v || /^[A-Z0-9][A-Z0-9/-]*$/.test(v) ? null : "Only letters, numbers, - and /");
