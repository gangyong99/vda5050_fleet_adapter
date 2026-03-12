"""AgvState 엔티티 단위 테스트."""

from vda5050_fleet_adapter.domain.entities.agv_state import AgvState
from vda5050_fleet_adapter.domain.entities.error import AgvError
from vda5050_fleet_adapter.domain.entities.safety import SafetyState
from vda5050_fleet_adapter.domain.enums import (
    ErrorLevel,
    EStopType,
)


class TestAgvStateProperties:
    def test_has_active_order_true(self, sample_agv_state):
        assert sample_agv_state.has_active_order is True

    def test_has_active_order_false(self, sample_header):
        state = AgvState(header=sample_header, order_id='')
        assert state.has_active_order is False

    def test_has_errors_false(self, sample_agv_state):
        assert sample_agv_state.has_errors is False

    def test_has_errors_true(self, sample_agv_state):
        sample_agv_state.errors.append(
            AgvError(error_type='test', error_level=ErrorLevel.WARNING)
        )
        assert sample_agv_state.has_errors is True

    def test_has_fatal_error(self, sample_agv_state):
        assert sample_agv_state.has_fatal_error is False
        sample_agv_state.errors.append(
            AgvError(error_type='fatal', error_level=ErrorLevel.FATAL)
        )
        assert sample_agv_state.has_fatal_error is True

    def test_is_emergency_stopped_false(self, sample_agv_state):
        assert sample_agv_state.is_emergency_stopped is False

    def test_is_emergency_stopped_true(self, sample_header):
        state = AgvState(
            header=sample_header,
            safety_state=SafetyState(e_stop=EStopType.MANUAL),
        )
        assert state.is_emergency_stopped is True


class TestAgvStateGetActionState:
    def test_get_existing_action(self, sample_agv_state):
        result = sample_agv_state.get_action_state('a1')
        assert result is not None
        assert result.action_type == 'pick'

    def test_get_nonexistent_action(self, sample_agv_state):
        result = sample_agv_state.get_action_state('nonexistent')
        assert result is None
