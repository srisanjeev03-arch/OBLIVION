from enum import Enum, auto


class State(Enum):
    CREATED = auto()
    ANALYZING = auto()
    PENDING_APPROVAL = auto()
    READY = auto()
    ERASING = auto()
    VERIFYING = auto()
    RECOVERY_TEST = auto()
    RESIDUAL_SCAN = auto()
    RESIDUAL_ANALYSIS = auto()
    ASSESSING = auto()
    CERTIFYING = auto()

    #: The process stopped while an operation was in flight, so the persisted
    #: state and the filesystem may disagree. Deliberately NOT terminal: it means
    #: "nobody has established what happened yet", and something must look. A
    #: crashed operation left in ERASING would be indistinguishable from one
    #: still running, and one silently marked FAILED would assert that nothing
    #: was destroyed - which is exactly what is not yet known.
    RECONCILIATION_REQUIRED = auto()

    COMPLETED = auto()
    PARTIAL = auto()
    FAILED = auto()
    INCONCLUSIVE = auto()
    CANCELLED = auto()

class StateMachineError(Exception):
    pass

class OperationStateMachine:
    def __init__(self, initial_state: State = State.CREATED):
        self._current_state = initial_state

        # Valid transitions
        self._transitions: dict[State, set[State]] = {
            State.CREATED: {State.ANALYZING, State.PENDING_APPROVAL, State.READY, State.FAILED, State.CANCELLED},
            State.ANALYZING: {State.PENDING_APPROVAL, State.READY, State.RESIDUAL_ANALYSIS, State.FAILED, State.CANCELLED},
            State.PENDING_APPROVAL: {State.READY, State.FAILED, State.CANCELLED},
            State.READY: {State.ERASING, State.RESIDUAL_ANALYSIS, State.FAILED, State.CANCELLED},
            State.ERASING: {State.VERIFYING, State.PARTIAL, State.FAILED, State.CANCELLED},
            State.VERIFYING: {State.COMPLETED, State.RECOVERY_TEST, State.RESIDUAL_ANALYSIS, State.PARTIAL, State.FAILED, State.CANCELLED},
            State.RECOVERY_TEST: {State.RESIDUAL_SCAN, State.RESIDUAL_ANALYSIS, State.PARTIAL, State.FAILED, State.CANCELLED},
            State.RESIDUAL_SCAN: {State.ASSESSING, State.PARTIAL, State.FAILED, State.CANCELLED},
            State.RESIDUAL_ANALYSIS: {State.VERIFYING, State.PARTIAL, State.FAILED, State.INCONCLUSIVE, State.CANCELLED},
            State.ASSESSING: {State.CERTIFYING, State.INCONCLUSIVE, State.FAILED, State.CANCELLED},
            State.CERTIFYING: {State.COMPLETED, State.FAILED, State.CANCELLED},
            # Reconciliation resolves to a definite outcome, or to INCONCLUSIVE
            # when the filesystem cannot answer. It never returns to an
            # in-flight state: the work that was interrupted is not resumed by
            # deciding what happened to it.
            State.RECONCILIATION_REQUIRED: {
                State.COMPLETED,
                State.PARTIAL,
                State.FAILED,
                State.INCONCLUSIVE,
                State.CANCELLED,
            },
        }

        # Any stage that can be interrupted mid-flight may land here. Approval
        # stages are excluded on purpose: nothing destructive has happened
        # before READY, so an interrupted approval is simply not approved.
        for interruptible in (
            State.ERASING,
            State.VERIFYING,
            State.RECOVERY_TEST,
            State.RESIDUAL_SCAN,
            State.RESIDUAL_ANALYSIS,
            State.ASSESSING,
            State.CERTIFYING,
        ):
            self._transitions[interruptible].add(State.RECONCILIATION_REQUIRED)


        self._terminal_states = {
            State.COMPLETED,
            State.PARTIAL,
            State.FAILED,
            State.INCONCLUSIVE,
            State.CANCELLED
        }

    @property
    def current_state(self) -> State:
        return self._current_state

    def transition_to(self, new_state: State) -> None:
        if self._current_state in self._terminal_states:
            raise StateMachineError(f"Cannot transition from terminal state: {self._current_state.name}")

        allowed_transitions = self._transitions.get(self._current_state, set())

        if new_state not in allowed_transitions:
            raise StateMachineError(
                f"Invalid transition from {self._current_state.name} to {new_state.name}"
            )

        self._current_state = new_state

    def is_terminal(self) -> bool:
        return self._current_state in self._terminal_states
