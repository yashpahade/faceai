// Camera frame -> compressed JPEG Blob (Phase D: mobile bandwidth).
// 1080p frame ~1.5 MB PNG; 960px JPEG q0.8 ~80-150 KB. Face recognition ke liye 960px kaafi hai
// (detector 640 pe chalta hai), aur mobile data/latency 10x kam.
export const MAX_SIDE = 960;

export function frameToCanvas(video, maxSide = MAX_SIDE) {
  const w = video.videoWidth;
  const h = video.videoHeight;
  const scale = Math.min(1, maxSide / Math.max(w, h));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(w * scale);
  canvas.height = Math.round(h * scale);
  // NOTE: un-mirrored frame (preview sirf CSS se mirror hai). Backend liveness "turn_left" image
  // coordinates mein naapta hai, isliye yahan flip NAHI karte.
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas;
}

export function canvasToJpeg(canvas, quality = 0.8) {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("capture failed"))), "image/jpeg", quality),
  );
}

export async function captureJpeg(video, opts = {}) {
  return canvasToJpeg(frameToCanvas(video, opts.maxSide), opts.quality);
}

// Upload kiye gaye file (gallery photo) ko bhi compress karo. createImageBitmap EXIF orientation
// apply karta hai (imageOrientation: "from-image"), backend bhi karta hai - double safe.
export async function compressFile(file, maxSide = MAX_SIDE, quality = 0.85) {
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * scale);
  canvas.height = Math.round(bmp.height * scale);
  canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
  return canvasToJpeg(canvas, quality);
}
