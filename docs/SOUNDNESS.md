# Formal Soundness Proof and Safety Guarantees

This document establishes the mathematical proof that the reachability analysis engine in **`certified-dose`** provides a **sound over-approximation** of the physical process output. Specifically, we prove that for any candidate dose $d$, the computed upper bound of the reachable set is guaranteed to be greater than or equal to the worst-case true effluent value under all admissible disturbance realizations:

$$\overline{\mathcal{R}}(d) \ge \sup_{\theta \in \Theta} f(d, \theta)$$

where $\Theta$ is the bounded input uncertainty set and $f(d, \theta)$ is the true nonlinear process model.

---

## 1. Mathematical Preliminaries

### 1.1 Interval Inclusion Monotonicity

Let $\mathbb{IR}$ denote the set of closed, bounded real intervals:

$$\mathbb{IR} = \{ [\underline{x}, \overline{x}] \mid \underline{x}, \overline{x} \in \mathbb{R}, \underline{x} \le \overline{x} \}$$

A function $\left[ g \right] : \mathbb{IR}^n \to \mathbb{IR}$ is an **inclusion function** (or interval extension) of a continuous real-valued function $g: \mathbb{R}^n \to \mathbb{R}$ if:

$$\forall x \in X \subseteq \mathbb{R}^n, \quad g(x) \in \left[ g \right]\left(X\right)$$

**Theorem 1 (Fundamental Theorem of Interval Arithmetic; Moore, 1966):**
If a rational function $g(x_1, \dots, x_n)$ is evaluated by replacing all real variables $x_i$ with intervals $X_i$ and all arithmetic operations with their corresponding interval arithmetic operations, the resulting natural interval extension $\left[ g \right]\left(X_1, \dots, X_n\right)$ satisfies inclusion monotonicity:

$$\forall x \in X, \quad g(x) \in \left[ g \right]\left(X\right)$$

Furthermore, if $X^{(1)} \subseteq X^{(2)}$, then $\left[ g \right]\left(X^{(1)}\right) \subseteq \left[ g \right]\left(X^{(2)}\right)$.

### 1.2 Soundness Definition

Let $L_{\text{compliance}} \in \mathbb{R}_{> 0}$ be the statutory maximum permissible effluent concentration (e.g. $1.0\text{ NTU}$). A certification decision is **sound** if and only if:

$$\text{Certified Safe}(d) \implies \left( \forall \theta \in \Theta, \; f(d, \theta) \le L_{\text{compliance}} \right)$$

If an algorithm certifies an action $d$ whose true output $f(d, \theta^{\star}) > L_{\text{compliance}}$ for some physical realization $\theta^{\star} \in \Theta$, the algorithm is **unsound** (false safety certificate).

---

## 2. Process Model Decomposition

The synthetic wastewater coagulation process model computes effluent turbidity $T_{\text{eff}}$ as:

$$T_{\text{eff}} = T_{\text{rem}} + T_{\text{over}}$$

where:

$$T_{\text{rem}}(d, T_{\text{in}}, T, \text{pH}) = T_{\text{floor}} + \frac{T_{\text{in}} - T_{\text{floor}}}{1 + \frac{c_1 \cdot d^{1.6}}{\phi_T(T) \cdot \phi_{\text{pH}}(\text{pH})}}$$

$$T_{\text{over}}(d, Q, \text{pH}) = c_2 \cdot d^{2.1} \cdot \left(\frac{Q}{Q_{\text{nom}}}\right)^{0.85} \cdot \phi_{\text{pH}}(\text{pH})$$

with correction factors:
- Temperature kinetics factor: $\phi_T(T) = \max\left(0.5, \; 1.0 + 0.015 \cdot (T_{\text{nom}} - T)\right)$
- pH penalty factor: $\phi_{\text{pH}}(\text{pH}) = 1.0 + 0.20 \cdot (\text{pH} - \text{pH}_{\text{opt}})^2$

Constants satisfy: $T_{\text{floor}} > 0, c_1 > 0, c_2 > 0, Q_{\text{nom}} > 0$.
The physical disturbance vector is:

$$\theta = (T_{\text{in}}, Q, \text{pH}, T) \in \Theta = [\underline{T}_{\text{in}}, \overline{T}_{\text{in}}] \times [\underline{Q}, \overline{Q}] \times [\underline{\text{pH}}, \overline{\text{pH}}] \times [\underline{T}, \overline{T}]$$

with physical domains: $T_{\text{in}} \ge T_{\text{floor}} > 0, Q > 0, T > 0, d \ge 0$.

---

## 3. Component-Wise Soundness Proof

We now examine each term in the model to prove that interval evaluation strictly upper-bounds the true maximum.

### 3.1 Temperature Factor $\phi_T(T)$
The mapping $T \mapsto 1.0 + 0.015 \cdot (T_{\text{nom}} - T)$ is an affine, strictly decreasing function of temperature. Its exact range over $T \in [\underline{T}, \overline{T}]$ is:

$$[1.0 + 0.015(T_{\text{nom}} - \overline{T}), \; 1.0 + 0.015(T_{\text{nom}} - \underline{T})]$$

Applying $\max(0.5, \cdot)$ preserves monotonicity. Thus, `temp_factor = Interval(temp_factor_lo, temp_factor_hi)` computes the **exact range** of $\phi_T(T)$ with zero wrapping error.

### 3.2 pH Penalty Factor $\phi_{\text{pH}}(\text{pH})$
The difference $\Delta \text{pH} = \text{pH} - \text{pH}_{\text{opt}}$ has exact range $[\underline{\text{pH}} - \text{pH}_{\text{opt}}, \overline{\text{pH}} - \text{pH}_{\text{opt}}]$.
The squaring operator in `Interval.__pow__(2)` evaluates:
- If $\Delta \text{pH} \ge 0$: $[(\underline{\Delta \text{pH}})^2, (\overline{\Delta \text{pH}})^2]$
- If $\Delta \text{pH} \le 0$: $[(\overline{\Delta \text{pH}})^2, (\underline{\Delta \text{pH}})^2]$
- If $0 \in \Delta \text{pH}$: $[0, \; \max(|\underline{\Delta \text{pH}}|, |\overline{\Delta \text{pH}}|)^2]$

In all three cases, the square of any real scalar $\Delta \text{pH}$ is bounded by the returned interval:

$$\forall \text{pH} \in [\underline{\text{pH}}, \overline{\text{pH}}], \quad (\text{pH} - \text{pH}_{\text{opt}})^2 \in [\Delta \text{pH}]^2$$

Multiplying by scalar $0.20 > 0$ and adding $1.0$ is monotonically increasing. Hence, $\phi_{\text{pH}}(\text{pH}) \in [\phi_{\text{pH}}]$ is exact.

### 3.3 Removal Turbidity $T_{\text{rem}}$
Observe the partial derivatives of $T_{\text{rem}}$ with respect to each variable on the physical domain:

1. **Influent Turbidity $T_{\text{in}}$**:
   $$\frac{\partial T_{\text{rem}}}{\partial T_{\text{in}}} = \frac{1}{1 + \frac{c_1 d^{1.6}}{\phi_T \phi_{\text{pH}}}} > 0$$
   $T_{\text{rem}}$ is strictly increasing in $T_{\text{in}}$. Its maximum occurs at $\overline{T}_{\text{in}}$.

2. **Denominator Factors ($\phi_T, \phi_{\text{pH}}$)**:
   Let $K = \phi_T \cdot \phi_{\text{pH}} > 0$. Then:
   $$\frac{\partial T_{\text{rem}}}{\partial K} = (T_{\text{in}} - T_{\text{floor}}) \cdot \frac{c_1 d^{1.6} K^{-2}}{\left(1 + \frac{c_1 d^{1.6}}{K}\right)^2} \ge 0$$
   $T_{\text{rem}}$ is monotonically non-decreasing in both $\phi_T$ and $\phi_{\text{pH}}$. Its maximum occurs when both $\phi_T$ and $\phi_{\text{pH}}$ are at their upper bounds ($\overline{\phi}_T, \overline{\phi}_{\text{pH}}$).

3. **Coagulant Dose $d$**:
   $$\frac{\partial T_{\text{rem}}}{\partial d} = - \frac{(T_{\text{in}} - T_{\text{floor}}) \cdot \frac{1.6 c_1 d^{0.6}}{K}}{\left(1 + \frac{c_1 d^{1.6}}{K}\right)^2} \le 0$$
   $T_{\text{rem}}$ is monotonically non-increasing in $d$. For a scalar candidate dose $d$, $d$ has zero width, so no dependency exists.

Because $T_{\text{in}}$ and $T$ appear **only once** in the entire expression for $T_{\text{rem}}$ and do not appear anywhere in $T_{\text{over}}$, evaluating $T_{\text{rem}}$ via interval arithmetic produces:

$$\sup_{T_{\text{in}}, T} T_{\text{rem}} = T_{\text{floor}} + \frac{\overline{T}_{\text{in}} - T_{\text{floor}}}{1 + \frac{c_1 d^{1.6}}{\overline{\phi}_T \cdot \overline{\phi}_{\text{pH}}}} = \overline{T}_{\text{rem}}$$

### 3.4 Overdosing Turbidity $T_{\text{over}}$
Observe the partial derivatives of $T_{\text{over}}$:

1. **Hydraulic Flow Rate $Q$**:
   $$\frac{\partial T_{\text{over}}}{\partial Q} = c_2 d^{2.1} \cdot \frac{0.85}{Q_{\text{nom}}} \left(\frac{Q}{Q_{\text{nom}}}\right)^{-0.15} \cdot \phi_{\text{pH}} \ge 0$$
   $T_{\text{over}}$ is strictly increasing in $Q$. Its maximum occurs at $\overline{Q}$. Since $Q$ appears only once in the entire system, its interval bound is exact.

2. **pH Penalty $\phi_{\text{pH}}$**:
   $$\frac{\partial T_{\text{over}}}{\partial \phi_{\text{pH}}} = c_2 d^{2.1} \left(\frac{Q}{Q_{\text{nom}}}\right)^{0.85} \ge 0$$
   $T_{\text{over}}$ is strictly increasing in $\phi_{\text{pH}}$. Its maximum occurs at $\overline{\phi}_{\text{pH}}$.

---

## 4. The Dependency Problem: Shared Variable Analysis

The fundamental source of potential excess conservatism in interval arithmetic is the **dependency problem** (loss of correlation when the same variable appears multiple times).

In our process model, exactly one uncertain variable appears in more than one term: **$\text{pH}$**. It appears in $T_{\text{rem}}$ through $\phi_{\text{pH}}$ and in $T_{\text{over}}$ through $\phi_{\text{pH}}$.

### 4.1 Monotonicity Concurrence Theorem
**Theorem 2 (Exact Bounds Under Shared Monotonic Variables):**
Let $f(x) = f_1(x) + f_2(x)$, where $f_1, f_2: X \to \mathbb{R}$ are both monotonically non-decreasing with respect to $x$ on interval $X = [\underline{x}, \overline{x}]$. Then:

$$\sup_{x \in X} [f_1(x) + f_2(x)] = f_1(\overline{x}) + f_2(\overline{x}) = \overline{f}_1 + \overline{f}_2$$

**Proof:**
Since $f_1$ is non-decreasing, $\forall x \in X, f_1(x) \le f_1(\overline{x})$.
Since $f_2$ is non-decreasing, $\forall x \in X, f_2(x) \le f_2(\overline{x})$.
Summing the inequalities:
$$\forall x \in X, \quad f_1(x) + f_2(x) \le f_1(\overline{x}) + f_2(\overline{x})$$
Equality holds at $x^{\star} = \overline{x} \in X$.
Therefore:
$$\sup_{x \in X} (f_1(x) + f_2(x)) = f_1(\overline{x}) + f_2(\overline{x})$$
$\blacksquare$

### 4.2 Application to $\phi_{\text{pH}}$
From Sections 3.3 and 3.4:
$$\frac{\partial T_{\text{rem}}}{\partial \phi_{\text{pH}}} \ge 0 \quad \text{and} \quad \frac{\partial T_{\text{over}}}{\partial \phi_{\text{pH}}} \ge 0$$

Both terms are **simultaneously maximized** at the upper bound $\overline{\phi}_{\text{pH}}$.
Because their partial derivatives with respect to $\phi_{\text{pH}}$ have the same sign, the supremum of their sum over $\phi_{\text{pH}} \in [\underline{\phi}_{\text{pH}}, \overline{\phi}_{\text{pH}}]$ is identically equal to the sum of their individual suprema:

$$\sup_{\text{pH}} \left( T_{\text{rem}}(\text{pH}) + T_{\text{over}}(\text{pH}) \right) = T_{\text{rem}}(\overline{\phi}_{\text{pH}}) + T_{\text{over}}(\overline{\phi}_{\text{pH}}) = \overline{T}_{\text{rem}} + \overline{T}_{\text{over}}$$

**Corollary:** The shared occurrence of $\text{pH}$ in $T_{\text{rem}}$ and $T_{\text{over}}$ introduces **zero dependency over-conservatism** on the upper bound. The computed upper bound $\overline{\mathcal{R}}(d)$ is the **exact supremum** of the process model over the disturbance box:

$$\overline{\mathcal{R}}_{\text{exact}}(d) = \max_{\theta \in \Theta} f(d, \theta)$$

---

## 5. Bounded Dose Actuator Uncertainty

When the applied dose is itself subject to bounded pump delivery uncertainty, $d \in D = [\underline{d}, \overline{d}]$:
- $\frac{\partial T_{\text{rem}}}{\partial d} \le 0 \implies$ maximized at $\underline{d}$.
- $\frac{\partial T_{\text{over}}}{\partial d} \ge 0 \implies$ maximized at $\overline{d}$.

In this case, interval arithmetic evaluates:

$$T_{\text{eff}}(D) = T_{\text{rem}}(\underline{d}) + T_{\text{over}}(\overline{d})$$

For any single physical realization $d^{\star} \in D$:

$$T_{\text{rem}}(d^{\star}) + T_{\text{over}}(d^{\star}) \le T_{\text{rem}}(\underline{d}) + T_{\text{over}}(\overline{d}) = \overline{T}_{\text{eff}}$$

Thus, the interval computation is guaranteed to be an **over-approximation** (conservative):

$$\max_{d \in D} f(d, \theta) \le \overline{\mathcal{R}}(D)$$

It can never underestimate the worst-case effluent.

---

## 6. Numerical Rounding and Safety Margins

In IEEE 754 floating-point arithmetic, catastrophic cancellation and directed rounding can theoretically produce infinitesimally underestimated bounds if outward rounding is not enforced at every instruction.

To guarantee soundness on standard standard hardware and standard CPython runtimes without platform-dependent rounding mode switches (e.g. `fesetround`), `ReachabilityEngine` implements an explicit additive safety margin:

$$\overline{\mathcal{R}}_{\text{certified}}(d) = \overline{\mathcal{R}}(d) + \delta_{\text{margin}}$$

where $\delta_{\text{margin}} \ge 0$ (default $0.02\text{ NTU}$).

Given machine epsilon $\epsilon_{\text{mach}} \approx 2.22 \times 10^{-16}$, the accumulated floating point error across the $\sim 20$ elementary arithmetic operations in $f(d, \theta)$ is bounded by:

$$|\text{fl}(f) - f| \le 25 \cdot \epsilon_{\text{mach}} \cdot |f| < 10^{-13}\text{ NTU}$$

Because $\delta_{\text{margin}} = 0.02 \gg 10^{-13}\text{ NTU}$, machine rounding error cannot breach the upper bound:

$$\overline{\mathcal{R}}_{\text{certified}}(d) > \max_{\theta \in \Theta} f(d, \theta) \quad \text{unconditionally.}$$

---

## 7. Strict Fail-Safe Invariant

The formal certifier enforces an unconditional fail-safe invariant:

```
[Candidate Dose d]
       │
       ▼
[Sanity & Physical Range Check] ──── Invalid / NaN / Inf ───┐
       │                                                    │
       ▼                                                    │
[pH Validity Regime Check] ───────── pH < 5.0 or > 8.5 ─────┤ (OUTSIDE_MODEL_VALIDITY)
       │                                                    │
       ▼                                                    │
[Reachability Engine Evaluation] ─── Computational Error ───┤
       │                                                    │
       ▼                                                    │
[Check: R.hi <= Compliance Limit]                           │
       │                                                    │
       ├─► Yes: ACCEPT candidate dose                       │
       │                                                    │
       └─► No:  Bisection Search                            │
                  │                                         │
                  ├─► Found Safe Dose: CORRECTED            │
                  └─► Not Found: SAFE FALLBACK ◄────────────┘
```

If **any** computational anomaly occurs:
1. `math.isnan(d)` or `math.isinf(d)` or $d < 0$
2. Numerical domain error (e.g., negative physical interval)
3. Disturbance uncertainty straddling out-of-validity regime ($\text{pH} < 5.0$ or $\text{pH} > 8.5$)
4. Unhandled runtime exception or timeout
5. Search unable to find any operating point where $\overline{\mathcal{R}}(d) \le L_{\text{compliance}}$

The system logs a critical diagnostic warning and unconditionally reverts to the pre-verified safe default action $d_{\text{fallback}}$.

**Soundness Guarantee:** An unverified or non-compliant dosing action is mathematically prevented from ever reaching the physical process actuator.

---

## 8. Operational Validity Scope & Chemical Regimes (v0.4.0)

A fundamental distinction must be maintained between **mathematical inclusion soundness** and **physical model validity**:

1. **Mathematical Inclusion Soundness:** The interval arithmetic theorems proven in Sections 1–4 hold universally for the mathematical function $f(d, \theta)$. For any input box $\Theta$, $\overline{\mathcal{R}}(d) \ge \sup_{\theta \in \Theta} f(d, \theta)$ with zero exception.
2. **Physical Process Validity:** The mathematical function $f(d, \theta)$ is an empirical surrogate representing single-chemical alum ($\text{Al}_2(\text{SO}_4)_3$) coagulation. Its physical faithfulness is strictly bounded to the aquatic chemistry regime where solid amorphous aluminum hydroxide ($\text{Al(OH)}_3\text{(s)}$) precipitates:

$$\text{pH}_{\text{valid}} \in [5.0, \; 8.0]$$

### 8.1 Chemical Mechanism at Regime Boundaries

- **Acidic Regime ($\text{pH} < 5.0$):** Aluminum remains primarily as trivalent hydrated cations $\text{Al}^{3+}$ and $\text{AlOH}^{2+}$. Insoluble floc does not form efficiently, and high doses do not settle.
- **Aluminate Regime ($\text{pH} > 8.5$):** The solubility of aluminum amphoterically increases due to hydroxide coordination, converting insoluble $\text{Al(OH)}_3\text{(s)}$ into soluble aluminate anions $\text{Al(OH)}_4^-$:

$$\text{Al(OH)}_3\text{(s)} + \text{OH}^- \rightleftharpoons \text{Al(OH)}_4^-$$

In this alkaline regime, the process model's quadratic penalty $\phi_{\text{pH}} = 1.0 + 0.20(\text{pH} - 7.2)^2$ is **qualitatively backwards**: it interprets rising pH as increasing coagulant demand, whereas adding more alum at $\text{pH} > 8.5$ causes severe dissolved aluminum breakthrough in finished water rather than particulate removal.

### 8.2 Out-of-Validity Certification Refusal

In v0.4.0, when the bounded input uncertainty interval $[\underline{\text{pH}}, \overline{\text{pH}}]$ enters the aluminate-dominant regime ($\overline{\text{pH}} > 8.5$) or acidic regime ($\underline{\text{pH}} < 5.0$), the engine refuses certification:

- `result.status = CertificationStatus.OUTSIDE_MODEL_VALIDITY`
- `result.process_model_valid = False`
- `result.model_validity_reason` cites the alum chemical boundary and explains that single-chemical dosing cannot be certified.

This behavior is distinct from `FAILED_SAFE_FALLBACK` (computational error) and `REJECTED_CORRECTED` (dose problem). The reachability engine explicitly refuses to issue a false or misleading safety certificate when the underlying process model's chemical assumptions are violated.

