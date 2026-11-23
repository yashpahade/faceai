# FaceAI Pro: Architecture

> Ek jagah poora system: kaun sa hissa kya karta hai, data kahan rehta hai, ek request kaise
> chalti hai, aur scale karne pe kya badlega. Diagrams Mermaid mein hain (GitHub pe render hote hain).

## 1. System context

```mermaid
flowchart LR
    subgraph Client["Client (PWA)"]
        S["Student phone<br/>face login · self attendance"]
        A["Admin laptop / kiosk tablet<br/>CRM · live scan · reports"]
    end

    subgraph Edge["Edge"]
        C["Caddy<br/>HTTPS (Let's Encrypt) · static React · security headers"]
    end

    subgraph App["Application (FastAPI, single process)"]
        API["REST API /v1<br/>JWT (users) · API key (machines)"]
        RL["Rate limiter + admission control"]
        ATT["Attendance service<br/>auth · CRM · rules · reports"]
        BIO["Recognition service<br/>enroll · recognize · delete · audit"]
        LIV["Liveness challenge store"]
        ENG["Face engine<br/>SCRFD → align → ArcFace"]
        IDX[("FAISS index<br/>in-memory cache")]
    end

    subgraph Data["Data"]
        PG[("Product DB<br/>Postgres / SQLite<br/>users · batches · attendance")]
        BDB[("Biometric store<br/>SQLite, AES-GCM<br/>embeddings · audit_log")]
        MOD[["ONNX models<br/>(registry: MLflow)"]]
    end

    subgraph Ops["Ops"]
        PR["Prometheus + alerts"] --> GR["Grafana"]
        BK["Backups<br/>pg_dump · SQLite online backup"]
    end

    S & A -->|HTTPS| C -->|/v1| API
    API --> RL --> ATT & BIO & LIV
    ATT --> PG
    ATT --> BIO
    BIO --> ENG --> MOD
    BIO --> IDX
    BIO --> BDB
    LIV --> ENG
    PR -.scrape /metrics.-> API
    BK -.-> PG & BDB
```

**Design principles**

| Principle | Kahan dikhta hai |
|---|---|
| Biometric data ko baaki data se alag rakho | Do databases; product DB mein sirf `person_id` |
| Source of truth vs cache | SQLite = truth, FAISS = startup pe rebuild hone wala cache |
| Fail closed | Prod mein keys/secret na ho to app *ready nahi hoti* |
| Model ek artifact hai, code nahi | Weights registry se (sha256-verified), image mein nahi |
| Har decision naapo | Eval pipeline (DVC), load tests, LFW experiments |

## 2. Code layers

```mermaid
flowchart TB
    R1["api/routes.py · attendance/routes.py<br/>HTTP, validation, auth deps"] --> S1["attendance/service.py<br/>product rules"]
    R1 --> S2["service.py (RecognitionService)<br/>biometric rules, audit"]
    S1 --> S2
    S1 --> M1["attendance/models.py<br/>SQLAlchemy ORM"]
    S2 --> V["vision/<br/>detector · align · embedder · quality · preprocess"]
    S2 --> ST["store/<br/>db.py (SQLite) · index.py (FAISS)"]
    S2 --> SEC["security/<br/>crypto · auth · liveness · challenge"]
```

Har layer sirf neeche wali ko jaanti hai. Isliye tests fake engine (`tests/fakes.py`) se poora API
bina GPU ke chala lete hain, aur Postgres pe jaane ke liye sirf `models.py` ka engine URL badalta hai.

## 3. Database architecture

### 3.1 Do databases kyun?

| | Product DB | Biometric store |
|---|---|---|
| Kya | naam, email, phone, batch, attendance | face embeddings (512-d), audit log |
| Tech | SQLAlchemy → SQLite (dev) / **Postgres** (prod) | SQLite (WAL) + FAISS cache |
| Encryption | Disk/volume level | **Row level AES-256-GCM**, AAD = `person_id\|model_id` |
| Access | Har API call | Sirf `RecognitionService` (audit ke saath) |
| Leak hua to | Contact data leak (bura) | Chehra badal nahi sakte, isliye extra layer |

Link: `users.person_id` ↔ `persons.id`. Product DB ke paas chehre ka data hai hi nahi.

### 3.2 Entity-relationship

```mermaid
erDiagram
    BATCHES ||--o{ USERS : "has students"
    USERS ||--o{ ATTENDANCE : "marks"
    BATCHES ||--o{ ATTENDANCE : "for"
    USERS |o--o| PERSONS : "person_id (cross-DB link)"
    PERSONS ||--o{ EMBEDDINGS : "has"
    PERSONS ||..o{ AUDIT_LOG : "person_id (no FK: survives deletion)"

    BATCHES {
        string id PK
        string name UK
        string start_time "HH:MM local"
        string end_time
        string days "0..6 (Mon=0)"
        int late_after_min
        int open_before_min
    }
    USERS {
        string id PK
        string email UK
        string password_hash "scrypt"
        string role "admin | student"
        string full_name
        string roll_no
        string status "active | inactive"
        string batch_id FK
        string person_id UK "biometric link"
        int token_version "JWT revocation"
    }
    ATTENDANCE {
        int id PK
        string user_id FK
        string batch_id FK
        date day "local date"
        string status "present | late"
        string method "face | manual"
        float confidence
        string marked_by
    }
    PERSONS {
        string id PK
        string name "= user id (no PII)"
        string consent_at
    }
    EMBEDDINGS {
        int id PK
        string person_id FK
        string model_id "embedding versioning"
        blob vector "E1|key_id|nonce|ciphertext"
        float det_score
        float sharpness
        string created_at "retention"
    }
    AUDIT_LOG {
        int id PK
        string ts
        string action
        string actor "key:ab12 / user:cd34"
        string person_id
        string request_id
        string detail "JSON, no PII"
    }
```

**Constraints jo bugs rokte hain**

- `UNIQUE(user_id, batch_id, day)` on attendance: do kiosks ek saath mark karein to bhi duplicate
  nahi (service check + DB constraint, race-safe).
- Absent rows store nahi hote, **compute** hote hain (class days − records). Kal batch ka schedule
  badla to purane din galat "absent" nahi bante.
- `embeddings.model_id`: model upgrade ke baad purani embeddings search mein nahi aati (alag vector space).
- `audit_log` pe FK nahi: person delete ho, audit (proof of deletion) rahe.
- `PRAGMA secure_delete`: deleted embeddings disk pe zero se overwrite.
- `users.token_version`: password change / deactivate → saare purane JWT turant invalid.

**Migrations:** dev/test `create_all`; prod Alembic (`python -m faceai.attendance.migrate`).

## 4. Face recognition pipeline

```mermaid
flowchart LR
    IMG["Image bytes"] --> DEC["decode_image<br/>EXIF rotation"]
    DEC --> DET["SCRFD det_10g<br/>640², threshold 0.4<br/>boxes + 5 landmarks"]
    DET --> NMS["NMS / merge"]
    NMS --> ALN["Umeyama similarity<br/>→ 112×112 aligned crop"]
    ALN --> Q{"Enroll?<br/>quality gate"}
    Q -->|"det≥0.6, face≥80px,<br/>sharp, frontal"| EMB
    ALN --> EMB["ArcFace w600k_r50<br/>→ 512-d, L2 norm"]
    EMB --> SRCH["FAISS IndexFlatIP<br/>cosine top-k"]
    SRCH --> AGG["Person-level max"]
    AGG --> THR{"sim ≥ threshold?<br/>(margin for login)"}
    THR -->|yes| MATCH["match"]
    THR -->|no| UNK["unknown"]
```

| Stage | Model / algo | Measured (RTX 3050 laptop) | Kyun |
|---|---|---|---|
| Detect | SCRFD 10G, 640², thr 0.4 | 18-23 ms GPU · 141 ms CPU | Measured: 1280² misses 90% of LFW faces and is 7× slower; thr 0.4 halves missed faces |
| Align | Umeyama (5 points) | <1 ms | ArcFace ne aligned faces pe hi seekha; bina iske accuracy girti hai |
| Embed | ArcFace R50 (WebFace600K) | 10.6 ms/face (b=1) → 4.4 ms (b=16) | 512-d, cosine; LFW 99.73% (thr 0.4) |
| Search | FAISS flat inner product | <1 ms @ 10k | Exact; ~1 lakh tak flat kaafi |
| End-to-end | API, 1-face image | p50 ~42 ms (c=1) | `docs/phase-4-serving.md` |

**Thresholds (alag-alag kaam, alag risk):**

| Use | Setting | Default | Logic |
|---|---|---|---|
| Recognize / kiosk | `FACEAI_MATCH_THRESHOLD` | 0.4 | Admin supervised; galat match manual override se theek |
| Face login | `FACEAI_FACE_LOGIN_THRESHOLD` + margin 0.05 | 0.5 | Account access = strict; do log paas-paas → password maango |
| Calibration | `python -m faceai.eval.calibrate` | your data | LFW threshold (0.253) apne cameras pe transfer nahi hota |

**Phase A experiments** (`docs/phase-a-accuracy.md`): CLAHE, flip-TTA, 1280 and multi-scale were
measured on LFW and rejected (no gain, or catastrophic for 1280); they stay as config switches for
re-measuring on your own cameras.

**Liveness (active):** random 2 steps (turn left/right/center) → frames → yaw (5 landmarks) +
same-identity check → single-use token (embedding ke saath). Face login/self-attendance usi token
ke face se hota hai, alag photo nahi bhej sakte. Limits: video replay / 3D mask nahi rokta
(passive PAD model chahiye, license + evaluation ke saath).

## 5. Key flows

### Face login

```mermaid
sequenceDiagram
    autonumber
    participant P as Phone (PWA)
    participant A as API
    participant L as Challenge store
    participant E as Face engine
    participant B as Biometric index
    participant D as Product DB
    P->>A: POST /v1/liveness/challenge
    A->>L: create (random steps, 60s TTL)
    A-->>P: steps ["turn_left","center"]
    Note over P: user follows prompts,<br/>1 frame per step (960px JPEG)
    P->>A: POST /v1/liveness/verify (frames)
    A->>E: detect + embed each frame
    A->>L: verify yaw sequence + same face, burn challenge
    A-->>P: liveness token (2 min, single use)
    P->>A: POST /v1/auth/face-login {token}
    A->>L: consume token → live embedding
    A->>B: top-k persons
    B-->>A: best + margin check
    A->>D: user by person_id (active?)
    A-->>P: JWT (amr: face)
```

### Kiosk / live attendance

```mermaid
sequenceDiagram
    participant K as Admin kiosk
    participant A as API
    participant R as RecognitionService
    participant S as AttendanceService
    loop every 2.5s (only after previous reply)
        K->>A: POST /v1/admin/attendance/scan (frame)
        A->>R: recognize all faces
        R-->>A: matches (person_id, similarity)
        A->>S: mark(user) per match
        S->>S: batch day? window? late? duplicate?
        S-->>A: present / late / already_marked / rejected
        A-->>K: results → animated feed
    end
```

## 6. Scaling path (honest limits)

Abhi design **ek API process** ke liye hai. Ye cheezein process memory mein hain:

| Component | Abhi | Multi-replica ke liye |
|---|---|---|
| Biometric store | SQLite file (volume) | Postgres + **pgvector** (ya Milvus/Qdrant), encrypted columns |
| FAISS index | In-memory, startup rebuild | Shared vector DB, ya har replica apna index + change feed |
| Liveness challenges/tokens | In-memory dict | Redis (TTL keys) |
| Rate limiter | In-memory buckets | Redis / API gateway |
| GPU | Same process | Alag inference service (Triton), batching wahan |

Pehli bottleneck GPU throughput hai (~15 req/s laptop GPU pe, Phase 4). Ek class (60 students,
kiosk 2.5s/frame) ke liye ye kaafi se zyada hai. 50+ simultaneous kiosks pe upar wala path lo.

## 7. Failure modes

| Failure | Behaviour |
|---|---|
| Model files missing / checksum mismatch | `/health/ready` = 503, load balancer traffic nahi bhejta |
| GPU fail | ORT CPU fallback (warning; `device=cuda` diya ho to fail) |
| Overload | 503 + `Retry-After` (admission control), har request slow nahi |
| Brute force login | 429 (rate limit) |
| DB file corrupt | Daily verified backups (`faceai.ops.backup`, `PRAGMA integrity_check`) |
| Encryption key lost | Embeddings unrecoverable → re-enroll (key backup alag, safe jagah) |
| Distribution drift (naye cameras) | Prometheus PSI alert → recalibrate threshold |
