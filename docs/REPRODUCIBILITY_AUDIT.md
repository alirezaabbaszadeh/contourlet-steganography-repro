# Reproducibility audit

## Scope

This audit covers the method, pseudocode, data declarations, metrics, attacks,
and numerical tables in Kumar, Singhal, and Sharma (Scientific Reports 16,
16771, 2026; DOI `10.1038/s41598-026-41168-0`). The supplied version of record
is 21 pages and contains no code-availability statement or supplementary
implementation.

The distinction used throughout this repository is:

- **reported**: a statement or number printed in the article;
- **interpreted**: a necessary implementation choice supported by the text;
- **proxy**: a transparent substitute where the required method is undisclosed;
- **reproduced**: independently obtained by executing this repository.

No reported number is labelled reproduced until the corresponding input,
preprocessing, algorithm, and metric can be matched.

## Outcome-determining gaps and contradictions

| Location | Observation | Consequence | Repository treatment |
|---|---|---|---|
| Algorithm 1 | Loops run from row/column 0 to 255, while experiments use 512×512 images | Half of each dimension has no written rule | Vectorize over the full configured image; retain this as an interpretation |
| Algorithm 1 | `L1=GENERATE_LIST(1,512,3)` and `L2=GENERATE_LIST(511,0,-3)` select the same `1 mod 3` values on `[0,255]` | The AP branch `N/4+193` is unreachable | Tested by `pseudocode_reachability()` |
| `CODE_HP` | Output is defined only when `N` is in `L3=0..32`; no `else` exists | Ordinary odd-parity pixels above 32 have no encrypted value | Strict mode raises; interpreted mode applies the printed HP formula to all odd-parity pixels |
| Encryption prose vs algorithms | Prose mentions modulus operations, but none appears in the formulas | Datatype/range behavior cannot be inferred | No invented modulus is applied |
| Algorithms 1 and 4 | Intermediate rounding, integer casts, and clipping are absent | Early uint8 conversion makes AP/GP/HP many-to-one | Preserve `float64` until the configured stego quantization boundary |
| Algorithm 4 | The GP inverse branch calls `CODE_GP`, not `DECODE_GP` | Literal decryption is not an inverse | Treat as a typographical error and call the inverse |
| `DECODE_HP` | The `IF N` condition is incomplete and `N/(2-N)` is singular at 2 | Attacked coefficients can explode or change sign | Optional, explicit clipping to `2-1e-6` |
| Algorithms 2 and 3 | LPDFB pyramid and directional filter names are not stated | CT coefficients are implementation-dependent | Built-in backend is labelled a proxy |
| CT description | No boundary extension, phase, directional vector, or toolbox version is stated | Even nominally identical filters can differ at borders and scales | Every proxy parameter is stored in configuration |
| Algorithm 2 | “highest frequency sub-band” is not indexed; secret/coefficient shape mapping is absent | Multiple incompatible embeddings fit the prose | Provide `finest` and `all_details` policies |
| Recovery claim | Only high-frequency coefficients are said to be embedded, yet a full secret is shown as recovered | A missing low-pass cannot be reconstructed exactly | Provide literal no-low-pass and coherent low-pass controls |
| CT coefficient count | The paper reports `4*(256²+128²+64²+32²)=348,160` directional coefficients while calling PDFB subsampled | A critically sampled 512² transform cannot have this high-pass count in addition to a low-pass | Record actual proxy redundancy in every run |
| Figure 4 | Direction labels and the visible number of directional tiles do not consistently match | The directional schedule cannot be recovered from the figure | Do not infer hidden parameters from the artwork |
| Image storage | Experiments mention BMP but do not state whether the reconstructed stego is rounded before extraction | Quantization error is amplified by division by `alpha=0.15` | Separate float-control and 8-bit-transmission presets |
| Dataset | Cover names vary by section; secret-image file identifiers are absent | Exact pairs cannot be reconstructed | Downloader uses documented identifiers and flags the Jet mapping as unverified |
| Dataset | “Jet” is not a named entry in the current USC-SIPI Misc catalogue | Input identity is uncertain | F-16 is a labelled proxy only |
| PSNR equation | The typeset equation contains a duplicated logarithm token | Direct literal evaluation is undefined | Use the standard `10 log10(255²/MSE)` form described in prose |
| SSIM | Equation appears global, while common software uses local windows | Values depend on implementation | Report global and windowed SSIM separately |
| NCC equation | Printed denominator is `sum(Ic²)`, not the symmetric norm product | The printed value is not standard NCC | Report both `ncc` and `ncc_paper_equation` |
| Gaussian attack | Prose names variance levels 5, 10, and 20; Table 7 uses 5, 10, and 15 | One attack point is contradictory | Match Table 7 and treat values as variance, not standard deviation |
| Crop attack | Prose says 10%, 25%, and 40% removed; Table 10's last first-column value is 75 while keep-fraction is 0.60 | The last row is internally inconsistent | Use keep-fractions 0.90, 0.75, 0.60 and identify the final removal as 40% |
| Geometric attacks | Padding, interpolation, registration, and post-attack dimensions are absent | Rotation/crop results are not uniquely defined | Bilinear rotation without registration; central crop with zero fill |
| JPEG attack | Codec, chroma mode, library, and save/reload pipeline are absent | Quality factors are not cross-library identical | Pillow grayscale JPEG with fixed options |
| Timing | Only hardware, MATLAB, and five-run averages are reported | No warm-up, toolbox, or code path can be checked | Do not compare runtime claims across environments |

## Reported targets

The values transcribed for audit are stored in `PAPER_TARGETS.csv`. They are
targets, not fixtures: tests must not be weakened or parameters tuned merely
to make a small benchmark reproduce a published average.

Reported headline averages are:

- cover/stego PSNR: 45.5 dB;
- cover/stego SSIM: 0.9837;
- extracted-secret BER: 0.0020;
- cover/stego NCC: 0.9951.

## What is verified here

- AP/GP/HP interpreted mapping is numerically invertible in float arithmetic;
- the article's L1/L2 reachability defect is machine-checked;
- strict HP behavior fails exactly where the pseudocode is undefined;
- proxy analysis/synthesis reconstructs analyzed images to numerical precision;
- all-coefficient float embedding/extraction is reversible;
- 8-bit stego quantization causes measurable recovery loss;
- attacks and random seeds are deterministic;
- metrics have identity and shape tests.

These facts validate this implementation's internal behavior. They do not
validate the missing author implementation.

## Minimum information needed for exact reproduction

The following should be requested from the authors before asserting exact
reproduction:

1. complete MATLAB source and toolbox/version;
2. `pfilter`, `dfilter`, `nlevs`, boundary mode, and exact subband indices;
3. the full AP/GP/HP functions, including all `else` branches, modulus,
   datatype, rounding, and clipping;
4. exact USC-SIPI file identifiers and cover-secret pairing matrix;
5. whether low-pass secret coefficients are embedded;
6. image save/reload points and formats;
7. exact MATLAB functions/options for SSIM, BER, NCC, noise, JPEG, rotation,
   crop, and any registration;
8. random seeds and the raw per-run outputs underlying Tables 3-11.

