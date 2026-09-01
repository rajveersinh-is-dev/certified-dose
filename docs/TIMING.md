# Execution Timing and Real-Time Latency Guarantees

## 1. Overview and Operational Significance

In process-control safety systems (such as chemical dosing in municipal water treatment, wastewater neutralization, and bioreactors), **timing guarantees are as critical as mathematical correctness**. A safety layer that computes provably correct bounds but blocks a control loop or introduces unbounded latency creates a severe cyber-physical hazard (actuator starvation, buffer overflows, or delayed response during storm surges).

This document formalizes the execution complexity, deterministic bounds, empirical latency benchmarks, and fail-safe timeout mechanisms of `certified-dose`.

---

## 2. Computational Complexity Profile

`certified-dose` relies exclusively on closed-form interval arithmetic rather than iterative numerical optimization, nonlinear solvers, or stochastic sampling during runtime certification:

| Operation | Mathematical Formulation | Time Complexity | Memory Complexity | Notes |
| :--- | :--- | :---: | :---: | :--- |
| **Interval Addition / Subtraction** | $[\underline{x} \pm \underline{y}, \overline{x} \pm \overline{y}]$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | 2 float operations |
| **Interval Multiplication** | $[\min(P), \max(P)]$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | 4 pairwise products |
| **Interval Monotonic Powers** | $[\underline{x}^p, \overline{x}^p]$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | Exact endpoint evaluation |
| **Reachability Forward Pass** | Natural interval evaluation $f(d, \mathbf{I})$ | $\mathcal{O}(K)$ | $\mathcal{O}(1)$ | $K$ process arithmetic ops ($\approx 25$ ops) |
| **Compliance Enclosure Check** | $\overline{\mathcal{R}} \le L_{\text{limit}}$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | Single float comparison |
| **Bisection Fallback Search** | Coarse grid + bisection refinement | $\mathcal{O}(N_{\text{iter}} \cdot K)$ | $\mathcal{O}(1)$ | Strictly bounded by $N_{\text{iter}}$ and $T_{\text{cap}}$ |

Because the forward reachability evaluation contains **zero loops, zero dynamic allocations, and zero unbounded recursions**, its computational execution profile is deterministic.

---

## 3. Empirical Latency Benchmarks

Empirical timings were measured across **10,000 single-check trials** and **4,500 bisection search sweeps** across $\pm 5\%$, $\pm 15\%$, and $\pm 30\%$ uncertainty widths (Intel Core / AMD x86_64, Windows / Linux):

### A. Single Certification Check (Nominal Path: Candidate Accepted)

When a candidate dose satisfies the compliance limit under bounded uncertainty, the certifier evaluates the forward reachability model once and returns immediately:

| Percentile | Latency ($\mu\text{s}$) | Latency ($\text{ms}$) | Throughput (Checks/sec) |
| :--- | :---: | :---: | :---: |
| **Minimum** | $20.3\,\mu\text{s}$ | $0.0203\,\text{ms}$ | $49,200\,\text{s}^{-1}$ |
| **Median (p50)** | **$22.6\,\mu\text{s}$** | **$0.0226\,\text{ms}$** | **$44,200\,\text{s}^{-1}$** |
| **Mean** | $22.8\,\mu\text{s}$ | $0.0228\,\text{ms}$ | $43,800\,\text{s}^{-1}$ |
| **p95** | $23.5\,\mu\text{s}$ | $0.0235\,\text{ms}$ | $42,500\,\text{s}^{-1}$ |
| **p99** | **$33.6\,\mu\text{s}$** | **$0.0336\,\text{ms}$** | **$29,700\,\text{s}^{-1}$** |
| **p99.9** | $48.1\,\mu\text{s}$ | $0.0481\,\text{ms}$ | $20,700\,\text{s}^{-1}$ |
| **Worst-Case Execution Time (WCET)** | **$81.0\,\mu\text{s}$** | **$0.0810\,\text{ms}$** | **$12,300\,\text{s}^{-1}$** |

> **Key Takeaway**: A single certification check executes in under **$35\,\mu\text{s}$** at the 99th percentile and has an empirical WCET under **$85\,\mu\text{s}$**.

---

### B. Bisection Fallback Search (Intervention Path: Candidate Rejected)

When an aggressive or faulty candidate controller proposes an unsafe dose, the safety wrapper rejects the dose and activates bisection fallback search to discover the lowest compliant setpoint:

| Configuration | Mean ($\text{ms}$) | Median ($\text{ms}$) | p95 ($\text{ms}$) | p99 ($\text{ms}$) | Max / WCET ($\text{ms}$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **$\pm 5\%$ Noise, 10 Iterations** | $0.29\,\text{ms}$ | $0.29\,\text{ms}$ | $0.37\,\text{ms}$ | $0.48\,\text{ms}$ | $0.64\,\text{ms}$ |
| **$\pm 5\%$ Noise, 25 Iterations (Default)** | **$0.59\,\text{ms}$** | **$0.57\,\text{ms}$** | **$0.65\,\text{ms}$** | **$0.77\,\text{ms}$** | **$1.57\,\text{ms}$** |
| **$\pm 5\%$ Noise, 50 Iterations** | $1.12\,\text{ms}$ | $1.08\,\text{ms}$ | $1.32\,\text{ms}$ | $1.80\,\text{ms}$ | $2.11\,\text{ms}$ |
| **$\pm 15\%$ Noise, 10 Iterations** | $0.29\,\text{ms}$ | $0.28\,\text{ms}$ | $0.34\,\text{ms}$ | $0.44\,\text{ms}$ | $0.62\,\text{ms}$ |
| **$\pm 15\%$ Noise, 25 Iterations (Default)** | **$0.63\,\text{ms}$** | **$0.62\,\text{ms}$** | **$0.72\,\text{ms}$** | **$0.83\,\text{ms}$** | **$1.22\,\text{ms}$** |
| **$\pm 15\%$ Noise, 50 Iterations** | $1.15\,\text{ms}$ | $1.13\,\text{ms}$ | $1.32\,\text{ms}$ | $1.72\,\text{ms}$ | $2.17\,\text{ms}$ |
| **$\pm 30\%$ Noise, 10 Iterations** | $0.27\,\text{ms}$ | $0.26\,\text{ms}$ | $0.33\,\text{ms}$ | $0.40\,\text{ms}$ | $0.61\,\text{ms}$ |
| **$\pm 30\%$ Noise, 25 Iterations (Default)** | **$0.61\,\text{ms}$** | **$0.58\,\text{ms}$** | **$0.73\,\text{ms}$** | **$0.84\,\text{ms}$** | **$0.94\,\text{ms}$** |
| **$\pm 30\%$ Noise, 50 Iterations** | $1.13\,\text{ms}$ | $1.11\,\text{ms}$ | $1.35\,\text{ms}$ | $1.64\,\text{ms}$ | $1.88\,\text{ms}$ |

---

## 4. Hard Latency Caps and Fail-Safe Timeout Invariants

To guarantee that computational delays cannot compromise plant safety:

1. **Hard Iteration Cap (`bisection_max_iter: int = 25`)**:
   The number of reachable evaluations during bisection search is strictly bounded by `bisection_max_iter`. It is impossible for the search loop to run unbounded.

2. **Hard Wall-Clock Timeout (`max_computation_time_ms: float = 50.0`)**:
   In addition to the iteration cap, `CertifiedDoseWrapper` monitors wall-clock elapsed time before each candidate evaluation. If cumulative computation exceeds `max_computation_time_ms`, the search is immediately aborted.

3. **Unconditional Safe Fallback on Timeout**:
   If the iteration cap or time budget is exceeded, the certifier does **not** crash or raise an uncaught exception. Instead, it returns:
   - `status`: `CertificationStatus.FAILED_SAFE_FALLBACK`
   - `certified_dose`: `self.fallback_dose` (the pre-certified conservative plant default)
   - `reason`: `Bisection search time budget exceeded (XX.X ms >= 50.0 ms limit). Reverted to fail-safe default dose.`

---

## 5. Control Loop Feasibility Matrix

Industrial process automation runs at varied cycle frequencies depending on physical dynamics:

| System Type | Typical Loop Cycle ($T_{\text{cycle}}$) | `certified-dose` WCET | Margin Factor ($\frac{T_{\text{cycle}}}{\text{WCET}}$) | Feasibility Status |
| :--- | :---: | :---: | :---: | :--- |
| **Water Coagulation Plant** | $10\,\text{s} - 60\,\text{s}$ | $1.57\,\text{ms}$ | $>6,000\times$ | **Exceptional headroom** |
| **Wastewater CSTR pH Control** | $1\,\text{s} - 5\,\text{s}$ | $1.57\,\text{ms}$ | $>600\times$ | **Exceptional headroom** |
| **Fast Chemical Dosing Valve** | $100\,\text{ms}$ ($10\,\text{Hz}$) | $1.57\,\text{ms}$ | $>60\times$ | **Fully compatible** |
| **Embedded Industrial PLC Loop** | $10\,\text{ms}$ ($100\,\text{Hz}$) | $1.57\,\text{ms}$ | $>6\times$ | **Fully compatible** |
| **High-Speed Sensor Interface** | $1\,\text{ms}$ ($1000\,\text{Hz}$) | $0.081\,\text{ms}$ (Single) | $>12\times$ | **Compatible (Single Check)** |

---

## 6. Reproducing Latency Benchmarks

To reproduce the empirical benchmarks locally:

```bash
# Run full 10,000-trial benchmark
python benchmarks/latency_benchmark.py

# Run quick verification smoke test
python benchmarks/latency_benchmark.py --quick
```
Raw machine-readable latency data is emitted to [`benchmarks/results_latency.json`](../benchmarks/results_latency.json).
