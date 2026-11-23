import "@testing-library/jest-dom/vitest";

// jsdom mein IntersectionObserver nahi hota (asli browsers mein hai). AnimatedNumber "dikhne pe"
// count karta hai -> test mein turant "visible" maan lo.
class IO {
  constructor(cb) {
    this.cb = cb;
  }
  observe(el) {
    this.cb([{ isIntersecting: true, target: el, intersectionRatio: 1 }]);
  }
  unobserve() {}
  disconnect() {}
}
globalThis.IntersectionObserver = globalThis.IntersectionObserver || IO;
