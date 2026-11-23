# Features: Bulk Import, Teacher Role, Holidays & Leave

## 1. Bulk import (`/admin/import/students`)

1. Admin → Students → **Import CSV** → template download (`full_name,email,phone,roll_no,batch`)
2. Excel/Sheets mein bharo → **Save as CSV UTF-8** → upload → **Check file** (dry run)
3. Preview: har galat row ka number + column + wajah (naam mein digit, galat mobile, duplicate
   email file mein ya DB mein, batch naam nahi mila). Ek row ki **saari** galtiyan ek saath.
4. Sab theek → consent checkbox → **Import** → **logins CSV download** (temporary passwords, sirf ek baar)

Design choices:
- **All-or-nothing:** ek bhi error → kuch save nahi. Aadha import (300 me se 287) + "kaunse reh
  gaye?" wali confusion se behtar hai "fix karo, dobara chalao".
- **Same validators** jo signup/admin-create mein hain (`attendance/validators.py`): koi doosra
  raasta nahi jisse kharab data aa sake.
- Limits: 1 MB, 2,000 rows; Excel ka BOM handle; batch naam case-insensitive.

## 2. Teacher role

| | Admin | Teacher | Student |
|---|---|---|---|
| Students list/detail, face enroll | sab | **sirf assigned batches** | — |
| Attendance view, manual override, live kiosk | sab | **sirf assigned batches** | khud ki |
| Reports, CSV export, overview | sab | **sirf assigned batches** | — |
| Leave approve/reject | sab | **sirf assigned batches** | request |
| Students add/delete/import, batches, teachers, holidays | ✅ | ❌ (403) | ❌ |

Scoping **server pe** hota hai (`staff_scope` dependency): UI chhupana security nahi hai; teacher
seedha API call kare to bhi doosre batch ka data nahi milta (`tests/test_features.py`). Teacher ke
kiosk pe doosre batch ka student → "not in your batches", mark nahi hota.

Data model: `batch_teachers` (many-to-many). Admin → Teachers page pe batch chips toggle karke assign.

## 3. Holidays + leave

- **Holiday** (`holidays` table): din + naam + batch (khaali = saare batches). Us din: attendance
  mark nahi hoti ("holiday: Diwali"), report mein `holiday`, absent nahi.
- **Leave** (`leaves` table): student request (date range + reason) → teacher/admin approve/reject.
  Sirf **approved** leave ke din `leave` dikhte hain; pending abhi bhi absent.
- **Attendance %** = (present + late) ÷ (present + late + absent). Holiday aur approved leave
  denominator mein nahi.

Migration: `0002_teachers_holidays_leaves` (Alembic) + `test_upgrade_head_matches_models`.

## Self-check questions

1. Import all-or-nothing kyun rakha? Partial import mein kya problem hoti?
2. Teacher ka menu chhupa diya, phir bhi server pe scope check kyun zaroori hai?
3. Pending leave ko absent kyun gina jaata hai, approved ko kyun nahi?
