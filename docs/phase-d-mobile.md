# Phase D: Mobile (PWA, camera, bandwidth, touch)

> Goal: phone pe app jaisa experience: home screen icon, full-screen, front camera, kam data,
> ek haath se use.

## 1. Phone pe chalao (same Wi-Fi, development)

Camera (`getUserMedia`) sirf **HTTPS** ya `localhost` pe milta hai. Phone ke liye PC `localhost`
nahi hai, isliye dev server self-signed HTTPS ke saath chalta hai.

```powershell
# Terminal 1: backend (PC pe)
.venv\Scripts\python -m faceai.attendance.create_admin --email admin@school.in   # ek baar
.venv\Scripts\python -m faceai                                                   # :8000

# Terminal 2: frontend, HTTPS + LAN
cd frontend
npm install          # ek baar
npm run dev:phone    # "Network: https://<PC-IP>:5173" print hoga
```

Phone pe (same Wi-Fi):
1. Chrome/Safari mein `https://<PC-IP>:5173` kholo. PC ka IP: `ipconfig` → Wi-Fi → IPv4.
2. "Your connection is not private": **Advanced → Proceed** (self-signed dev certificate; production
   mein Caddy asli certificate laata hai).
3. Camera permission **Allow**.
4. Install: Chrome menu → **Add to Home screen** (iPhone: Share → Add to Home Screen). Ab ye
   full-screen app ki tarah khulta hai.

Phone se page nahi khul raha? Windows Firewall port 5173 block kar raha hai. Pehli baar `npm run
dev:phone` pe Windows "Allow access" poochhe to **Private networks** allow karo.

Sirf frontend phone se reach hona chahiye: `/v1` requests Vite proxy PC ke andar hi
FastAPI (:8000) tak le jaata hai.

## 2. Production (real phones, internet)

`docker-compose.prod.yml` (Phase E): domain ka DNS server pe point karo, `FACEAI_DOMAIN` set karo,
Caddy Let's Encrypt certificate khud le aata hai. Students `https://attendance.yourschool.in`
kholke "Add to Home screen" karte hain. App store ki zaroorat nahi.

## 3. Kya optimize kiya

| Area | Kya | Kyun |
|---|---|---|
| PWA | manifest, icons (192/512, maskable), service worker (Workbox) | Installable, full-screen, fast reload |
| Offline | App shell + pehle dekhe gaye GET reports (NetworkFirst, 4s timeout) | Kamzor network pe bhi history dikhe |
| Offline (jaan-boojh ke NAHI) | Attendance marking, liveness, login | Cache se "present" ka jhootha bharosa nahi |
| Camera | `facingMode: user`, 1280×720 ideal, 24 fps, `playsInline` | iOS fullscreen video nahi, battery/heat kam |
| Portrait | 3:4 camera box on phones, 16:9 desktop; oval phone ke hisaab se | Vertical video natural lage |
| Upload | Frame → 960px JPEG q0.8 (~100 KB) | 1080p PNG ~1.5 MB; mobile data + latency 10× kam |
| Gallery photos | `createImageBitmap(..., imageOrientation: "from-image")` + compress | EXIF rotation + size |
| Touch | 44-52px targets, bottom tab bar (thumb zone), `safe-area-inset` | Ek haath, iPhone notch/home bar |
| Kiosk loop | Reply ke baad hi next frame; tab hidden → pause | Slow network pe requests jama nahi, battery |
| Data | Admin code lazy; student phone pe charts download nahi | Pehli load ~108 KB gzip |

## 4. Mirror wali gotcha

Front camera preview CSS se mirror hai (selfie jaisa natural). Bheje gaye frames **un-mirrored**,
kyunki liveness "turn_left" image coordinates mein naapta hai. Isliye prompt user ki taraf se
ulta likha hai ("Turn your head right" = image mein left). Phase A ka flip-TTA embedding ko
mirror-invariant bhi banata hai.

## Self-check questions

1. Phone pe `http://<PC-IP>:5173` (bina S) pe camera kyun nahi chalta?
2. Attendance POST ko service worker cache kyun nahi karta?
3. 960px JPEG kaafi kyun hai jab detector 640 pe chalta hai?
