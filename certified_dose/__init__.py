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
from certified_dose.process_model import (
    ModelParameters,
    ProcessModel,
    SyntheticProcessModel,
)
from certified_dose.reachability import ReachabilityEngine, ReachableSet
from certified_dose.simulate import (
    ClosedLoopSimulator,
    SimulationRecord,
    SimulationSummary,
    simulate_closed_loop,
)
from certified_dose.validation import (
    BENCHMARK_DATASETS,
    DATASET_EDWARDS_1997,
    DATASET_VAN_BENSCHOTEN_1990,
    EmpiricalDataset,
    ModelValidationReport,
    validate_all_datasets,
    validate_synthetic_model,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "Interval",
    "AffineForm",
    "ProcessModel",
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
    "EmpiricalDataset",
    "DATASET_EDWARDS_1997",
    "DATASET_VAN_BENSCHOTEN_1990",
    "BENCHMARK_DATASETS",
    "ModelValidationReport",
    "validate_synthetic_model",
    "validate_all_datasets",
]
