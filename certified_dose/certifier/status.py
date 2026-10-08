from enum import StrEnum


class CertificationStatus(StrEnum):
    """Outcome status of the formal certification check.

    ACCEPTED: Proposed dose was verified safe within the compliance envelope.

    REJECTED_CORRECTED: Proposed dose violated the compliance envelope; a safe
        replacement dose was found via bisection search.

    FAILED_SAFE_FALLBACK: Computation failed or timed out; the conservative
        fallback dose was applied as a fail-safe.

    OUTSIDE_MODEL_VALIDITY: The pH disturbance interval lies outside the
        valid operating range for the single-chemical alum coagulation model.
        The model cannot make a trustworthy safety claim at all -- not that
        there is no safe dose, but that the model's assumptions about aluminum
        speciation are violated and any certification would be meaningless.
        This is distinct from FAILED_SAFE_FALLBACK (computational failure)
        and REJECTED_CORRECTED (correctable dose problem). The correct
        operator response is acid pre-treatment or pH adjustment to re-enter
        the alum coagulation window, NOT increasing coagulant dose.
    """

    ACCEPTED = "ACCEPTED"
    REJECTED_CORRECTED = "REJECTED_CORRECTED"
    FAILED_SAFE_FALLBACK = "FAILED_SAFE_FALLBACK"
    OUTSIDE_MODEL_VALIDITY = "OUTSIDE_MODEL_VALIDITY"
