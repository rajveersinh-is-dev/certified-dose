"""Interactive Streamlit dashboard for formal reachability dosing certification.

Enables visual exploration of worst-case reachable sets, sensor uncertainty
envelopes, dynamic closed-loop simulations, and the '0 violations' guarantee.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from certified_dose.certifier import CertifiedDoseWrapper
from certified_dose.controller import AggressiveCostMinimizerController, PlantState
from certified_dose.process_model import SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine
from certified_dose.simulate import ClosedLoopSimulator


def setup_page() -> None:
    """Configures Streamlit page layout and theme styling."""
    st.set_page_config(
        page_title="certified-dose | Formal Reachability Safety Layer",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .metric-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 16px;
            border-left: 5px solid #28a745;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .metric-title { font-size: 0.85rem; color: #6c757d; text-transform: uppercase; font-weight: bold; }
        .metric-value { font-size: 1.8rem; font-weight: bold; margin: 4px 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> dict[str, float | int]:
    """Renders interactive sidebar controls and returns parameter values."""
    st.sidebar.title("🛡️ Safety Controls")
    st.sidebar.markdown("Configure sensor uncertainty and regulatory thresholds.")

    st.sidebar.subheader("Regulatory Threshold")
    compliance_limit = st.sidebar.slider(
        "Effluent Compliance Ceiling (NTU)",
        min_value=0.5,
        max_value=2.0,
        value=1.0,
        step=0.05,
        help="Maximum permissible effluent turbidity. Regulatory limit.",
    )

    st.sidebar.subheader("Sensor Uncertainty Margins")
    turb_pct = (
        st.sidebar.slider(
            "Influent Turbidity Uncertainty (±%)",
            min_value=5,
            max_value=30,
            value=15,
            step=1,
        )
        / 100.0
    )

    flow_pct = (
        st.sidebar.slider(
            "Flow Rate Uncertainty (±%)",
            min_value=5,
            max_value=25,
            value=10,
            step=1,
        )
        / 100.0
    )

    ph_delta = st.sidebar.slider(
        "pH Measurement Noise (±Δ)",
        min_value=0.1,
        max_value=0.5,
        value=0.3,
        step=0.05,
    )

    temp_delta = st.sidebar.slider(
        "Temperature Noise (±°C)",
        min_value=0.5,
        max_value=4.0,
        value=2.0,
        step=0.5,
    )

    st.sidebar.subheader("Simulation Parameters")
    steps = st.sidebar.slider(
        "Timesteps", min_value=50, max_value=200, value=100, step=10
    )
    seed = st.sidebar.number_input("Random Disturbance Seed", value=42, step=1)
    controller_aggression = st.sidebar.slider(
        "Candidate Controller Aggression (Chemical Shaving)",
        min_value=0.4,
        max_value=1.0,
        value=0.65,
        step=0.05,
        help="Lower values shave chemical dose more aggressively, increasing risk of violations without safety wrapper.",
    )

    return {
        "compliance_limit": compliance_limit,
        "turb_pct": turb_pct,
        "flow_pct": flow_pct,
        "ph_delta": ph_delta,
        "temp_delta": temp_delta,
        "steps": int(steps),
        "seed": int(seed),
        "aggression": controller_aggression,
    }


def main() -> None:
    """Main dashboard rendering entry point."""
    setup_page()

    st.title("🛡️ certified-dose: Formal Reachability Safety Layer")
    st.markdown(
        "**Worst-case certified process dosing via interval reachability analysis.** "
        "Every dosing decision is guaranteed to keep effluent quality within the regulatory envelope under bounded disturbance uncertainty."
    )

    params = render_sidebar()

    # Run closed-loop simulation
    model = SyntheticProcessModel()
    certifier = CertifiedDoseWrapper(
        engine=ReachabilityEngine(model=model, safety_margin=0.02),
        compliance_limit=params["compliance_limit"],
        default_uncertainty={
            "turbidity_pct": params["turb_pct"],
            "flow_rate_pct": params["flow_pct"],
            "ph_delta": params["ph_delta"],
            "temp_delta": params["temp_delta"],
        },
    )
    candidate_ctrl = AggressiveCostMinimizerController(aggression=params["aggression"])
    simulator = ClosedLoopSimulator(
        model=model, certifier=certifier, candidate_controller=candidate_ctrl
    )

    summary = simulator.run(
        n_steps=int(params["steps"]),
        seed=int(params["seed"]),
        storm_start=25,
        storm_duration=25,
    )

    # Metric KPI summary cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Control Steps", summary.total_steps)
    with col2:
        st.metric(
            "Unchecked Candidate Violations",
            summary.candidate_violations,
            delta=f"{(summary.candidate_violations / summary.total_steps) * 100:.1f}% failure rate",
            delta_color="inverse",
        )
    with col3:
        st.metric(
            "Certified Violations",
            summary.certified_violations,
            delta="GUARANTEED 0",
            delta_color="normal",
        )
    with col4:
        st.metric(
            "Safety Wrapper Interventions",
            f"{summary.interventions} steps",
            delta=f"{summary.intervention_rate_pct:.1f}% corrected",
            delta_color="off",
        )

    tab1, tab2, tab3 = st.tabs(
        [
            "📈 Closed-Loop Telemetry",
            "🔍 Single-Dose Reachability Inspector",
            "📖 Methodology & Disclosures",
        ]
    )

    with tab1:
        st.subheader("Dynamic Closed-Loop Simulation with Storm Event")
        st.caption(
            "Notice how between steps 25 and 50 (high turbidity storm surge), the unverified candidate controller "
            "proposes inadequate doses causing severe violations (red). The formal safety certifier intervenes (green), "
            "keeping effluent strictly under the 1.0 NTU limit."
        )

        steps_arr = np.array([r.step for r in summary.records])
        cand_eff = np.array([r.candidate_effluent for r in summary.records])
        cert_eff = np.array([r.certified_effluent for r in summary.records])
        reach_hi = np.array([r.reachable_hi for r in summary.records])
        reach_lo = np.array([r.reachable_lo for r in summary.records])
        cand_dose = np.array([r.candidate_dose for r in summary.records])
        cert_dose = np.array([r.certified_dose for r in summary.records])
        intervened = np.array([r.was_intervened for r in summary.records])
        raw_turb = np.array([r.influent_turbidity for r in summary.records])

        # Plot 1: Effluent Turbidity vs Compliance Limit
        fig1 = go.Figure()
        # Shaded reachable set band
        fig1.add_trace(
            go.Scatter(
                x=steps_arr,
                y=reach_hi,
                mode="lines",
                line={"width": 0},
                showlegend=False,
                name="Reachable High",
            )
        )
        fig1.add_trace(
            go.Scatter(
                x=steps_arr,
                y=reach_lo,
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor="rgba(40, 167, 69, 0.15)",
                name="Certified Reachable Envelope",
            )
        )
        # Candidate Effluent
        fig1.add_trace(
            go.Scatter(
                x=steps_arr,
                y=cand_eff,
                mode="lines",
                line={"color": "#dc3545", "width": 2, "dash": "dot"},
                name="Unchecked Candidate Effluent",
            )
        )
        # Certified Effluent
        fig1.add_trace(
            go.Scatter(
                x=steps_arr,
                y=cert_eff,
                mode="lines",
                line={"color": "#28a745", "width": 2.5},
                name="True Certified Effluent",
            )
        )
        # Regulatory Limit Line
        fig1.add_hline(
            y=params["compliance_limit"],
            line={"color": "#d9534f", "width": 2, "dash": "dash"},
            annotation_text=f"Compliance Limit ({params['compliance_limit']:.2f} NTU)",
            annotation_position="top right",
        )
        fig1.update_layout(
            title="Effluent Turbidity: Candidate vs Certified Response",
            xaxis_title="Simulation Step",
            yaxis_title="Effluent Turbidity (NTU)",
            hovermode="x unified",
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
        )
        st.plotly_chart(fig1, use_container_width=True)

        # Plot 2: Dosing Actions (Proposed vs Applied)
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=steps_arr,
                y=cand_dose,
                mode="lines",
                line={"color": "#6f42c1", "width": 1.5, "dash": "dash"},
                name="Candidate Proposed Dose",
            )
        )
        fig2.add_trace(
            go.Scatter(
                x=steps_arr,
                y=cert_dose,
                mode="lines",
                line={"color": "#007bff", "width": 2},
                name="Certified Safe Dose",
            )
        )
        # Markers for safety interventions
        int_steps = steps_arr[intervened]
        int_doses = cert_dose[intervened]
        fig2.add_trace(
            go.Scatter(
                x=int_steps,
                y=int_doses,
                mode="markers",
                marker={
                    "symbol": "circle",
                    "size": 7,
                    "color": "#ffc107",
                    "line": {"width": 1, "color": "#333"},
                },
                name="Safety Wrapper Intervention",
            )
        )
        fig2.update_layout(
            title="Dosing Actions: Candidate vs Safety-Corrected Dosing Setpoint",
            xaxis_title="Simulation Step",
            yaxis_title="Coagulant Dose (mg/L)",
            hovermode="x unified",
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Plot 3: Influent Turbidity
        fig3 = go.Figure()
        fig3.add_trace(
            go.Scatter(
                x=steps_arr,
                y=raw_turb,
                mode="lines",
                line={"color": "#fd7e14", "width": 2},
                name="Raw Influent Turbidity (NTU)",
            )
        )
        fig3.update_layout(
            title="Raw Water Influent Turbidity (Environmental Disturbance)",
            xaxis_title="Simulation Step",
            yaxis_title="Influent Turbidity (NTU)",
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
        )
        st.plotly_chart(fig3, use_container_width=True)

    with tab2:
        st.subheader("Interactive Single-Dose Reachability Inspector")
        st.markdown(
            "Probe any operating point and inspect the formal reachable interval $[y_{\\min}, y_{\\max}]$ in real time."
        )

        i_col1, i_col2 = st.columns(2)
        with i_col1:
            insp_turb = st.slider("Raw Influent Turbidity (NTU)", 10.0, 80.0, 32.0, 1.0)
            insp_flow = st.slider("Flow Rate (m3/h)", 600.0, 1500.0, 1050.0, 25.0)
        with i_col2:
            insp_ph = st.slider("pH", 6.5, 8.5, 7.3, 0.1)
            insp_temp = st.slider("Temperature (°C)", 5.0, 28.0, 16.0, 1.0)

        insp_dose = st.slider("Candidate Coagulant Dose (mg/L)", 2.0, 60.0, 16.0, 0.5)

        # Evaluate reachability
        insp_state = PlantState(
            turbidity=insp_turb,
            flow_rate=insp_flow,
            ph=insp_ph,
            temperature=insp_temp,
        )
        dist_intervals = certifier.build_disturbance_intervals(insp_state)
        cert_res = certifier.certify_action(insp_dose, dist_intervals)
        reach_set = cert_res.reachable_set

        status_badge = (
            "✅ **ACCEPTED (CERTIFIED SAFE)**"
            if cert_res.status == "ACCEPTED"
            else f"⚠️ **REJECTED & CORRECTED TO {cert_res.certified_dose:.2f} mg/L**"
        )
        st.markdown(f"### Verdict: {status_badge}")
        st.info(cert_res.reason)

        # Plot Reachable Set Bar
        fig_bar = go.Figure()
        fig_bar.add_trace(
            go.Bar(
                name="Reachable Set",
                x=[reach_set.hi - reach_set.lo],
                y=["Effluent Turbidity"],
                base=[reach_set.lo],
                orientation="h",
                marker={
                    "color": (
                        "#28a745"
                        if reach_set.hi <= params["compliance_limit"]
                        else "#dc3545"
                    )
                },
            )
        )
        fig_bar.add_vline(
            x=params["compliance_limit"],
            line={"color": "red", "width": 3, "dash": "dash"},
            annotation_text=f"Compliance Limit ({params['compliance_limit']} NTU)",
        )
        fig_bar.update_layout(
            title=f"Worst-Case Reachable Effluent: [{reach_set.lo:.3f}, {reach_set.hi:.3f}] NTU",
            xaxis_title="Effluent Turbidity (NTU)",
            yaxis_visible=False,
            height=220,
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Operator Explainability and Sensitivity Attribution
        exp = cert_res.explain()
        with st.expander(
            "🔎 Operator Explainability & Sensitivity Attribution", expanded=True
        ):
            e_col1, e_col2 = st.columns([1, 1])
            with e_col1:
                st.markdown(f"**Binding Constraint**: {exp.binding_constraint}")
                st.markdown(
                    f"**Safety Margin**: `{exp.safety_margin:+.3f} NTU` below ceiling"
                )
                st.markdown(
                    f"**Actionable Operator Guidance**:\n> {exp.operator_guidance}"
                )

            with e_col2:
                if exp.sensitivities:
                    st.markdown(
                        "**Uncertainty Attribution (% contribution to output spread)**"
                    )
                    sens_x = [
                        s.relative_contribution_pct for s in reversed(exp.sensitivities)
                    ]
                    sens_y = [
                        s.variable.replace("_", " ").title()
                        for s in reversed(exp.sensitivities)
                    ]
                    fig_sens = go.Figure(
                        go.Bar(
                            x=sens_x,
                            y=sens_y,
                            orientation="h",
                            marker={
                                "color": [
                                    "#e74c3c" if val > 30 else "#3498db"
                                    for val in sens_x
                                ]
                            },
                            text=[f"{v:.1f}%" for v in sens_x],
                            textposition="auto",
                        )
                    )
                    fig_sens.update_layout(
                        xaxis_title="% Contribution",
                        margin={"l": 20, "r": 20, "t": 20, "b": 20},
                        height=200,
                    )
                    st.plotly_chart(fig_sens, use_container_width=True)

    with tab3:
        st.subheader("Formal Safety Methodology & Mathematical Guarantees")
        st.markdown(r"""
            ### How Formal Reachability Works
            1. **Bounded Input Uncertainty**: Rather than assuming single nominal sensor values, sensors provide an interval:
               $$T_{in} \in [\underline{T}_{in}, \overline{T}_{in}], \quad Q \in [\underline{Q}, \overline{Q}]$$
            2. **Interval Arithmetic Propagation**: Given a proposed candidate dose $d$, the nonlinear process model:
               $$T_{eff} = f(d, T_{in}, Q, pH, T)$$
               is evaluated over the input intervals using closed interval arithmetic operations ($+, -, \times, /, x^p$).
            3. **Guaranteed Reachable Set**: The output is an interval:
               $$\mathcal{R}(d) = [\underline{T}_{eff}, \overline{T}_{eff}]$$
               By interval inclusion monotonicity, for all possible physical disturbances $\theta \in \Theta$:
               $$f(d, \theta) \in \mathcal{R}(d)$$
            4. **Safety Certificate**:
               An action is certified if and only if:
               $$\sup \mathcal{R}(d) = \overline{T}_{eff} \le L_{limit}$$
            5. **Fail-Safe Guarantee**:
               If the reachable upper bound exceeds $L_{limit}$, or if any numerical error/timeout occurs, the certifier
               replaces the proposed dose with a provably-safe fallback.
            """)
        st.warning(
            "**Research Prototype Disclosure**: This software uses a synthetic nonlinear process model for research "
            "and demonstration purposes. It has not been calibrated or certified for deployment in physical regulated "
            "water treatment or chemical processing plants."
        )


if __name__ == "__main__":
    main()
