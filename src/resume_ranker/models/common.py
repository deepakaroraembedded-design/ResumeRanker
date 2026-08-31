from __future__ import annotations

from dataclasses import dataclass

from pydantic.dataclasses import dataclass as pydantic_dataclass


@pydantic_dataclass(frozen=True)
class Diagnostic:
    """A machine-readable diagnostic attached to a stage result.

    Attributes:
        stage: Pipeline stage identifier, e.g. "S1" .. "S9".
        code: Reason code from the collected code registry.
        message: Human-readable description.
        fatal: Whether the diagnostic aborts the run.  Stages should almost
            always keep fatal=False; only JobSpec compilation is fatal per TRD §2.5.
    """

    stage: str
    code: str
    message: str
    fatal: bool = False


@dataclass(frozen=True, slots=True)
class StageResult[T]:
    """Every stage returns this.

    A stage NEVER raises for bad input data — it returns value=None plus
    diagnostics.  Raising is reserved for programmer errors.

    Attributes:
        value: The stage output, or None if the stage could not produce one.
        diagnostics: Zero or more diagnostic records.
    """

    value: T | None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        """True iff the stage produced a value."""
        return self.value is not None


@pydantic_dataclass(frozen=True)
class IntegrityFinding:
    """A finding produced by an integrity detector.

    Detectors only report; they never apply penalties.
    """

    detector: str
    code: str
    message: str
    spans: tuple[tuple[int, int], ...] = ()
    quotes: tuple[str, ...] = ()


ReidentificationMap = dict[str, str]
