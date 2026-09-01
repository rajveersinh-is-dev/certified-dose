"""certified-dose: Formal reachability-analysis safety layer for chemical dosing.

Every dosing action is provably guaranteed to keep the process output within a
regulatory compliance envelope under bounded input uncertainty.
"""

from certified_dose.certifier import (
    CertificationResult,
    CertificationStatus,
    CertifiedDoseWrapper,
    WrappedControllerProtocol,
)
from certified_dose.controller import (
    AdversarialController,
    AggressiveCostMinimizerController,
    BaseController,
    ConstantDoseController,
    HeuristicController,
    PlantState,
)
from certified_dose.intervals import AffineForm, Interval
from certified_dose.process_model import ModelParameters, SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine, ReachableSet
from certified_dose.simulate import (
    ClosedLoopSimulator,
    SimulationRecord,
    SimulationSummary,
    simulate_closed_loop,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Interval",
    "AffineForm",
    "ModelParameters",
    "SyntheticProcessModel",
    "ReachabilityEngine",
    "ReachableSet",
    "PlantState",
    "BaseController",
    "HeuristicController",
    "AggressiveCostMinimizerController",
    "AdversarialController",
    "ConstantDoseController",
    "CertificationStatus",
    "CertificationResult",
    "CertifiedDoseWrapper",
    "WrappedControllerProtocol",
    "SimulationRecord",
    "SimulationSummary",
    "ClosedLoopSimulator",
    "simulate_closed_loop",
]
