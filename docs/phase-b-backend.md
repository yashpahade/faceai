# Phase B: Product Backend (auth, roles, students, batches, attendance, reports)

> Goal: biometric engine (Phase 1-7) ke upar ek sellable product: login, admin/student roles,
> student CRM, batches, attendance rules, reports. Architecture diagram: `docs/architecture.md`.

## 1. Do databases (privacy by design)

Product data (naam, email, attendance) **SQLAlchemy** se alag DB mein, biometric embeddings purane
encrypted store mein. Link sirf `users.person_id`. Product DB leak ho to chehre ka data usmein nahi
hai. SQLAlchemy isliye ki prod mein Postgres pe sirf URL badalna pade (Phase E).

## 2. Authentication

| Kya | Kaise | Kyun |
|---|---|---|
| Password hash | `scrypt` (stdlib), per-user salt | Memory-hard: GPU brute force mehenga |
| Session | JWT HS256 (`sub`, `role`, `ver`, `amr`, `exp`) | Stateless; har request pe DB lookup sirf revocation check ke liye |
| Revocation | `users.token_version` | Password change / deactivate → purane tokens turant bekaar |
| Login error | Hamesha "invalid email or password" | "Email exists?" leak nahi (user enumeration) |
| Face login | Liveness token → wahi embedding → identify | Liveness ek insaan kare, login doosra, ye possible nahi |
| Face login threshold | 0.5 + top-2 margin 0.05 | Recognition (0.4) se strict: account access ka risk zyada |
| Admin account | `python -m faceai.attendance.create_admin` | Signup sirf students; admin API se nahi ban sakta |

`amr` (authentication method: `pwd`/`face`) token mein hai: future policy jaise "reports export ke
liye password login chahiye" isi se lagti hai.

## 3. RBAC

`current_user` (JWT verify + DB check) → `require_admin` (role). Student `/v1/admin/*` pe 403.
Phase 7 ki `X-API-Key` machine clients (integrations) ke liye `/v1` biometric routes pe rehti hai.

## 4. Attendance rules (`attendance/rules.py`, pure functions)

```
open_before_min    start      start+late_after_min        end
      |-------------|--------------------|-----------------|
  attendance opens   present ...........  late ............  closed
```

- Batch ke din (Mon=0..Sun=6) ke alawa: reject
- Ek din ek record: `UNIQUE(user_id, batch_id, day)` + service check (do kiosks ek saath = safe)
- Local timezone (`FACEAI_TIMEZONE`, default Asia/Kolkata): server UTC pe ho to bhi 9 baje = 9 baje IST
- **Absent store nahi hota, compute hota hai**: class days − records. Schedule badla to purane
  din galat absent nahi bante. Aaj ka din absent nahi gina jaata (class abhi chal sakti hai).

## 5. Marking paths

| Path | Kaun | Liveness | Identity check |
|---|---|---|---|
| `POST /v1/me/attendance` | Student (phone) | Zaroori (token) | Live face == apna `person_id` |
| `POST /v1/admin/attendance/scan` | Admin kiosk | Nahi (supervised) | Frame ke saare recognized faces |
| `POST /v1/admin/attendance/manual` | Admin | — | Override (present/late/absent), audit `marked_by` |

## 6. Reports

`/v1/admin/reports/summary` (per student present/late/absent/%, per day totals) aur
`/export.csv`. CSV mein **formula injection** guard: `=HYPERLINK(...)` naam wala student Excel
mein code na chala de (`'` prefix).

## Self-check questions

1. Face login threshold recognition threshold se zyada kyun hai? Margin check kya rokta hai?
2. Absent rows ko DB mein store karne mein kya problem hoti?
3. JWT stateless hai, phir bhi har request pe DB lookup kyun? Bina iske password change ke baad kya hota?
4. Student ki self-attendance ke liye liveness zaroori hai, kiosk ke liye nahi. Kyun?
