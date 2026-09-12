# Contourlet-Domain Image Data Hiding for Visual Communication: Adaptive Allocation and Validity-Aware Recovery

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Target: JVCIR](https://img.shields.io/badge/Journal-JVCIR%20(Elsevier)-orange.svg)](https://www.sciencedirect.com/journal/journal-of-visual-communication-and-image-representation)
[![Release: v1.0.0--jvcir--submission](https://img.shields.io/badge/Release-v1.0.0--jvcir--submission-brightgreen.svg)](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/releases/tag/v1.0.0-jvcir-submission)
[![Artifact Tag](https://img.shields.io/badge/Artifact%20Tag-FINAL--5J--RESULTS--20260812-blue.svg)](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/releases/tag/FINAL-5J-RESULTS-20260812)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-teal.svg)](https://www.python.org/)
[![Tests: 41 Passed](https://img.shields.io/badge/Tests-41%20Passed-success.svg)](tests/)

Official research artifact, verification pipeline, and reproducible codebase for the manuscript:

> **Contourlet-Domain Image Data Hiding for Visual Communication: Adaptive Allocation and Validity-Aware Recovery**  
> **Authors:** Alireza Abbaszadeh$^{1,*}$, Mohammad Hossein Moattar$^{1}$  
> $^{1}$ *Department of Computer Engineering, Mashhad Branch, Islamic Azad University, Mashhad, Iran*  
> $^*$ *Corresponding author: alireza.abbaszadeh8558@iau.ir*  
> **Target Journal:** *Journal of Visual Communication and Image Representation* (JVCIR), Elsevier  
> **Official Release:** [`v1.0.0-jvcir-submission`](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/releases/tag/v1.0.0-jvcir-submission)  
> **Immutable Results Tag:** [`FINAL-5J-RESULTS-20260812`](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/releases/tag/FINAL-5J-RESULTS-20260812) | **Results Branch:** [`results/final-5j-20260812`](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/tree/results/final-5j-20260812)

---

## 📌 Executive Summary

Digital image transmission across open communication channels necessitates robust security, high visual fidelity, and resilience to packet corruption and transmission noise. This repository hosts the complete, audited, and deterministic implementation of our visual data-hiding framework designed for noisy communication channels:

1. **Semantic Base/Detail Representation:** Hierarchical partitioning of secret images into structural base and detail layers, enabling progressive image reconstruction even under severe channel degradation.
2. **Fixed-Budget Reed–Solomon Unequal Error Protection (UEP):** An asymmetric channel-coding design that allocates heavy redundancy to critical base structural bits and header layers while preserving transmission bandwidth.
3. **Calibration-Driven Adaptive Bit Allocation:** An energy-driven allocation mechanism that dynamically steers message payloads across multidirectional high-frequency contourlet subbands based on local directional energy and human visual system (HVS) masking characteristics.
4. **Transform Basis Capacity Audit:** A mathematical and empirical proof establishing that exactly 245,760 coordinates out of 327,680 raw directional entries in the pyramidal directional filter bank (PDFB) are independently writable, defining the rigorous capacity bound of the embedding domain.
5. **Validity-Aware Recovery Analysis:** Tracking explicit recovery states (Complete, Base-Only, Header-Corrupt) across 50 preregistered image pairs (COCO 2017 validation), 530 embeddings, and 8,420 channel evaluations under matched cover–stego distortion.

---

## 🔬 Controlled Configuration Matrix (Ablation Study)

To isolate individual mechanism effects without payload or fidelity confounds, all configurations are matched for full protected-bit load (61,440 bits) and identical embedding distortion ($44.02 \pm 0.81$ dB PSNR):

| Config | Name | Allocation Scheme | Channel Coding | Research Question / Mechanism Isolated |
|:---:|:---:|:---:|:---:|:---|
| **C0** | Uniform + EEP | Uniform | Equal Error Protection | Baseline reference: no spatial adaptation, symmetric protection |
| **C1** | Uniform + UEP | Uniform | Unequal Error Protection | Isolates the pure effect of semantic UEP without directional guidance |
| **C2** | Adaptive + EEP | Adaptive Energy | Equal Error Protection | Isolates the pure effect of adaptive directional allocation |
| **C3** | **Proposed Method** | **Adaptive Energy** | **Unequal Error Protection** | **Full proposed architecture: synergistic interaction of adaptive allocation and UEP** |
| **C4** | Base-First Control | Base Priority | UEP Heavy | Benchmark isolating early base bitstream placement |

---

## 📊 Dataset & Forensic Verification

- **Evaluation Corpus:** 50 preregistered image pairs deterministically selected from the Microsoft COCO 2017 validation dataset (CC BY 2.0 license), spanning diverse natural textures, frequency distributions, and edge densities.
- **Channel Matrix:** 8,420 systematic channel evaluations testing:
  - Additive White Gaussian Noise (AWGN) across SNR levels ($\sigma \in \{1, 2, 5, 10, 15\}$).
  - Lossy JPEG compression across quality factors ($QF \in \{90, 80, 70, 60, 50, 40\}$).
  - Median and Gaussian spatial filtering.
  - Salt-and-pepper impulse noise.
- **Checksums & Audit Trail:** 100% SHA-256 verified manifests for input images, directional subband arrays, and evaluation records (`SHA256SUMS-curated.txt`).

---

## 📁 Repository Structure

```text
├── configs/              # TOML experiment configurations for C0-C4 and benchmark protocols
├── docs/                 # Methodology documentation, capacity proof, and architecture specs
├── examples/             # Sample image pair pairing manifests (reproducible IDs)
├── scripts/              # Dataset downloaders, verification tools, and figure generation
├── src/ctsteg/           # Core Python scientific package:
│   ├── adaptive.py       # Directional subband energy analysis & adaptive bit-allocation
│   ├── attacks.py        # Differentiable channel attack models (JPEG, AWGN, filtering)
│   ├── benchmark.py      # Batch evaluation harness and metric calculation
│   ├── bitplanes.py      # Semantic bitplane slicing and binary serialization
│   ├── config.py         # Type-safe configuration schemas
│   ├── ecc.py            # Reed-Solomon codec and UEP bitstream packaging
│   ├── metrics.py        # PSNR, SSIM, NC, LPIPS, and bit-error-rate (BER) evaluators
│   ├── pipeline.py       # End-to-end data-hiding transport pipeline
│   └── transform.py      # Multiscale Pyramidal Directional Filter Bank (PDFB) implementation
├── tests/                # 41 deterministic unit and integration test suites
├── pyproject.toml        # Build specifications and package dependencies
└── CITATION.cff          # Machine-readable scholarly citation metadata
```

---

## 🚀 Quickstart & Reproduction

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/alirezaabbaszadeh/contourlet-steganography-repro.git
cd contourlet-steganography-repro

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install package in editable development mode
pip install -e .
```

### 2. Run Test Suite

Verify complete test coverage (41 unit & integration tests):

```bash
python -m unittest discover -s tests -v
```

### 3. Inspect Evaluation Evidence

The full 8,420-row evaluation matrix and generated publication artifacts are preserved on the dedicated results branch and release:

- **Official Release:** [v1.0.0-jvcir-submission](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/releases/tag/v1.0.0-jvcir-submission)
- **Immutable Tag:** [FINAL-5J-RESULTS-20260812](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/releases/tag/FINAL-5J-RESULTS-20260812)
- **Results Data Branch:** [`results/final-5j-20260812`](https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/tree/results/final-5j-20260812)

---

## 📜 Citation

If you use this codebase, methodology, or results in your research, please cite our manuscript:

```bibtex
@article{AbbaszadehMoattar2026JVCIR,
  title   = {Contourlet-Domain Image Data Hiding for Visual Communication: Adaptive Allocation and Validity-Aware Recovery},
  author  = {Abbaszadeh, Alireza and Moattar, Mohammad Hossein},
  journal = {Journal of Visual Communication and Image Representation},
  year    = {2026},
  note    = {Elsevier. Official Artifact Release: \url{https://github.com/alirezaabbaszadeh/contourlet-steganography-repro/releases/tag/v1.0.0-jvcir-submission}}
}
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
