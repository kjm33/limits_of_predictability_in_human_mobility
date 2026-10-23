# The "zip trick": how S_actual is measured (Lempel–Ziv / Kontoyiannis estimator)

*Note on the entropy estimator used in `src/mobility/entropy.py::lz_entropy`, following Song et al. 2010 (SOM S4) and Kontoyiannis et al. 1998.*

## Core identity: compression = prediction

Shannon proved the optimal code for a source compresses it to exactly H bits/symbol — no more, no less. So "how compressible is your location history?" *is* "how predictable are you?", measured without ever building a model. gzip/zip are LZ-family compressors, and the Kontoyiannis estimator we use is an idealized, mathematically clean zipper.

## What the zipper actually does

A zip file is mostly *back-references*: instead of re-storing a chunk of text, it stores "(go back 200 chars, copy 5)". Our estimator makes that explicit. Walk along the sequence; at each position `i`, ask: *how far can I copy from my own past before I hit something genuinely new?*

```
Λ(i) = length of the shortest block starting at i
       that appears NOWHERE in the prefix seq[0:i]
```

Everything in that block except the **last** symbol was "already seen — free". The last symbol is the surprise; you had to actually pay for it. So Λ(i) = freebies + 1.

## Worked example

Sequence `ABABC`:

| i | prefix seen | block tried | Λ(i) | reading |
|---|---|---|---|---|
| 0 | *(empty)* | `A` not found | 1 | total surprise |
| 1 | `A` | `B` not found | 1 | surprise |
| 2 | `AB` | `A`✓ `AB`✓ `ABC`✗ | **3** | saw the pattern `AB` before — 2 freebies, then `C` surprises |
| 3 | `ABA` | `B`✓ `BC`✗ | 2 | 1 freebie |
| 4 | `ABAB` | `C`✗ | 1 | surprise |

ΣΛ = 8, and S = n·log₂n / ΣΛ = 5·2.32/8 ≈ **1.45 bits**. The histogram entropy S_unc of the same string is 1.52 — LZ came in *lower*, because it noticed `AB` repeats in *order*, which the histogram can't see. That's the whole point of S_actual.

## Why the formula is the price of zipping

A back-reference into an n-symbol history is just a number between 1 and n — it costs **log₂n bits** — and it delivers Λ(i) symbols. Bits per symbol at position i ≈ log₂n / Λ(i). Averaging over all positions gives exactly `n·log₂n / ΣΛ(i)`. The reason `log₂n` (history size), not `log₂(alphabet)`, appears: you're paying for a *pointer into your past*, not for a fresh symbol. And the deep theorem (Kontoyiannis 1998): the longest match into a history of length n grows like log n / H, so this ratio converges to the true entropy rate — capturing **every order of correlation simultaneously** (daily cycles, weekly cycles, Markov structure), because matching is on contiguous blocks, i.e., on arbitrary contexts.

Implementation detail: matching uses `str.find` against the exact prefix (C-speed two-way search); cells are mapped to single chars via `np.unique(..., return_inverse=True)`.

## The two sanity limits (both in our tests)

- `AAAAA...` (perfectly routine life): blocks match all the way back, Λ explodes, S → 0. Zero entropy = zero surprise = in principle 100% predictable. This is the *correct* limit, even though folklore says "periodic → log₂3" — the folklore holds only for the naive LZ-complexity-per-block variant, not the exact estimator.
- Uniform iid draws over k cells: match length ≈ log_k(n) by chance, S ≈ log₂k. But chance matches slightly inflate Λ, so finite sequences *underestimate* — the −5.4% bias we measured at n=50k, k=8.

## Why the sandwich S_actual ≤ S_unc ≤ S_rand must hold

- **S_rand** assumes all N cells equally likely (know nothing),
- **S_unc** uses the histogram but ignores order (know frequencies),
- **S_actual** exploits order too (know everything compressible).

Each is the same sequence with strictly more exploitable structure removed. Our cohort respects it 100%; cohort means: S_rand 4.98 ≥ S_unc 4.02 ≥ S_actual 3.03 bits.

Fano then converts S_actual into Π_max — the "no algorithm will ever do better than this" ceiling of ~0.637 (cohort mean) that our Markov (0.231) and Transformer (0.260) top-1 accuracies are still climbing toward.
