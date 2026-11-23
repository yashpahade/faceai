# Phase C: React Frontend (FaceAI Pro web app)

> Stack: Vite + React 18 + TailwindCSS + React Router + Zustand + Framer Motion + Recharts.
> Code: `frontend/`. Dev: `cd frontend; npm install; npm run dev` → http://localhost:5173
> (API `/v1` Vite proxy se FastAPI :8000 pe; same-origin, CORS ki zaroorat nahi).

## 1. Pages

| Route | Role | Kya |
|---|---|---|
| `/login` | all | Face login (liveness) ya email+password, animated tab switch |
| `/signup` | all | Step 1 details + consent, step 2 face enroll (camera) |
| `/dashboard` | student | Hero + "Mark attendance" (liveness), progress ring, stats, history |
| `/profile` | all | Edit profile, (re-)enroll face |
| `/admin` | admin | Overview stats, recent activity, quick actions |
| `/admin/students` (+`/:id`) | admin | CRM: search, batch filter, add (consent), detail, face enroll (camera/upload), delete, overrides |
| `/admin/attendance` | admin | Day view + manual override |
| `/admin/live` | admin | Kiosk: live camera scan → animated "marked" feed |
| `/admin/reports` | admin | Daily stacked chart, per-student %, CSV export |
| `/admin/batches` | admin | Timings, days, late rules |

## 2. Components

| Component | Kaam |
|---|---|
| `FaceCamera` | getUserMedia, mirrored preview (frames un-mirrored), animated oval: idle / scanning (rotating gradient + scan line + pulse) / success / error (shake), shutter flash |
| `LivenessFlow` | challenge → step prompts with animated arrows → frames → verify → token; step progress dots; success burst |
| `LiveDetector` | 2.5s loop, **ek request khatam hone ke baad hi agli**, tab hidden ho to pause |
| `AttendanceTable` | sort/filter; mobile pe cards, desktop pe table |
| `motion.jsx` | PageTransition, Stagger, AnimatedNumber, ProgressRing, SuccessBurst, Skeleton, Toaster, Aurora |

## 3. Design system

- **Type:** Inter Variable (self-hosted: CSP `font-src 'self'`, koi third-party request nahi)
- **Color:** brand indigo → accent violet gradient; semantic emerald (present), amber (late), rose (absent)
- **Surfaces:** `card` (soft shadow), `glass` (blur, auth pages + toasts + mobile tab bar)
- **Dark mode:** `prefers-color-scheme`, har component ke dark tokens
- **Motion:** ease `[0.22, 1, 0.36, 1]`, springs for layout (`layoutId` nav pill, tab pill).
  `MotionConfig reducedMotion="user"` + CSS fallback: OS mein "reduce motion" on ho to movement band.
- **A11y:** 44px+ touch targets, focus-visible rings, `role="alert"`/`aria-live` for results,
  labels on every input, keyboard-reachable everything.

## 4. Performance

- Admin pages `lazy()`: student ke phone pe admin code / charts download hi nahi hote.
- Initial JS ~108 KB gzip (React + router + motion); Reports (Recharts) ~107 KB alag chunk.
- Camera frames 960px JPEG q0.8 (~100 KB) upload, 1080p PNG (~1.5 MB) nahi.

## 5. Security in the browser

- JWT localStorage mein (PWA reload ke baad session). XSS defence: React escaping, koi
  `dangerouslySetInnerHTML` nahi, strict CSP (Caddy, Phase E).
- 401 → automatic logout. Attendance marking kabhi offline cache se nahi (Phase D).

## Self-check questions

1. Preview mirror hai par bheje gaye frames nahi. Agar frames bhi mirror kar dete to liveness kya karta?
2. LiveDetector `setInterval` ki jagah "reply ke baad next" kyun? Slow 3G pe kya farak padta?
3. Reduced-motion users ke liye animations band kyun karte hain?
