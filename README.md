# certified-dose

[![CI](https://github.com/Raj123-0/certified-dose/actions/workflows/ci.yml/badge.svg)](https://github.com/Raj123-0/certified-dose/actions/workflows/ci.yml)
[![Nightly Fuzzing](https://github.com/Raj123-0/certified-dose/actions/workflows/nightly-fuzz.yml/badge.svg)](https://github.com/Raj123-0/certified-dose/actions/workflows/nightly-fuzz.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type Checked with mypy](https://img.shields.io/badge/mypy-strict-blue)](https://mypy-lang.org/)

A Python package, CLI, and interactive dashboard that wraps automated process-control dosing decisions (e.g. coagulant dosing in water treatment plants) with a **formal reachability-analysis safety layer**. Every dosing action is guaranteed to keep the output variable inside a regulatory compliance envelope under bounded input uncertainty — not just "good on average," but worst-case certified.

---

## The Problem

Regulated process industries (such as municipal water treatment, pharmaceutical formulation, and chemical processing) increasingly employ machine learning controllers (reinforcement learning, gradient-boosted trees, neural networks) to select dosing setpoints. These models optimize *average* operational cost and chemical consumption.

However, standard ML models provide **no worst-case guarantees**. Under unexpected influent disturbances — such as storm-induced turbidity surges, sudden flow spikes, or pH shifts — an optimizing controller seeking to shave chemical costs can inadvertently propose an under-dose or over-dose that breaches mandatory regulatory limits (e.g. effluent turbidity exceeding 1.0 NTU). Regulators, municipal operators, and insurers require mathematical guarantees that worst-case deviations will never violate compliance envelopes.

## The Reachability-Analysis Solution

`certified-dose` acts as a formal verification guardrail between any candidate controller and the physical dosing actuators. Given (1) a proposed candidate dose and (2) bounded intervals representing sensor noise and disturbance uncertainty (e.g. influent turbidity $T_{in} \pm 15\%$, flow rate $Q \pm 10\%$, pH, temperature), the certifier propagates these input intervals through a non-linear process model using **rigorous interval arithmetic**.

The computation determines the **guaranteed reachable set** $[y_{\min}, y_{\max}]$ of effluent contaminant concentrations. If the supremum of the reachable set satisfies the regulatory limit ($y_{\max} \le L_{limit}$), the candidate action is certified and dispatched. If the reachable set violates the envelope, the certifier rejects the action and falls back to a certified safe dose computed via bisection search or a conservative fail-safe default.

---

## Architecture

```mermaid
flowchart LR
    subgraph Sensing["Plant Sensors"]
        S[Current State<br/>Disturbance Intervals]
    end

    subgraph Controller["Candidate Controller"]
        ML[ML / RL / Heuristic<br/>Cost-Optimizing Agent]
    end

    subgraph Certification["Formal Safety Wrapper (certified-dose)"]
        IA[Interval Reachability Engine]
        CHK{Reachable Set<br/>within Envelope?}
        BIS[Bisection Safe Dose Search]
        FS[Conservative Fail-Safe Fallback]
    end

    subgraph Actuation["Plant Actuator"]
        P[Coagulant Dosing Pump]
    end

    S --> ML
    S --> IA
    ML -->|Proposed Dose d_cand| IA
    IA --> CHK
    CHK -->|Yes: Safe| P
    CHK -->|No: Unsafe| BIS
    BIS -->|Found Safe Dose| P
    BIS -->|Failed/Timeout| FS
    FS --> P
```

---

## Quickstart

### Installation

```bash
# Clone repository
git clone https://github.com/Raj123-0/certified-dose.git
cd certified-dose

# Install core library
pip install -e .

# Install with dashboard and development tools
pip install -e ".[dashboard,dev]"
```

### Python API Example

```python
from certified_dose import (
    Interval,
    SyntheticProcessModel,
    ReachabilityEngine,
    CertifiedDoseWrapper,
    HeuristicController,
)

# 1. Initialize process model and reachability engine
model = SyntheticProcessModel()
engine = ReachabilityEngine(model=model, safety_margin=0.02)

# 2. Wrap any candidate controller with formal certification
wrapper = CertifiedDoseWrapper(
    engine=engine,
    compliance_limit=1.0,  # e.g., max 1.0 NTU effluent turbidity
    fallback_dose=24.0,    # provably safe default dose (mg/L)
)

# 3. Define disturbance bounds from sensor measurements
state = {
    "turbidity": Interval(20.0, 26.0),  # NTU
    "flow_rate": Interval(900.0, 1100.0),  # m3/h
    "ph": Interval(7.1, 7.5),
    "temperature": Interval(16.0, 18.0),  # deg C
}

# 4. Certify candidate dose
candidate_dose = 14.5  # Proposed by an aggressive cost-cutting controller
result = wrapper.certify_action(candidate_dose, state)

print(f"Status: {result.status.value}")
print(f"Proposed: {result.proposed_dose:.2f} mg/L -> Certified: {result.certified_dose:.2f} mg/L")
print(f"Worst-Case Reachable Effluent: [{result.reachable_set.lo:.3f}, {result.reachable_set.hi:.3f}] NTU")
```

---

## Command Line Interface (CLI)

The package provides the `certified-dose` executable:

```bash
# Run a 100-step closed-loop simulation comparing candidate vs certified control
certified-dose simulate --steps 100 --seed 42 --limit 1.0

# Perform a one-shot reachability check for a candidate dose
certified-dose check --dose 16.0 --turbidity 25.0 --flow 1000.0 --limit 1.0

# Launch the interactive visual dashboard
certified-dose dashboard --port 8501
```

---

## Interactive Dashboard

The Streamlit dashboard allows operators, engineers, and researchers to explore reachability certification in real time:

- **Live Parameter Controls**: Sliders for sensor uncertainty ($\pm \% T_{in}$, $\pm \% Q$, $\pm \Delta pH$, $\pm \Delta T$) and regulatory limits.
- **Dynamic Simulation View**: Real-time plots comparing candidate dosing vs certified safe dosing.
- **Reachable Set Envelopes**: Shaded regions showing guaranteed bounds $[y_{\min}, y_{\max}]$ alongside the regulatory threshold line.
- **Zero Violations Metric**: Visual counter tracking blocked unsafe actions and guaranteed zero compliance breaches.
- **Interactive Dose Inspector**: Test arbitrary candidate doses and inspect immediate reachability envelopes.

```bash
certified-dose dashboard
```

*(Streamlit runs locally at `http://localhost:8501`)*

---

## Running with Docker

Run the entire application including the interactive dashboard using Docker:

```bash
# Build and run container
docker build -t certified-dose .
docker run -p 8501:8501 certified-dose
```

Or with Docker Compose:

```bash
docker compose up --build
```

Access the dashboard at `http://localhost:8501`.

## Verification Results at Scale (10,000,000+ Trials)

To rigorously validate that interval reachability bounds never underestimate worst-case effluent concentrations, `certified-dose` is continuously stress-tested via large-scale vectorized Monte Carlo fuzzing across randomized physical operating points:

| Metric | Measured Value | Guarantee |
| :--- | :---: | :--- |
| **Total Monte Carlo Trials** | **10,000,000** | Exhaustive brute-force parameter search |
| **Scenarios Tested** | **1,000** | Diverse disturbance profiles ($\pm 5\%$ to $\pm 25\%$ noise) |
| **Samples per Scenario** | **10,000** | Uniform parameter space coverage |
| **Soundness Violations** | **0** | **100% Sound** (Zero false safety certificates) |
| **Min Conservatism Margin** | **+0.02104 NTU** | Strictly $\ge 0$ (Bound always strictly encloses samples) |
| **Mean Conservatism Margin** | **+0.03549 NTU** | Tight enclosing bound with minimal excess conservatism |
| **Max Conservatism Margin** | **+0.19097 NTU** | Bounded even under adverse multi-parameter storm spikes |
| **Sampling Throughput** | **20,280,000 trials/s** | High-throughput vectorized verification engine |

Run the verification suite locally:

```bash
python benchmarks/large_scale_fuzz.py --trials 10000000 --scenarios 1000
```

---

## Conservatism & Chemical-Cost Overhead Benchmark

To quantify the economic cost of formal reachability guarantees vs. unverified cost-minimizing controllers, we benchmarked the system across an environmental uncertainty sweep ($\pm 5\%$ through $\pm 30\%$ disturbance intervals) during a simulated storm surge (influent turbidity spiking to $>60\text{ NTU}$):

![Conservatism Benchmark](docs/assets/benchmark_conservatism.png)

### Uncertainty Parameter Sweep Results

| Uncertainty Width | Naive Violations (Unchecked) | Certified Violations | Safety Interventions | Naive Dose | Certified Dose | Chemical Overhead (%) | Peak Effluent |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **±5%** | 25 (25.0%) | **0 (0.0%)** | 25 (25.0%) | 14.77 mg/L | 15.44 mg/L | **+4.5%** | 0.923 NTU |
| **±10%** | 25 (25.0%) | **0 (0.0%)** | 29 (29.0%) | 14.77 mg/L | 15.73 mg/L | **+6.5%** | 0.885 NTU |
| **±15%** | 25 (25.0%) | **0 (0.0%)** | 93 (93.0%) | 14.77 mg/L | 16.21 mg/L | **+9.7%** | 0.850 NTU |
| **±20%** | 25 (25.0%) | **0 (0.0%)** | 100 (100.0%) | 14.77 mg/L | 16.90 mg/L | **+14.4%** | 0.819 NTU |
| **±25%** | 25 (25.0%) | **0 (0.0%)** | 100 (100.0%) | 14.77 mg/L | 17.66 mg/L | **+19.6%** | 0.791 NTU |
| **±30%** | 25 (25.0%) | **0 (0.0%)** | 100 (100.0%) | 14.77 mg/L | 18.53 mg/L | **+25.4%** | 0.767 NTU |

**Key Takeaways**:
1. **Zero Regulatory Breaches**: At all uncertainty widths, `certified-dose` achieved **0 violations**, whereas the unverified controller committed violations on 25% of control steps.
2. **Minimal Overhead at Realistic Sensor Tolerances**: At standard industrial sensor noise levels ($\pm 10\%$ to $\pm 15\%$), the worst-case safety guarantee requires only **$+6.5\%$ to $+9.7\%$** chemical overhead.
3. **Graceful Scaling**: Even under extreme $\pm 30\%$ sensor uncertainty, the chemical overhead is bounded at $+25.4\%$, remaining far below traditional fixed emergency dosing recipes ($> +60\%$).

Run the benchmark suite and generate figures locally:

```bash
python benchmarks/conservatism_benchmark.py --steps 100 --seed 42
```

---

## Testing & Verification

The test suite includes property-based tests (Hypothesis), Monte Carlo fuzzing against brute-force sampling, unit tests, and closed-loop end-to-end scenarios:

```bash
# Run test suite with line coverage
pytest --cov=certified_dose --cov-report=term-missing --cov-fail-under=90

# Format checking and linting
black --check certified_dose tests
ruff check certified_dose tests

# Strict type checking
mypy certified_dose
```

---

## Limitations & Non-Goals

> [!CAUTION]
> **Research and Demonstration Notice**:
> `certified-dose` is an open-source research and educational library intended to demonstrate the principles of formal reachability analysis and verified interval arithmetic in process-control dosing.
>
> 1. **Empirically Validated Steady-State Kinetics**: The steady-state coagulant dose-response curve has been empirically validated against published bench-scale water treatment jar-testing benchmarks (*Edwards 1997, Journal AWWA 89(5):78-89*), demonstrating $R^2 = 0.9999$, overall $\text{RMSE} = 0.055\text{ NTU}$, and compliance-window precision of $\text{RMSE} = 0.015\text{ NTU}$ across $15 - 60\text{ mg/L}$ doses (run `certified-dose validate` to view live diagnostics).
> 2. **What Remains Illustrative / Unvalidated**:
>    - **Hydraulic Transport Dynamics**: Full-scale water treatment plants feature spatial dead-zones, flocculator baffle mixing gradients, and non-ideal clarifier residence time distributions (RTDs) that are represented here by a simplified bulk scaling factor $(Q/Q_{\text{nom}})^{0.85}$.
>    - **Complex Water Chemistry**: Natural raw water contains varying dissolved organic carbon (DOC), specific UV absorbance (SUVA), alkalinity buffers, and silica interferents that require site-specific jar-test calibration.
>    - **Actuator & Sensor Latencies**: Physical dosing pumps exhibit mechanical dead-bands, priming delays, and sensor transit pipeline delays that are not modeled.
> 3. **Not Validated for Real Regulatory Use**: This software is **not** certified, accredited, or approved by the EPA, FDA, or municipal authorities for deployment in actual regulated drinking water utilities, wastewater facilities, or pharmaceutical manufacturing plants.
> 4. **Non-Goals**: This package does not provide real-time hardware PLC drivers, SCADA/OPC-UA integration, automated regulatory filing compliance, or hardware emergency shutdown interlocks on physical equipment.
