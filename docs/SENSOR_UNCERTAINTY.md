# Sensor Uncertainty Investigation & Sensitivity Analysis

**Version:** 0.4.0  
**Status:** Validated  
**References:** EPA Method 180.1, ISO 7027-1:2016, USGS TM 1-D3, Hach 1720E / TU5300 sc Manuals  

---

## 1. Motivation & Background

In `certified-dose` v0.1.0–v0.3.0, instrumentation uncertainty for influent turbidity was modeled as a flat proportional band:

$$\Delta T = \max(0.50\text{ NTU},\, 0.10 \times T_{\text{reading}})$$

During the real-world evaluation against USGS NWIS continuous water-quality telemetry (documented in `docs/REAL_WORLD_EVALUATION.md` §4.2), two questions arose regarding this assumption:

1. **At low turbidity ($T < 5$ NTU):** Does a $10\%$ relative error or a $0.50$ NTU floor represent true nephelometer performance?
2. **At storm-scale turbidity ($T > 100$–$250+$ NTU):** Does real nephelometer field error remain linear at $\pm 10\%$, or does optical physics (e.g. multiple scattering, absorption, biofouling) cause degradation or relative compression?

This document summarizes the literature and instrumentation findings, specifies the piecewise tiered uncertainty model implemented in v0.4.0, and presents empirical sensitivity benchmarks across both USGS field datasets.

---

## 2. Instrumentation Literature & Regulatory Specifications

### 2.1 EPA Method 180.1 (Nephelometric Turbidity Determination)

- **Validated Operating Range:** EPA Method 180.1 is formally validated **only for 0 to 40 NTU**.
- **Dilution Requirement:** Section 11.2 explicitly mandates that for samples with turbidity exceeding $40$ NTU, the sample must be diluted with turbidity-free water to bring the reading into the $0$–$40$ NTU range. In continuous online field monitoring (such as USGS gage stations or plant intake turbidimeters), inline dilution is rarely practical, meaning online readings above $40$ NTU operate outside the strictly validated EPA envelope.
- **Instrument Accuracy:** Under laboratory conditions with primary formazin standards, instrument precision within $0$–$40$ NTU is typically $\pm 2\%$ to $\pm 5\%$.

### 2.2 Optical Physics at High Turbidity (> 100 NTU)

- **Single vs. Multiple Scattering:** Standard nephelometry relies on single-event Rayleigh/Mie scattering at 90 degrees. At particle concentrations corresponding to $T > 100$ NTU, the mean free path of light through the fluid decreases substantially, causing **multiple scattering** (photons scattered by multiple particles before detection) and **attenuation/absorption**.
- **Non-Linear Response:** Above $\sim 100$ NTU, the 90-degree scattered light signal becomes non-linear and eventually peaks and decreases at extremely high turbidities ($> 1000$ NTU), a phenomenon known as signal reversal.
- **Field Standards (USGS TM 1-D3 & Fondriest 2014):** Field calibrations of submersible and flow-through optical probes indicate that while manufacturer calibration under clean optical conditions promises $\pm 5\%$ up to $1000$ NTU, real-world field deployment introduces errors of $\pm 10\%$ to $\pm 20\%$ at $T > 100$ NTU due to window biofouling, particulate sedimentation, and hydrodynamic shearing around the optical face.

---

## 3. Piecewise EPA-Tiered Uncertainty Model

To reflect both the high precision within the EPA-validated window and the optical degradation at high turbidity, v0.4.0 introduces the `TurbidityUncertaintyModel.PIECEWISE_EPA_RANGE` in `certified_dose.real_world`:

$$
\Delta T = \max\left(0.50\text{ NTU},\, \epsilon(T) \times T\right)
$$

where the fractional relative uncertainty $\epsilon(T)$ is piecewise defined:

$$
\epsilon(T) = \begin{cases} 
0.05 & \text{for } T \le 40.0\text{ NTU} \quad \text{(EPA Method 180.1 validated range; conservative field allowance)} \\
0.10 & \text{for } 40.0 < T \le 100.0\text{ NTU} \quad \text{(Transitional regime; un-diluted nephelometry)} \\
0.15 & \text{for } T > 100.0\text{ NTU} \quad \text{(High-turbidity multiple-scattering degradation)}
\end{cases}
$$

An absolute floor of $\Delta T_{\min} = 0.50$ NTU is maintained across all ranges to account for sensor zero-drift and electronic noise.

---

## 4. Empirical Sensitivity Benchmark

We evaluated the entire 5,727-record USGS dataset across four uncertainty specifications:
1. **Proportional 5%:** Optimistic clean-sensor baseline ($\pm 5\%$).
2. **Proportional 10% (Default):** Standard v0.1.0–v0.3.0 conservative model ($\pm 10\%$).
3. **Proportional 15%:** Heavy field fouling / adverse condition model ($\pm 15\%$).
4. **Piecewise EPA-Tiered:** v0.4.0 tiered model ($5\% / 10\% / 15\%$).

### 4.1 Station 04193500 (Maumee River at Waterville, OH — Turbidity Range 4.5–240 NTU)

| Uncertainty Model | Accepted (%) | Rejected & Corrected (%) | Outside Model Validity (%) | Chemical Overhead (%) | Mean Applied Dose (mg/L) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Proportional 5%** | 70.16% | 0.00% | 29.84% | 2.90% | 18.62 |
| **Proportional 10% (Default)** | 69.99% | 0.17% | 29.84% | 2.90% | 18.62 |
| **Proportional 15%** | 68.83% | 1.33% | 29.84% | 2.91% | 18.62 |
| **Piecewise EPA-Tiered** | 69.95% | 0.21% | 29.84% | 2.90% | 18.62 |

### 4.2 Station 01184000 (Connecticut River at Thompsonville, CT — Turbidity Range 0.4–33 NTU)

| Uncertainty Model | Accepted (%) | Rejected & Corrected (%) | Outside Model Validity (%) | Chemical Overhead (%) | Mean Applied Dose (mg/L) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Proportional 5%** | 91.31% | 0.00% | 8.69% | 39.97% | 3.82 |
| **Proportional 10% (Default)** | 91.31% | 0.00% | 8.69% | 39.97% | 3.82 |
| **Proportional 15%** | 91.31% | 0.00% | 8.69% | 39.97% | 3.82 |
| **Piecewise EPA-Tiered** | 91.31% | 0.00% | 8.69% | 39.97% | 3.82 |

---

## 5. Key Findings & Discussion

1. **Upland / Low-Turbidity Regimes (Connecticut River):**
   - In pristine or upland water sources where turbidity is consistently $< 5$ NTU, the absolute uncertainty floor ($\pm 0.50$ NTU) completely dominates relative percentage scaling ($5\%$, $10\%$, or $15\%$).
   - As a result, certification outcomes and applied chemical overhead are **$100\%$ invariant** to the chosen relative error model in low-turbidity conditions.

2. **Agricultural / Flashy Regimes (Maumee River):**
   - The piecewise model achieves $69.95\%$ acceptance, nearly identical to the $10\%$ default ($69.99\%$), while tightening certification bounds during baseline conditions ($T \le 40$ NTU) and adding protective conservatism during extreme sediment runoff events ($T > 100$ NTU).
   - The outside-validity percentage ($29.84\%$) is governed strictly by pH dynamics (algal blooms driving $\text{pH} > 8.5$), completely independent of turbidity uncertainty scaling.

3. **Conclusion:**
   - The original $\pm 10\%$ flat proportional model is confirmed to be a robust, conservative surrogate for general water treatment plant modeling across typical operating bands ($10$–$80$ NTU).
   - For high-precision installations or plants with severe sediment spikes, the `PIECEWISE_EPA_RANGE` model provides grounded fidelity aligned with EPA Method 180.1 standards and optical scattering physics.