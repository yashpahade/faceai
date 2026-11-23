# Phase 7: Trust & Safety (encryption, auth, audit, consent, deletion, liveness)

> Goal: face recognition ek **biometric** system hai. Password leak ho to badal lo; chehra badal
> nahi sakte. Isliye yahan "chalta hai" kaafi nahi hai. Data minimum rakho, encrypted rakho, har
> access ka hisaab rakho, aur delete karna ho to sach mein delete karo.

> ⚖️ Legal: India mein DPDP Act 2023, Europe mein GDPR (biometric = "special category"). Ye code
> technical controls deta hai. Legal compliance (consent text, purpose limitation, DPO, notices)
> ke liye lawyer se baat karo.

## 1. Threat model: kya bachana hai, kisse?

| Threat | Control | Code |
|---|---|---|
| DB file/backup chori | Embeddings AES-256-GCM se encrypted | `security/crypto.py`, `store/db.py` |
| Ek ki embedding doosre ki row mein chipkana | GCM AAD = `person_id\|model_id` | `test_cipher_roundtrip_and_aad_binding` |
| Koi bhi API call kare (naam list, "ye insaan DB mein hai?") | API key (`X-API-Key`), sirf hashes stored | `security/auth.py` |
| "Kisne kab kya kiya?" ka jawab nahi | Append-only audit log | `audit_log` table, `GET /v1/audit` |
| Bina permission enrollment | `consent: true` required, `consent_at` stored | `PersonCreate` |
| Delete ke baad data disk pe pada rehna | `PRAGMA secure_delete`, index se bhi hatana, retention | `delete_person`, `purge_embeddings_older_than` |
| Photo/screen dikha ke login | Liveness interface (fail-closed) | `security/liveness.py` |
| Raw photos leak | Photos **kabhi store nahi hoti**, sirf embedding | `routes.py` (memory mein decode) |

## 2. Encryption at rest

```
embedding (512 float32) ──AES-256-GCM(key, nonce, AAD=person_id|model_id)──► b"E1"|key_id|nonce|ct+tag
```
- **GCM** = encryption + integrity. Ek bit bhi badla to decrypt fail.
- **AAD** ciphertext ko uski row se bandhta hai. Attacker DB mein A ka vector B ki row mein copy kare
  ("main B hoon") to decrypt fail ho jaata hai.
- **Key rotation**: `FACEAI_ENCRYPTION_KEYS="2:<new>,1:<old>"`. Pehli key se encrypt, baaki se
  decrypt. `python -m faceai.security.migrate` sab rows nayi key pe le aata hai, phir purani hatao.
- **Key kahan?** Secret manager / env. DB ke saath kabhi nahi, git mein kabhi nahi.
- Purane plaintext rows (Phase 1 DB) bhi `migrate` encrypt kar deta hai.

Kya ye kaafi hai? Nahi. Running process ki memory mein vectors plaintext hain (search ke liye
zaroori). Encryption at rest *chori hui files* se bachata hai, compromised server se nahi.

## 3. Prod mein fail closed

`FACEAI_ENV=prod` mein app **ready nahi hogi** agar:
- `FACEAI_ENCRYPTION_KEYS` set nahi, ya
- `FACEAI_API_KEY_HASHES` set nahi (auth band nahi kar sakte), ya
- `FACEAI_LIVENESS=required` par koi checker configured nahi.

"Bhool gaye config karna" ka nateeja *secure default* hona chahiye, khula system nahi.

## 4. Audit log

Har write (`person.create`, `face.enroll`, `person.delete`, `retention.purge`) ek row:
`ts, action, actor (key:ab12cd34), person_id, request_id, detail`.
- **Biometric ya naam audit mein nahi**: audit log khud PII ka doosra store na ban jaaye.
- Person delete hone ke baad bhi audit rehta hai. Wahi **proof of deletion** hai ("user X ka data
  23 Nov ko key Y ne delete kiya, 3 embeddings").
- `request_id` se logs (Phase 0) aur audit jud jaate hain.

## 5. Deletion + retention ("right to be forgotten")

`DELETE /v1/persons/{id}` → SQLite rows (CASCADE) + FAISS index se hatao + audit + receipt
`{"person_id", "deleted_embeddings"}`. `PRAGMA secure_delete=ON` deleted pages ko zero se overwrite
karta hai, warna data DB file mein "free pages" mein pada rehta hai.

Backups? Unme purana data abhi bhi hai. Backup retention policy bhi utni hi zaroori hai.

`FACEAI_RETENTION_DAYS=365`: startup pe isse purani embeddings purge (aur
`python -m faceai.security.retention` cron se). Data jitna kam rakhoge, leak utna chhota hoga.

## 6. Liveness (presentation attack detection)

Bina liveness ke system "kisi ki photo dikhao, andar aao" hai. Is repo mein **koi PAD model ship
nahi hota**, sirf interface + wiring:
- `FACEAI_LIVENESS=off` (default): `liveness: null` response mein. Matlab: *check nahi hua*.
- `FACEAI_LIVENESS=required`: checker nahi diya to app ready nahi. Spoof mila to enroll 422,
  recognize mein us face ka match nahi milta.

Kyun ship nahi kiya? Ek PAD model ko apne camera aur attack types (print, replay, mask) pe
**APCER/BPCER** (ISO/IEC 30107-3) se evaluate kiye bina lagana "security theatre" hai: false sense
of security, jo koi check na hone se bhi bura hai. Phase 2 wala sabak yahan bhi lagta hai: naapo, phir
bharosa karo. Model lagane ke liye `LivenessChecker` protocol implement karo (`check(image, bbox)
-> LivenessResult`) aur `create_app(..., liveness=checker)` mein do.

## 7. Bias / fairness

Phase 2 mein bola tha: TAR/FAR ko demographic groups (umar, gender, skin tone) mein **alag-alag**
naapo. Trust & safety ka ye sabse zaroori hissa hai jo code se solve nahi hota, data aur process se
hota hai. Kisi group pe FAR zyada = us group ke log zyada galat pakde jaayenge.

## Self-check questions

1. DB encrypted hai, server hack ho gaya. Attacker kya padh sakta hai, kya nahi?
2. AAD na ho to attacker encrypted DB ke saath kya kar sakta hai, bina key jaane?
3. Audit log mein naam kyun nahi rakhte? Phir bhi audit "kisi ke baare mein" kaise batata hai?
4. `liveness: null` aur `liveness: {live: true}` mein kya farak hai? Client ko kaise treat karna chahiye?
5. User ne delete request di. Kahan-kahan se data hatana padega (hint: index, backups, logs)?
