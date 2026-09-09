import pytest
from oblivion.core.state.machine import OperationStateMachine, State, StateMachineError

def test_valid_linear_flow():
    sm = OperationStateMachine()
    assert sm.current_state == State.CREATED

    sm.transition_to(State.ANALYZING)
    assert sm.current_state == State.ANALYZING

    sm.transition_to(State.READY)
    assert sm.current_state == State.READY

    sm.transition_to(State.ERASING)
    assert sm.current_state == State.ERASING

    sm.transition_to(State.VERIFYING)
    assert sm.current_state == State.VERIFYING

    sm.transition_to(State.RECOVERY_TEST)
    assert sm.current_state == State.RECOVERY_TEST

    sm.transition_to(State.RESIDUAL_SCAN)
    assert sm.current_state == State.RESIDUAL_SCAN

    sm.transition_to(State.ASSESSING)
    assert sm.current_state == State.ASSESSING

    sm.transition_to(State.CERTIFYING)
    assert sm.current_state == State.CERTIFYING

    sm.transition_to(State.COMPLETED)
    assert sm.current_state == State.COMPLETED
    assert sm.is_terminal()

def test_invalid_transition():
    sm = OperationStateMachine()
    with pytest.raises(StateMachineError):
        sm.transition_to(State.ERASING)

def test_transition_from_terminal_state():
    sm = OperationStateMachine()
    sm.transition_to(State.ANALYZING)
    sm.transition_to(State.FAILED)
    assert sm.is_terminal()

    with pytest.raises(StateMachineError):
        sm.transition_to(State.READY)

def test_terminal_states():
    sm = OperationStateMachine()
    sm.transition_to(State.ANALYZING)
    sm.transition_to(State.CANCELLED)
    assert sm.current_state == State.CANCELLED
    assert sm.is_terminal()
