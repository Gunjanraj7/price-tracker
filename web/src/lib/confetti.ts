// A short burst of confetti, for a price that hit its target. Pure CSS
// animation (see .confetti in styles.css), skipped when the system asks for less motion.

const COLORS = ["#ff9900", "#2874f0", "#ffe11b", "#fb641b", "#26a541", "#ff5ca8", "#8b5cf6"];

export function confetti(pieces = 90): void {
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

  const layer = document.createElement("div");
  layer.className = "confetti";
  layer.setAttribute("aria-hidden", "true");
  for (let i = 0; i < pieces; i++) {
    const piece = document.createElement("i");
    const style = piece.style;
    style.setProperty("--left", `${Math.random() * 100}vw`);
    style.setProperty("--drift", `${(Math.random() - 0.5) * 30}vw`);
    style.setProperty("--spin", `${(Math.random() - 0.5) * 1440}deg`);
    style.setProperty("--delay", `${Math.random() * 0.35}s`);
    style.setProperty("--duration", `${1.6 + Math.random() * 1.4}s`);
    style.setProperty("--color", COLORS[i % COLORS.length]);
    if (i % 3 === 0) piece.className = "round";
    layer.append(piece);
  }
  document.body.append(layer);
  window.setTimeout(() => layer.remove(), 3500);
}
