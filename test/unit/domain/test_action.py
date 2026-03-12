"""Action 엔티티 단위 테스트."""

import pytest

from vda5050_fleet_adapter.domain.entities.action import (
    Action,
    ActionParameter,
    ActionState,
)
from vda5050_fleet_adapter.domain.enums import ActionStatus, BlockingType
from vda5050_fleet_adapter.domain.exceptions import (
    InvalidStateTransitionError,
)


class TestAction:
    def test_construction(self):
        action = Action(
            action_type='pick',
            action_id='a1',
            blocking_type=BlockingType.HARD,
            action_parameters=[
                ActionParameter(key='stationType', value='floor'),
            ],
        )
        assert action.action_type == 'pick'
        assert action.blocking_type == BlockingType.HARD
        assert len(action.action_parameters) == 1


class TestActionState:
    def test_initial_status_is_waiting(self):
        state = ActionState(action_id='a1', action_type='pick')
        assert state.action_status == ActionStatus.WAITING

    def test_valid_transition_waiting_to_initializing(self):
        state = ActionState(action_id='a1', action_type='pick')
        state.transition_to(ActionStatus.INITIALIZING)
        assert state.action_status == ActionStatus.INITIALIZING

    def test_valid_full_lifecycle(self):
        state = ActionState(action_id='a1', action_type='pick')
        state.transition_to(ActionStatus.INITIALIZING)
        state.transition_to(ActionStatus.RUNNING)
        state.transition_to(ActionStatus.PAUSED)
        state.transition_to(ActionStatus.RUNNING)
        state.transition_to(ActionStatus.FINISHED)
        assert state.action_status == ActionStatus.FINISHED

    def test_valid_transition_to_failed_from_any_active(self):
        for start in [
            ActionStatus.WAITING,
            ActionStatus.INITIALIZING,
            ActionStatus.RUNNING,
            ActionStatus.PAUSED,
        ]:
            state = ActionState(
                action_id='a1', action_type='test',
                action_status=start,
            )
            state.transition_to(ActionStatus.FAILED)
            assert state.action_status == ActionStatus.FAILED

    def test_invalid_transition_waiting_to_finished(self):
        state = ActionState(action_id='a1', action_type='pick')
        with pytest.raises(InvalidStateTransitionError):
            state.transition_to(ActionStatus.FINISHED)

    def test_invalid_transition_waiting_to_running(self):
        state = ActionState(action_id='a1', action_type='pick')
        with pytest.raises(InvalidStateTransitionError):
            state.transition_to(ActionStatus.RUNNING)

    def test_invalid_transition_finished_to_running(self):
        state = ActionState(
            action_id='a1', action_type='pick',
            action_status=ActionStatus.FINISHED,
        )
        with pytest.raises(InvalidStateTransitionError):
            state.transition_to(ActionStatus.RUNNING)

    def test_invalid_transition_failed_is_terminal(self):
        state = ActionState(
            action_id='a1', action_type='pick',
            action_status=ActionStatus.FAILED,
        )
        with pytest.raises(InvalidStateTransitionError):
            state.transition_to(ActionStatus.RUNNING)

    def test_error_message_contains_details(self):
        state = ActionState(action_id='xyz', action_type='pick')
        with pytest.raises(InvalidStateTransitionError, match='xyz'):
            state.transition_to(ActionStatus.FINISHED)
