# Exploratory PDFB-range coordinate construction (2026-07-30)

## Result

The locked raw P4 directional arrays cannot provide 222,360 independently
writable coefficients. This is a rank limitation, not a filter-search or
numerical-precision problem.

An exact, finite-cost alternative is available without lowering the locked
reconstruction or writability thresholds:

- parameterize the valid P4 Laplacian residual by the three critical 9-7
  wavelet high-pass arrays (`LH`, `HL`, `HH`);
- do the same for P3;
- map each valid residual to and from the locked four-channel `pkva`
  directional bank;
- expose the resulting six arrays as **independent multiscale PDFB-range
  coordinates**, not as raw directional-array coefficients.

Their capacity is

```text
P4: 3 * 256 * 256 = 196,608
P3: 3 * 128 * 128 =  49,152
                         -------
                          245,760
required                  222,360
unused                     23,400
```

The construction was executed on CPU8 with the real Minh Do toolbox. It passed
18 unit-coordinate probes and a dense, exactly 222,360-coordinate sign trial.

## Why raw P4 fails

At one Laplacian-pyramid level, let:

- `H` be the low-pass analysis and 2:1 downsampling operator;
- `G` be the corresponding upsampling and synthesis operator;
- `Q = I - G H` be the valid-detail projection;
- `T` be the invertible critical `pkva` directional analysis operator.

For the perfect-reconstruction filter pair, `H G = I`. Therefore:

```text
Q^2 = (I - GH)^2 = I - GH = Q
rank(Q) = N - N/4 = 3N/4
```

The raw directional write/read map is similar to this projection:

```text
P = T Q T^-1
```

so it has the same rank. At P4, `N = 512^2`, hence:

```text
rank(P4) = 3 * 512^2 / 4 = 196,608
```

No preconditioner can create 222,360 independent P4-only coordinates because
the rank of every composed map remains at most 196,608. The observed raw
single-coefficient response is the expected projection response:

```text
minimum self gain        0.7176372469354391
maximum cross-talk       0.1450286248181030
maximum off-target L2    0.6034419426017464
```

Scaling or iterating a raw impulse cannot remove this missing dimension. A
solver could make a small sampled subset look good, but it cannot provide a
full-rank 222,360-slot contract.

## Closed-form multiscale coordinate map

Let `W` be the one-level critical 9-7 wavelet bank already shipped in the
Contourlet toolbox as `wfb2dec`/`wfb2rec`. For a valid detail residual `d`,
the `LL` output is zero up to floating-point error. Define:

```text
decode_level(c_dir):
    d = dfbrec_l(c_dir, "pkva")
    [LL, LH, HL, HH] = wfb2dec(d, h_9_7, g_9_7)
    require LL approximately 0
    return [LH, HL, HH]

encode_level([LH, HL, HH]):
    d = wfb2rec(0, LH, HL, HH, h_9_7, g_9_7)
    return dfbdec_l(d, "pkva", 2)
```

The two maps are inverses on the valid PDFB detail range. They use all of the
locked machinery:

- pyramidal filter `9-7`;
- directional filter `pkva`;
- directional schedule `[2,2,2,2]`;
- real `pdfbdec`/`pdfbrec`;
- real `dfbdec_l`/`dfbrec_l`;
- the toolbox's critical 9-7 wavelet pair.

This is a basis/range-coordinate change, not an approximation and not an
iterative optimization. Its cost is linear in the number of pixels and it
needs one ordinary analysis/synthesis path per image.

## Revised Stage-0 checks

The raw inventory and raw-projection diagnostics should remain in the evidence,
but raw-impulse writability must not be reported as the writability of the new
coordinate scheme. The revised gate should separately record:

1. the unchanged raw PDFB band inventory and full reconstruction error;
2. the mathematical rank certificate for P3 and P4;
3. six virtual-band identities, shapes, and exact capacity;
4. maximum absolute `LL` leakage when decoding valid P3/P4 residuals;
5. at least three unit probes in each of the six virtual bands;
6. self gain, cross-talk, and off-target L2 measured after virtual decoding;
7. a dense exactly 222,360-slot sign round trip;
8. hashes of the toolbox, coordinate-map source, selection map, and evidence.

The numerical thresholds remain unchanged:

```text
reconstruction max error <= 1e-8
self gain               >= 0.99
cross-talk               <= 0.01
off-target L2 ratio      <= 0.05
probes per virtual band  >= 3
required slots            = 222,360
```

## CPU8 evidence

Exploratory implementation:

```text
scripts/explore_pdfb_multiscale_coordinates_20260730.m
```

Server evidence:

```text
/srv/ctsteg/evidence/pdfb-multiscale-coordinates-exploratory-20260730.json
```

Observed result:

```text
candidate coordinates            245,760
unit probes                             18
minimum self gain          0.9999999999997513
maximum cross-talk         4.973799150320701e-13
maximum off-target L2      5.715111265072498e-12
dense selected slots                    222,360
dense sign errors                             0
dense maximum error        6.821210263296962e-13
reconstruction max error   1.699618223938160e-11
overall exploratory pass                       true
```

SHA-256 values on CPU8:

```text
script:
6ab4c42dce62d4382098d5e83383d4c66cb4c5700cb874f5e36bf59139078525

evidence:
403f0feb6f42aa579250a14a8dcc4dc56fed6d744feeb12b9d50a2f56e3c0ae8
```

The locked, non-exploratory Stage-0 v2 implementation is:

```text
scripts/audit_pdfb_multiscale_stage0_v2.m
```

The final CPU8 evidence produced from that source is:

```text
/srv/ctsteg/evidence/pdfb-multiscale-stage0-v2-FINAL2-20260730T125401Z.json
```

Its identities are:

```text
Stage-0 v2 script SHA-256:
5e6569a12407d321cd6ad2e12f43cda63dc6e58b64501e7fe2f3de28497efc4c

Stage-0 v2 evidence SHA-256:
3908b492ff486fee78ee06327230637978de8be7263f827135d0ea2d76fb4a39
```

That evidence has `schema=2`, `runtime_verified=true`,
`profile=octave_pdfb_range_coordinates_v2`, `exploratory=false`, and
`author_equivalence_claimed=false`. It records the runtime executable and a
sorted, relative-path SHA-256 inventory for all 72 regular files recursively
under the locked toolbox root. The complete-tree digest is:

```text
29cb403a6e41d3ad8e6e9b7956098d2fdaa872749162f75187c9285aef5ad0c9
```

An independent Python traversal matched all 72 path/hash pairs exactly, with
no missing or extra entry. The embedded script hash was also independently
checked against the server file after the run.

FINAL2 additionally gates:

```text
12 first/last boundary probes:
  minimum self gain        0.9999999999997513
  maximum cross-talk       3.979039320256561e-13
  maximum off-target L2    5.568116883900321e-12

full 245,760-coordinate dense trial:
  sign errors              0
  maximum error            6.679101716144942e-13
  relative L2 error        7.593012214276008e-14

maximum valid-range leakage:
  observed                 1.965720395088333e-11
  threshold                1e-8
```

The exact 222,360-coordinate dense trial remains present and required.

## Pipeline integration contract

The final adapter should keep raw PDFB analysis private and expose the six
independent coordinate arrays to allocation, embedding, and extraction:

```text
P4: LH 256x256, HL 256x256, HH 256x256
P3: LH 128x128, HL 128x128, HH 128x128
```

Embedding adds the weighted sign pattern in these virtual arrays, reconstructs
valid P3/P4 residuals with `wfb2rec(0, ...)`, converts them to raw `pkva`
directional arrays with `dfbdec_l`, and finally calls the locked PDFB
synthesis. Extraction performs the inverse operations and thresholds the
stego-minus-cover virtual-coordinate difference. The existing PSNR calibration
can remain unchanged because it already calibrates the synthesized image
perturbation.

The adapter fingerprint must include:

- the exact coordinate scheme/version;
- P3/P4 level order;
- virtual-band order and shapes;
- `9-7`, `pkva`, and `[2,2,2,2]`;
- toolbox inventory hashes;
- the Stage-0 evidence hash;
- the deterministic 222,360-slot map hash.

## Mandatory claim boundary

This is a scientifically valid repair, but it is a protocol change. The old
protocol said “raw fourth-level directional coefficients.” The valid wording
is now:

> independent multiscale coordinates in the P3+P4 range of the locked
> 9-7/pkva PDFB

It must not be called 222,360 independently writable raw P4 coefficients, and
it must not be claimed as author-equivalent. The protocol/config/fingerprint
must receive a new version before article results are generated.
