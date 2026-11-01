import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);
export { gsap, ScrollTrigger };

// Svelte action: fade/rise children marked with data-reveal once on enter.
export function reveal(node) {
  const els = node.querySelectorAll("[data-reveal]");
  const tween = gsap.from(els, {
    y: 26,
    opacity: 0,
    duration: 0.8,
    stagger: 0.09,
    ease: "power2.out",
    scrollTrigger: { trigger: node, start: "top 78%", once: true },
  });
  return {
    destroy() {
      tween.scrollTrigger?.kill();
      tween.kill();
    },
  };
}

// Svelte action: call a callback once when the element scrolls into view.
export function onEnter(node, callback) {
  const st = ScrollTrigger.create({
    trigger: node,
    start: "top 70%",
    once: true,
    onEnter: () => typeof callback === "function" && callback(),
  });
  return {
    destroy() {
      st.kill();
    },
  };
}
