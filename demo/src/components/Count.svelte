<script>
  import { gsap } from "../lib/anim.js";
  let { value = 0, digits = 0, suffix = "", prefix = "" } = $props();

  let el = $state(null);
  let shown = $state(0);

  $effect(() => {
    if (!el) return;
    const obj = { v: 0 };
    const tween = gsap.to(obj, {
      v: value,
      duration: 1.8,
      ease: "power2.out",
      scrollTrigger: { trigger: el, start: "top 88%", once: true },
      onUpdate: () => (shown = obj.v),
    });
    return () => {
      tween.scrollTrigger?.kill();
      tween.kill();
    };
  });
</script>

<span class="num" bind:this={el}>
  {prefix}{shown.toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })}{suffix}
</span>
