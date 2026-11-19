# Face AI Docker Setup

This repository contains a face recognition backend with InsightFace and FAISS.

## Run with Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

Then open:

- http://127.0.0.1:8000/docs

## Endpoints

- `POST /register` — register a face name and image
- `POST /recognize` — recognize faces in an image
- `GET /faces` — list registered faces
- `DELETE /faces/{face_id}` — delete a registered face
- `POST /bulk_import` — import images from `data/faces`

## Local data persistence

The `docker-compose.yml` mounts:

- `./data` → `/app/data`
- `./uploads` → `/app/uploads`

So FAISS index and image data persist across container restarts.

## Notes

- You can still use `.env` if desired, but Docker is the recommended way to run this service.
- If you want to pass environment variables directly, add them under `environment:` in `docker-compose.yml`.
