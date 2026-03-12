"""Unit tests for dispatch_delivery payload builder."""

import pytest
from vda5050_fleet_adapter.scripts.dispatch_delivery import (
    build_delivery_payload,
)


class TestBuildDeliveryPayload:
    """Tests for build_delivery_payload()."""

    @pytest.fixture()
    def base_payload(self) -> dict:
        """Return a payload built with default dispatch_task_request."""
        return build_delivery_payload(
            pickup='station_A',
            dropoff='station_B',
            load_type='Tool',
            load_id='SP4ECTR002',
            station_name='1004',
        )

    def test_dispatch_task_request_type(self, base_payload: dict) -> None:
        """Without fleet/robot, type should be dispatch_task_request."""
        assert base_payload['type'] == 'dispatch_task_request'
        assert 'robot' not in base_payload
        assert 'fleet' not in base_payload

    def test_robot_task_request_type(self) -> None:
        """With fleet and robot, type should be robot_task_request."""
        payload = build_delivery_payload(
            pickup='A', dropoff='B',
            load_type='Tool', load_id='C001', station_name='S1',
            fleet='vda5050_fleet', robot='AGV_001',
        )
        assert payload['type'] == 'robot_task_request'
        assert payload['fleet'] == 'vda5050_fleet'
        assert payload['robot'] == 'AGV_001'

    def test_compose_category(self, base_payload: dict) -> None:
        """Request category should be 'compose'."""
        assert base_payload['request']['category'] == 'compose'

    def test_description_category(self, base_payload: dict) -> None:
        """Description category should be 'delivery'."""
        desc = base_payload['request']['description']
        assert desc['category'] == 'delivery'

    def test_two_phases(self, base_payload: dict) -> None:
        """Payload should contain exactly two phases."""
        phases = base_payload['request']['description']['phases']
        assert len(phases) == 2

    def test_phase1_go_to_pickup(self, base_payload: dict) -> None:
        """Phase 1 first activity should go to pickup location."""
        phase1 = base_payload['request']['description']['phases'][0]
        activities = phase1['activity']['description']['activities']
        assert activities[0]['category'] == 'go_to_place'
        assert activities[0]['description'] == 'station_A'

    def test_phase1_pick_action(self, base_payload: dict) -> None:
        """Phase 1 second activity should be a pick action."""
        phase1 = base_payload['request']['description']['phases'][0]
        activities = phase1['activity']['description']['activities']
        action = activities[1]
        assert action['category'] == 'perform_action'
        assert action['description']['category'] == 'pick'
        desc = action['description']['description']
        assert desc['loadType'] == 'Tool'
        assert desc['loadID'] == 'SP4ECTR002'

    def test_phase2_go_to_dropoff(self, base_payload: dict) -> None:
        """Phase 2 first activity should go to dropoff location."""
        phase2 = base_payload['request']['description']['phases'][1]
        activities = phase2['activity']['description']['activities']
        assert activities[0]['category'] == 'go_to_place'
        assert activities[0]['description'] == 'station_B'

    def test_phase2_drop_action(self, base_payload: dict) -> None:
        """Phase 2 second activity should be a drop action."""
        phase2 = base_payload['request']['description']['phases'][1]
        activities = phase2['activity']['description']['activities']
        action = activities[1]
        assert action['category'] == 'perform_action'
        assert action['description']['category'] == 'drop'
        desc = action['description']['description']
        assert desc['stationName'] == '1004'

    def test_action_duration_estimate(self, base_payload: dict) -> None:
        """Both actions should have 10s duration estimate."""
        phases = base_payload['request']['description']['phases']
        for phase in phases:
            activities = phase['activity']['description']['activities']
            action_desc = activities[1]['description']
            assert action_desc[
                'unix_millis_action_duration_estimate'] == 10000

    def test_start_time(self) -> None:
        """Start time should be passed through."""
        payload = build_delivery_payload(
            pickup='A', dropoff='B',
            load_type='T', load_id='C', station_name='S',
            start_time_ms=42000,
        )
        assert payload['request'][
            'unix_millis_earliest_start_time'] == 42000

    def test_priority_included_when_nonzero(self) -> None:
        """Priority should be included when non-zero."""
        payload = build_delivery_payload(
            pickup='A', dropoff='B',
            load_type='T', load_id='C', station_name='S',
            priority=5,
        )
        assert payload['request']['priority'] == {'value': 5}

    def test_priority_omitted_when_zero(self, base_payload: dict) -> None:
        """Priority should not be in request when zero (default)."""
        assert 'priority' not in base_payload['request']

    def test_sequence_activity_structure(self, base_payload: dict) -> None:
        """Each phase should use sequence activity category."""
        for phase in base_payload['request']['description']['phases']:
            assert phase['activity']['category'] == 'sequence'
            assert 'activities' in phase['activity']['description']

    def test_use_tool_sink_false(self, base_payload: dict) -> None:
        """Both actions should have use_tool_sink set to False."""
        phases = base_payload['request']['description']['phases']
        for phase in phases:
            activities = phase['activity']['description']['activities']
            action_desc = activities[1]['description']
            assert action_desc['use_tool_sink'] is False
