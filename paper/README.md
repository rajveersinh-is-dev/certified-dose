# Certified-Dose Research Paper

This directory contains the LaTeX source and bibliographic data for the technical systems paper:

> **Certified-Dose: A Formally Verified Reachability Wrapper for Safety-Critical Process Control Dosing with Lessons from Real-World Validation**  
> *Target Venues*: arXiv (cs.SY, cs.LO, cs.CE), IEEE Transactions on Control Systems Technology, or ACM/IEEE ICCPS.

---

## Directory Structure

```text
paper/
├── certified_dose_paper.tex    # Primary LaTeX source (self-contained article class)
├── references.bib              # BibTeX bibliography with real, verified citations
└── README.md                   # Rebuild instructions and data provenance mapping
```

---

## Rebuilding the PDF

The paper is written using standard LaTeX packages (`amsmath`, `amssymb`, `amsthm`, `booktabs`, `cite`, `microtype`, `hyperref`, `tabularx`) supported by all modern TeX distributions (TeX Live, MiKTeX, MacTeX) and Overleaf.

### 1. Using `latexmk` (Recommended)

```bash
cd paper
latexmk -pdf certified_dose_paper.tex
```

### 2. Using `pdflatex` + `bibtex` Manual Pipeline

```bash
cd paper
pdflatex certified_dose_paper.tex
bibtex certified_dose_paper
pdflatex certified_dose_paper.tex
pdflatex certified_dose_paper.tex
```

### 3. Using Docker (Zero Local Setup)

```bash
docker run --rm -v ${PWD}/paper:/work -w /work texlive/texlive:latest pdflatex certified_dose_paper.tex
```

### 4. Overleaf

1. Create a new blank project on [Overleaf](https://www.overleaf.com).
2. Upload `certified_dose_paper.tex` and `references.bib`.
3. Set the compiler to **pdfLaTeX** and compile.

---

## Data and Experimental Provenance

Every numeric metric, benchmark score, and empirical result presented in the paper traces directly to existing, reproducible artifacts in the `certified-dose` repository:

| Paper Section / Table | Content | Source in Repository | Command to Re-run / Verify |
| :--- | :--- | :--- | :--- |
| **Table 1** | Multi-Tier Verification Stack | Core test suite & static tools | `pytest -q`, `pytest --cov`, `mypy --strict certified_dose` |
| **Section 4.5** | AST Mutation Testing (100% kill score) | `cosmic-ray.toml` | `cosmic-ray run --config cosmic-ray.toml` |
| **Section 5.1.1** | 10M-Trial Monte Carlo Fuzzing | `benchmarks/results_fuzz_10m.json` | `python benchmarks/large_scale_fuzz.py --trials 10000000` |
| **Table 2** | Execution Latency & WCET Profiling | `benchmarks/results_latency.json` | `python benchmarks/latency_benchmark.py` |
| **Table 3** | Empirical Literature Jar Tests | `certified_dose/validation.py` | `certified-dose validate --dataset all` |
| **Table 4** | Real-World USGS NWIS Telemetry (5,727 records) | `benchmarks/results_real_world.json` | `python benchmarks/real_world_benchmark.py` |
| **Section 6 & 7** | Algal Bloom Breakdown & 854 records (29.84%) reclassification | `docs/REAL_WORLD_EVALUATION.md`, `tests/test_ph_validity.py` | `pytest tests/test_ph_validity.py` |
| **Table 5** | EPA Method 180.1 Sensor Uncertainty Sensitivity | `benchmarks/results_sensor_uncertainty.json` | `python benchmarks/sensor_uncertainty_benchmark.py` |

---

## Authorship and Research Notice

This paper was prepared as part of the `certified-dose` open-source verification initiative. In accordance with the repository's **Research and Demonstration Notice**, this paper and the accompanying software represent an academic prototype for peer review and research evaluation. It has not received regulatory accreditation from the U.S. EPA, FDA, or municipal authorities, and must not be used as the sole safety mechanism in operating physical water treatment plants without on-site pilot validation.
