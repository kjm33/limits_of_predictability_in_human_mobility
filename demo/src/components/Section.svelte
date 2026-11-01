<script>
  import { reveal } from "../lib/anim.js";
  let { id, kicker, title, lede = "", children } = $props();
</script>

<section class="scene" {id} use:reveal>
  <div class="wrap">
    <span class="kicker" data-reveal>{kicker}</span>
    <h2 data-reveal>{title}</h2>
    {#if lede}<p class="lede" data-reveal>{lede}</p>{/if}
    {@render children()}
  </div>
</section>
