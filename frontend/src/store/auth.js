import { create } from "zustand";
import { persist } from "zustand/middleware";

// Token localStorage mein (PWA reload ke baad login rahe). XSS se bachao ke liye app mein
// kahin bhi user-provided HTML render nahi hota (React default escaping).
export const useAuth = create(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: "faceai-auth" },
  ),
);
