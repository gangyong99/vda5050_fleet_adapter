"""RobotAdapter 유닛 테스트."""

from unittest.mock import MagicMock

import pytest

from vda5050_fleet_adapter.usecase.ports.robot_api import (
    CommissionState,
    RobotAPIResult,
    RobotUpdateData,
)
from vda5050_fleet_adapter.usecase.robot_adapter import RobotAdapter


@pytest.fixture
def mock_api():
    """Mock RobotAPI."""
    api = MagicMock()
    api.navigate.return_value = RobotAPIResult.SUCCESS
    api.stop.return_value = RobotAPIResult.SUCCESS
    api.pause.return_value = RobotAPIResult.SUCCESS
    api.start_activity.return_value = RobotAPIResult.SUCCESS
    api.is_command_completed.return_value = False
    api.get_data.return_value = RobotUpdateData(
        robot_name='AGV-001',
        map_name='map1',
        position=[1.0, 2.0, 0.0],
        battery_soc=0.85,
    )
    return api


@pytest.fixture
def mock_node():
    """Mock ROS 2 node."""
    node = MagicMock()
    node.get_logger.return_value = MagicMock()
    node.get_clock.return_value = MagicMock()
    return node


@pytest.fixture
def adapter(mock_api, mock_node, sample_nav_nodes, sample_nav_edges):
    """Create RobotAdapter instance with mocks."""
    from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
        create_graph,
    )
    graph = create_graph(sample_nav_nodes, sample_nav_edges)
    robot = RobotAdapter(
        name='AGV-001',
        api=mock_api,
        node=mock_node,
        fleet_handle=MagicMock(),
        nav_nodes=sample_nav_nodes,
        nav_edges=sample_nav_edges,
        nav_graph=graph,
    )
    robot.configuration = MagicMock()
    return robot


class TestRobotAdapterNavigate:
    """navigate() 테스트."""

    def test_navigate_increments_cmd_id(self, adapter):
        """Navigate 호출 시 cmd_id가 증가한다."""
        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        initial_cmd_id = adapter.cmd_id
        adapter.navigate(dest, execution)

        assert adapter.cmd_id == initial_cmd_id + 1

    def test_navigate_sets_execution(self, adapter):
        """Navigate 호출 시 execution이 설정된다."""
        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter.navigate(dest, execution)

        assert adapter.execution is execution

    def test_navigate_calls_api(self, adapter, mock_api):
        """navigate가 API.navigate를 호출한다."""
        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter.navigate(dest, execution)
        # attempt_cmd_until_success가 스레드에서 호출하므로 잠시 대기
        adapter.cancel_cmd_attempt()

        mock_api.navigate.assert_called_once()
        call_args = mock_api.navigate.call_args
        assert call_args[0][0] == 'AGV-001'  # robot_name
        assert call_args[0][1] == 1  # cmd_id

    def test_navigate_creates_new_order(self, adapter):
        """첫 navigate 시 _active_order_id가 생성된다."""
        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        assert adapter._order.active_order_id is None
        adapter.navigate(dest, execution)
        adapter.cancel_cmd_attempt()

        assert adapter._order.active_order_id is not None
        assert adapter._order.active_order_id.startswith('order_')
        assert adapter._order.order_update_id == 0
        assert adapter._order.final_destination is not None

    def test_navigate_updates_existing_order(self, adapter):
        """두 번째 navigate 시 같은 orderID, update_id 증가."""
        dest1 = MagicMock()
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()

        adapter.navigate(dest1, exec1)
        adapter.cancel_cmd_attempt()

        first_order_id = adapter._order.active_order_id
        first_final_dest = adapter._order.final_destination

        dest2 = MagicMock()
        dest2.position = [0.0, 0.0, 0.0]
        dest2.map = 'map1'
        exec2 = MagicMock()

        adapter.navigate(dest2, exec2)
        adapter.cancel_cmd_attempt()

        assert adapter._order.active_order_id == first_order_id
        assert adapter._order.order_update_id == 1
        assert adapter._order.final_destination == first_final_dest

    def test_navigate_passes_order_id_to_api(self, adapter, mock_api):
        """navigate가 order_id와 order_update_id를 API에 전달한다."""
        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter.navigate(dest, execution)
        adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        # args: (name, cmd_id, nodes, edges, map, order_id, update_id)
        assert len(call_args) == 7
        assert call_args[5].startswith('order_')  # order_id
        assert call_args[6] == 0  # order_update_id


class TestRobotAdapterStop:
    """stop() 테스트."""

    def test_stop_clears_execution(self, adapter, mock_api):
        """Stop 호출 시 execution이 None이 된다."""
        execution = MagicMock()
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        adapter.execution = execution

        adapter.stop(activity)
        adapter.cancel_cmd_attempt()

        assert adapter.execution is None

    def test_stop_increments_cmd_id(self, adapter, mock_api):
        """Stop 호출 시 cmd_id가 증가한다."""
        execution = MagicMock()
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        adapter.execution = execution
        initial_cmd_id = adapter.cmd_id

        adapter.stop(activity)
        adapter.cancel_cmd_attempt()

        assert adapter.cmd_id == initial_cmd_id + 1

    def test_stop_sends_pause_not_cancel(self, adapter, mock_api):
        """Stop 호출 시 startPause를 전송한다 (cancelOrder 아님)."""
        execution = MagicMock()
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        adapter.execution = execution

        adapter.stop(activity)
        adapter.cancel_cmd_attempt()

        mock_api.pause.assert_called_once()
        mock_api.stop.assert_not_called()

    def test_stop_sets_paused_for_negotiation(self, adapter, mock_api):
        """Stop 호출 시 _is_paused_for_negotiation이 True가 된다."""
        execution = MagicMock()
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        adapter.execution = execution

        adapter.stop(activity)
        adapter.cancel_cmd_attempt()

        assert adapter._is_paused_for_negotiation is True

    def test_stop_preserves_order_state(self, adapter, mock_api):
        """Stop 호출 시 order 상태가 유지된다 (negotiation 대비)."""
        execution = MagicMock()
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        adapter.execution = execution
        adapter._order.active_order_id = 'order_1_abc'
        adapter._order.order_update_id = 2
        adapter._order.final_destination = 'wp3'

        adapter.stop(activity)
        adapter.cancel_cmd_attempt()

        assert adapter._order.active_order_id == 'order_1_abc'
        assert adapter._order.order_update_id == 2
        assert adapter._order.final_destination == 'wp3'

    def test_stop_ignores_different_activity(self, adapter, mock_api):
        """다른 activity에 대한 stop은 무시된다."""
        execution = MagicMock()
        activity = MagicMock()
        execution.identifier.is_same.return_value = False
        adapter.execution = execution

        adapter.stop(activity)

        assert adapter.execution is execution
        mock_api.pause.assert_not_called()
        mock_api.stop.assert_not_called()


class TestRobotAdapterExecuteAction:
    """execute_action() 테스트."""

    def test_execute_action_increments_cmd_id(self, adapter):
        """execute_action 호출 시 cmd_id가 증가한다."""
        execution = MagicMock()
        initial_cmd_id = adapter.cmd_id

        adapter.execute_action('charge', {}, execution)
        adapter.cancel_cmd_attempt()

        assert adapter.cmd_id == initial_cmd_id + 1

    def test_execute_action_sets_execution(self, adapter):
        """execute_action 호출 시 execution이 설정된다."""
        execution = MagicMock()

        adapter.execute_action('teleop', {}, execution)
        adapter.cancel_cmd_attempt()

        assert adapter.execution is execution

    def test_execute_action_calls_api(self, adapter, mock_api):
        """execute_action이 API.start_activity를 호출한다."""
        execution = MagicMock()
        params = {'zone': 'A'}

        adapter.execute_action('clean', params, execution)
        adapter.cancel_cmd_attempt()

        mock_api.start_activity.assert_called_once()
        call_args = mock_api.start_activity.call_args
        assert call_args[0][0] == 'AGV-001'
        assert call_args[0][2] == 'clean'
        assert call_args[0][3] == {'zone': 'A'}


class TestRobotAdapterUpdate:
    """update() 테스트."""

    def test_update_completes_navigate_by_distance(
        self, adapter, mock_api
    ):
        """Navigate 도착 판정: 거리 threshold 이내면 완료."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.cmd_id = 5
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [1.0, 2.0]

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.1, 2.1, 0.0],  # dist ~0.14, within 0.5
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_called_once()
        assert adapter.execution is None
        assert adapter._nav.is_navigating is False
        assert adapter._nav.target_position is None

    def test_completion_preserves_order_during_task(
        self, adapter, mock_api
    ):
        """명령 완료 시 task 중에는 order 상태가 유지된다."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.cmd_id = 5
        mock_update_handle = MagicMock()
        mock_update_handle.more.return_value.current_task_id \
            .return_value = 'compose.dispatch-001'
        adapter.update_handle = mock_update_handle
        adapter._order.active_order_id = 'order_5_abc'
        adapter._order.order_update_id = 1
        adapter._order.final_destination = 'wp3'
        adapter._order.current_task_id = 'compose.dispatch-001'
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [1.0, 2.0]

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.0, 2.0, 0.0],  # exact match
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_called_once()
        assert adapter.execution is None
        # Order state preserved (task still active)
        assert adapter._order.active_order_id == 'order_5_abc'

    def test_completion_resets_order_when_task_ends(
        self, adapter, mock_api
    ):
        """Task 완료 시 order 상태가 초기화된다."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.cmd_id = 5
        mock_update_handle = MagicMock()
        # current_task_id returns empty string (task ended)
        mock_update_handle.more.return_value.current_task_id \
            .return_value = ''
        adapter.update_handle = mock_update_handle
        adapter._order.active_order_id = 'order_5_abc'
        adapter._order.order_update_id = 1
        adapter._order.final_destination = 'wp3'
        adapter._order.current_task_id = 'compose.dispatch-001'
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [1.0, 2.0]

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.0, 2.0, 0.0],  # at target
            battery_soc=0.85,
        )

        adapter.update(state, data)
        adapter.cancel_cmd_attempt()

        assert adapter._order.active_order_id is None
        assert adapter._order.order_update_id == 0
        assert adapter._order.final_destination is None
        # 정상 도착이므로 cancelOrder 미전송
        mock_api.stop.assert_not_called()

    def test_update_keeps_execution_if_not_completed(
        self, adapter, mock_api
    ):
        """Navigate 미완료 시 (거리 초과) execution이 유지된다."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.cmd_id = 5
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [10.0, 10.0]

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.0, 2.0, 0.0],  # far from target
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_not_called()
        assert adapter.execution is execution

    def test_update_sends_state_to_rmf(self, adapter, mock_api):
        """update가 update_handle.update()를 호출한다."""
        adapter.update_handle = MagicMock()

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.0, 2.0, 0.0],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        adapter.update_handle.update.assert_called_once()

    def test_update_tracks_position(self, adapter, mock_api):
        """update가 position을 캐시한다."""
        adapter.update_handle = MagicMock()

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[3.0, 4.0, 1.5],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        assert adapter.position == [3.0, 4.0, 1.5]

    def test_update_sets_commission_on_state_change(
        self, adapter, mock_api
    ):
        """Commission 상태 변경 시 set_commission이 호출된다."""
        update_handle = MagicMock()
        more_handle = MagicMock()
        commission_obj = MagicMock()
        more_handle.commission.return_value = commission_obj
        update_handle.more.return_value = more_handle
        adapter.update_handle = update_handle

        mock_api.get_commission_state.return_value = CommissionState(
            False, False, False
        )

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.0, 2.0, 0.0],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        more_handle.commission.assert_called_once()
        more_handle.set_commission.assert_called_once_with(commission_obj)
        assert adapter._last_commission == CommissionState(
            False, False, False
        )

    def test_update_skips_commission_when_unchanged(
        self, adapter, mock_api
    ):
        """동일 commission 상태 시 set_commission이 호출되지 않는다."""
        update_handle = MagicMock()
        adapter.update_handle = update_handle

        commission = CommissionState(True, True, True)
        mock_api.get_commission_state.return_value = commission
        adapter._last_commission = commission

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.0, 2.0, 0.0],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        update_handle.set_commission.assert_not_called()

    def test_update_skips_commission_when_none(self, adapter, mock_api):
        """Commission None 시 set_commission이 호출되지 않는다."""
        update_handle = MagicMock()
        adapter.update_handle = update_handle

        mock_api.get_commission_state.return_value = None

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001',
            map_name='map1',
            position=[1.0, 2.0, 0.0],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        update_handle.set_commission.assert_not_called()


class TestDistanceBasedArrival:
    """거리 기반 도착 판정 테스트."""

    def test_navigate_within_threshold_completes(
        self, adapter, mock_api
    ):
        """Navigate: threshold 이내 → 도착 완료."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 5.0]
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.3, 5.3, 0.0],  # dist ~0.42
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_called_once()
        assert adapter.execution is None

    def test_navigate_beyond_threshold_not_completed(
        self, adapter, mock_api
    ):
        """Navigate: threshold 초과 → 미완료."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 5.0]
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[4.0, 4.0, 0.0],  # dist ~1.41
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_not_called()
        assert adapter.execution is execution

    def test_navigate_exact_threshold_completes(
        self, adapter, mock_api
    ):
        """Navigate: 정확히 threshold 거리 → 도착 완료."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.5, 0.0, 0.0],  # dist = 0.5
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_called_once()
        assert adapter.execution is None

    def test_action_uses_is_command_completed(
        self, adapter, mock_api
    ):
        """Action은 기존 is_command_completed 방식을 사용한다."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.cmd_id = 5
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = False
        mock_api.is_command_completed.return_value = True

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[100.0, 100.0, 0.0],  # far away, irrelevant
            battery_soc=0.85,
        )

        adapter.update(state, data)

        mock_api.is_command_completed.assert_called_once_with(
            'AGV-001', 5
        )
        execution.finished.assert_called_once()
        assert adapter.execution is None

    def test_action_not_completed(self, adapter, mock_api):
        """Action 미완료 시 execution이 유지된다."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.cmd_id = 5
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = False
        mock_api.is_command_completed.return_value = False

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[1.0, 2.0, 0.0],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_not_called()
        assert adapter.execution is execution

    def test_navigate_sets_target_position(self, adapter):
        """navigate() 호출 시 base end node 좌표로 설정된다."""
        dest = MagicMock()
        dest.position = [5.0, 3.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter.navigate(dest, execution)
        adapter.cancel_cmd_attempt()

        # goal_node=wp3(5,5) — dest.position(5,3)에 가장 가까운 노드
        assert adapter._nav.target_position == [5.0, 5.0]
        assert adapter._nav.is_navigating is True

    def test_execute_action_clears_navigating(self, adapter):
        """execute_action() 호출 시 _is_navigating이 False가 된다."""
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 3.0]
        execution = MagicMock()

        adapter.execute_action('charge', {}, execution)
        adapter.cancel_cmd_attempt()

        assert adapter._nav.is_navigating is False

    def test_custom_arrival_threshold(
        self, mock_api, mock_node,
        sample_nav_nodes, sample_nav_edges,
    ):
        """커스텀 arrival_threshold가 적용된다."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        graph = create_graph(sample_nav_nodes, sample_nav_edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=sample_nav_nodes,
            nav_edges=sample_nav_edges,
            nav_graph=graph,
            arrival_threshold=1.0,
        )
        robot.update_handle = MagicMock()

        execution = MagicMock()
        robot.execution = execution
        robot._nav.is_navigating = True
        robot._nav.target_position = [5.0, 0.0]

        state = MagicMock()
        # dist = 0.8, within 1.0 threshold
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.8, 0.0, 0.0], battery_soc=0.85,
        )

        robot.update(state, data)

        execution.finished.assert_called_once()

    def test_reset_order_clears_navigate_state(self, adapter):
        """_reset_order_state가 navigate 상태를 초기화한다."""
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 3.0]

        adapter._reset_order_state()

        assert adapter._nav.is_navigating is False
        assert adapter._nav.target_position is None


class TestThetaBasedArrival:
    """Theta 기반 도착 판정 테스트."""

    def test_theta_ok_completes(self, adapter, mock_api):
        """거리 OK + theta OK → 도착 완료."""
        import math
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]
        adapter._nav.target_theta = math.pi / 2
        adapter.allowed_deviation_theta = math.radians(15)
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 0.0, math.pi / 2],  # exact theta
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_called_once()
        assert adapter.execution is None

    def test_theta_ng_not_completed(self, adapter, mock_api):
        """거리 OK + theta NG → 미도착."""
        import math
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]
        adapter._nav.target_theta = math.pi / 2
        adapter.allowed_deviation_theta = math.radians(15)
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 0.0, 0.0],  # theta off by π/2
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_not_called()
        assert adapter.execution is execution

    def test_no_theta_distance_only(self, adapter, mock_api):
        """Theta 미설정 시 거리 기반 도착 (기존 동작)."""
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]
        adapter._nav.target_theta = None
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 0.0, 0.0],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_called_once()
        assert adapter.execution is None

    def test_theta_within_deviation_completes(self, adapter, mock_api):
        """theta가 허용 오차 내이면 도착 완료."""
        import math
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]
        adapter._nav.target_theta = math.pi / 2
        adapter.allowed_deviation_theta = math.radians(15)
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            # theta off by 10° (< 15° threshold)
            position=[5.0, 0.0, math.pi / 2 + math.radians(10)],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        execution.finished.assert_called_once()

    def test_theta_reset_on_completion(self, adapter, mock_api):
        """도착 완료 시 _navigate_target_theta가 None으로 리셋."""
        import math
        execution = MagicMock()
        adapter.execution = execution
        adapter.update_handle = MagicMock()
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]
        adapter._nav.target_theta = math.pi / 2
        adapter.allowed_deviation_theta = math.radians(15)
        adapter.arrival_threshold = 0.5

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 0.0, math.pi / 2],
            battery_soc=0.85,
        )

        adapter.update(state, data)

        assert adapter._nav.target_theta is None

    def test_theta_reset_on_order_reset(self, adapter):
        """_reset_order_state가 _navigate_target_theta를 리셋."""
        import math
        adapter._nav.target_theta = math.pi / 2

        adapter._reset_order_state()

        assert adapter._nav.target_theta is None


class TestRobotAdapterRetry:
    """attempt_cmd_until_success() 테스트."""

    def test_retry_on_failure(self, adapter, mock_api):
        """API 실패 시 재시도한다."""
        call_count = 0

        def failing_then_success(*args):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return RobotAPIResult.SUCCESS
            return RobotAPIResult.RETRY

        mock_api.navigate.side_effect = failing_then_success

        adapter.attempt_cmd_until_success(
            cmd=mock_api.navigate,
            args=('AGV-001', 1, [], [], 'map1'),
        )

        # 스레드가 자연스럽게 완료될 때까지 대기 (cancel하지 않음)
        if adapter._issue_cmd_thread is not None:
            adapter._issue_cmd_thread.join(timeout=5.0)

        assert call_count >= 2

    def test_cancel_stops_retry(self, adapter, mock_api):
        """cancel_cmd_attempt()가 재시도를 중지한다."""
        mock_api.navigate.return_value = False

        adapter.attempt_cmd_until_success(
            cmd=mock_api.navigate,
            args=('AGV-001', 1, [], [], 'map1'),
        )

        # 즉시 취소
        adapter.cancel_cmd_attempt()

        assert adapter._issue_cmd_thread is None


@pytest.fixture
def adapter_with_handle(
    mock_api, mock_node,
    sample_nav_nodes, sample_nav_edges,
):
    """Create RobotAdapter with update_handle."""
    from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
        create_graph,
    )
    graph = create_graph(sample_nav_nodes, sample_nav_edges)
    robot = RobotAdapter(
        name='AGV-001',
        api=mock_api,
        node=mock_node,
        fleet_handle=MagicMock(),
        nav_nodes=sample_nav_nodes,
        nav_edges=sample_nav_edges,
        nav_graph=graph,
    )
    robot.configuration = MagicMock()
    mock_update_handle = MagicMock()
    mock_update_handle.more.return_value.current_task_id \
        .return_value = 'compose.dispatch-001'
    robot.update_handle = mock_update_handle
    return robot


class TestFinalNameIntegration:
    """destination.final_name을 사용한 navigate 테스트."""

    def test_uses_final_name_destination(
        self, adapter_with_handle, mock_api,
    ):
        """destination.final_name이 있을 때 최종 목적지를 사용한다."""
        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        dest.name = 'wp2'
        dest.final_name = 'wp4'
        execution = MagicMock()

        adapter_with_handle.position = [0.0, 0.0, 0.0]
        adapter_with_handle.navigate(dest, execution)
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.final_destination == 'wp4'

    def test_falls_back_without_final_name(
        self, adapter_with_handle, mock_api,
    ):
        """destination.final_name이 없으면 goal_node를 사용한다."""
        dest = MagicMock(spec=[])
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter_with_handle.position = [0.0, 0.0, 0.0]
        adapter_with_handle.navigate(dest, execution)
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.final_destination == 'wp2'

    def test_falls_back_when_final_name_empty(
        self, adapter_with_handle, mock_api,
    ):
        """destination.final_name이 빈 문자열이면 fallback한다."""
        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        dest.name = 'wp2'
        dest.final_name = ''
        execution = MagicMock()

        adapter_with_handle.position = [0.0, 0.0, 0.0]
        adapter_with_handle.navigate(dest, execution)
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.final_destination == 'wp2'


class TestOrderLifecycle:
    """Order 라이프사이클 관리 테스트."""

    def test_order_preserved_across_navigates(
        self, adapter_with_handle, mock_api
    ):
        """같은 task 내에서 order가 유지된다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest1 = MagicMock()
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        order_id = adapter_with_handle._order.active_order_id

        # Navigate 완료 시뮬레이션: 거리 기반 도착
        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 0.0, 0.0], battery_soc=0.85,
        )
        adapter_with_handle.update(state, data)

        # Order state 유지 (task 아직 active)
        assert adapter_with_handle._order.active_order_id == order_id

    def test_order_update_id_increments(
        self, adapter_with_handle, mock_api
    ):
        """같은 task 내 두 번째 navigate에서 update_id 증가."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest1 = MagicMock()
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        order_id = adapter_with_handle._order.active_order_id
        assert adapter_with_handle._order.order_update_id == 0

        dest2 = MagicMock()
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        exec2 = MagicMock()
        adapter_with_handle.navigate(dest2, exec2)
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.active_order_id == order_id
        assert adapter_with_handle._order.order_update_id == 1

    def test_stop_pauses_for_negotiation(
        self, adapter_with_handle,
    ):
        """Stop 시 pause 상태로 전환 (order 유지)."""
        execution = MagicMock()
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        adapter_with_handle.execution = execution
        adapter_with_handle._order.active_order_id = 'order_1_abc'
        adapter_with_handle._order.current_task_id = 'compose.dispatch-001'

        adapter_with_handle.stop(activity)
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._is_paused_for_negotiation is True
        assert adapter_with_handle._order.active_order_id == 'order_1_abc'


class TestDestinationName:
    """destination.name 사용 테스트."""

    def test_uses_destination_name_when_available(
        self, adapter_with_handle, mock_api
    ):
        """destination.name이 nav_nodes에 있으면 사용한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp3'
        dest.position = [4.9, 4.9, 0.0]  # near wp3 anyway
        dest.map = 'map1'
        execution = MagicMock()

        adapter_with_handle.navigate(dest, execution)
        adapter_with_handle.cancel_cmd_attempt()

        # goal_node should be wp3 (from name, not find_nearest_node)
        assert adapter_with_handle._order.final_destination is not None

    def test_falls_back_to_nearest_node(
        self, adapter_with_handle, mock_api
    ):
        """destination.name이 없으면 find_nearest_node를 사용한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock(spec=[])  # no 'name' attribute
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter_with_handle.navigate(dest, execution)
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.final_destination is not None

    def test_falls_back_when_name_not_in_nav_nodes(
        self, adapter_with_handle, mock_api
    ):
        """destination.name이 nav_nodes에 없으면 fallback한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'unknown_waypoint'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter_with_handle.navigate(dest, execution)
        adapter_with_handle.cancel_cmd_attempt()

        # Should use find_nearest_node fallback (wp2)
        assert adapter_with_handle._order.final_destination is not None


class TestFinalNameReResolve:
    """Order update 시 final_destination 재조회 테스트."""

    def test_uses_final_name_on_update(
        self, adapter_with_handle, mock_api
    ):
        """두 번째 navigate에서 final_name으로 재조회한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # First navigate: no final_name
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = ''
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        # fallback used
        assert adapter_with_handle._order.final_destination == 'wp2'

        # Second navigate: final_name available
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp4'
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        exec2 = MagicMock()
        adapter_with_handle.navigate(dest2, exec2)
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.final_destination == 'wp4'

    def test_keeps_destination_when_no_final_name(
        self, adapter_with_handle, mock_api
    ):
        """final_name이 없으면 기존 final_dest를 유지한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = ''
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        first_dest = adapter_with_handle._order.final_destination

        # Second navigate, still no final_name
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = ''
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        exec2 = MagicMock()
        adapter_with_handle.navigate(dest2, exec2)
        adapter_with_handle.cancel_cmd_attempt()

        # _final_destination keeps previous value (fallback)
        assert adapter_with_handle._order.final_destination == first_dest


class TestNegotiation:
    """Negotiation 처리 테스트."""

    @staticmethod
    def _wait_thread(adapter):
        """Retry 스레드가 완료될 때까지 대기한다."""
        if adapter._issue_cmd_thread is not None:
            adapter._issue_cmd_thread.join(timeout=5.0)

    def test_negotiation_sends_cancel_then_new_order(
        self, adapter_with_handle, mock_api
    ):
        """Negotiation 시 cancelOrder 후 새 orderID로 navigate한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # 1. 첫 번째 navigate (정상)
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp4'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        first_order_id = adapter_with_handle._order.active_order_id
        assert first_order_id is not None

        # 2. stop() → startPause (직접 호출)
        activity = MagicMock()
        exec1.identifier.is_same.return_value = True
        adapter_with_handle.stop(activity)

        assert adapter_with_handle._is_paused_for_negotiation is True
        mock_api.pause.assert_called_once()

        # 3. navigate() → composite: cancelOrder → 1s 대기 → 새 order
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp4'
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        exec2 = MagicMock()
        adapter_with_handle.navigate(dest2, exec2)
        # 스레드 완료 대기 (cancel + 1s + navigate)
        self._wait_thread(adapter_with_handle)

        # cancelOrder 호출됨
        mock_api.stop.assert_called_once()
        # navigate도 호출됨 (첫 번째 + negotiation 후)
        assert mock_api.navigate.call_count == 2
        # 새 orderID
        assert adapter_with_handle._order.active_order_id != first_order_id
        assert adapter_with_handle._order.order_update_id == 0
        assert adapter_with_handle._is_paused_for_negotiation is False

    def test_negotiation_creates_new_order_id(
        self, adapter_with_handle, mock_api
    ):
        """Negotiation 후 orderID가 새로 생성된다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest1 = MagicMock()
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        old_id = adapter_with_handle._order.active_order_id

        # stop → pause (직접 호출)
        activity = MagicMock()
        exec1.identifier.is_same.return_value = True
        adapter_with_handle.stop(activity)

        # navigate → cancel + new order
        dest2 = MagicMock()
        dest2.position = [0.0, 5.0, 0.0]
        dest2.map = 'map1'
        exec2 = MagicMock()
        adapter_with_handle.navigate(dest2, exec2)
        self._wait_thread(adapter_with_handle)

        new_id = adapter_with_handle._order.active_order_id
        assert new_id is not None
        assert new_id != old_id
        assert new_id.startswith('order_')

    def test_task_end_while_paused_sends_cancel(
        self, adapter_with_handle, mock_api
    ):
        """Pause 상태에서 task 종료 시 cancelOrder를 전송한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        # stop → pause (직접 호출)
        activity = MagicMock()
        exec1.identifier.is_same.return_value = True
        adapter_with_handle.stop(activity)

        assert adapter_with_handle._is_paused_for_negotiation is True

        # task 종료 시뮬레이션: update에서 task_id가 빈 문자열
        adapter_with_handle.update_handle.more.return_value \
            .current_task_id.return_value = ''
        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 0.0, 0.0], battery_soc=0.85,
        )
        adapter_with_handle.update(state, data)
        adapter_with_handle.cancel_cmd_attempt()

        # cancelOrder가 _reset_order_state에서 호출됨
        mock_api.stop.assert_called_once()
        assert adapter_with_handle._is_paused_for_negotiation is False
        assert adapter_with_handle._order.active_order_id is None

    def test_negotiation_flow_sequence(
        self, adapter_with_handle, mock_api
    ):
        """전체 negotiation 시퀀스: pause → cancel → new order."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # 1. 정상 navigate
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp4'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        # 2. negotiation 발생 → stop (startPause 직접 호출)
        activity = MagicMock()
        exec1.identifier.is_same.return_value = True
        adapter_with_handle.stop(activity)

        # pause 직접 호출 확인
        assert mock_api.pause.call_count == 1
        assert mock_api.stop.call_count == 0

        # 3. 새 경로로 navigate (composite: cancel → wait → navigate)
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp4'
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        exec2 = MagicMock()
        adapter_with_handle.navigate(dest2, exec2)
        self._wait_thread(adapter_with_handle)

        # cancel 호출 확인
        assert mock_api.stop.call_count == 1
        # 새 navigate 호출 확인 (총 2회: 첫 번째 + negotiation 후)
        assert mock_api.navigate.call_count == 2


class TestTaskCancelSendsCancelOrder:
    """Task cancel 시 cancelOrder 전송 테스트."""

    def test_no_cancel_after_normal_completion(
        self, adapter_with_handle, mock_api
    ):
        """정상 도착 후 task 종료 시 cancelOrder를 전송하지 않는다."""
        adapter = adapter_with_handle

        # navigate 상태를 직접 설정 (thread 의존성 제거)
        adapter.execution = MagicMock()
        adapter._order.active_order_id = 'order-cancel-test'
        adapter._order.current_task_id = 'compose.dispatch-001'
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]

        # task 진행 중이므로 current_task_id는 동일한 값 반환
        adapter.update_handle.more.return_value \
            .current_task_id.return_value = 'compose.dispatch-001'

        mock_api.stop.assert_not_called()

        # navigate 도착 → execution 완료 (completed_normally=True)
        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 0.0, 0.0], battery_soc=0.85,
        )
        adapter.update(state, data)

        # execution 완료, order는 아직 유지 (task 진행 중)
        assert adapter.execution is None
        assert adapter._order.active_order_id == 'order-cancel-test'
        assert adapter._order.completed_normally is True

        # task 종료: task_id가 빈 문자열로 변경
        adapter.update_handle.more.return_value \
            .current_task_id.return_value = ''
        adapter.update(state, data)
        adapter.cancel_cmd_attempt()

        # 정상 도착이므로 cancelOrder 미전송
        mock_api.stop.assert_not_called()
        assert adapter._order.active_order_id is None

    def test_cancel_when_task_aborted_before_arrival(
        self, adapter_with_handle, mock_api
    ):
        """도착 전 task 취소 시 cancelOrder를 전송한다."""
        adapter = adapter_with_handle

        # navigate 상태 설정 (아직 도착 안 함)
        adapter.execution = MagicMock()
        adapter._order.active_order_id = 'order-cancel-test'
        adapter._order.current_task_id = 'compose.dispatch-001'
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [5.0, 0.0]

        # execution을 외부에서 제거 (task abort 시뮬레이션)
        adapter.execution = None

        # task cancel: task_id가 빈 문자열로 변경
        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[1.0, 0.0, 0.0], battery_soc=0.85,
        )
        adapter.update_handle.more.return_value \
            .current_task_id.return_value = ''
        adapter.update(state, data)
        adapter.cancel_cmd_attempt()

        # 비정상 종료이므로 cancelOrder 전송
        mock_api.stop.assert_called_once()
        assert adapter._order.active_order_id is None

    def test_cancel_task_request_with_execution_alive(
        self, adapter_with_handle, mock_api
    ):
        """execution이 살아있는 상태에서 task 취소 시 cancelOrder를 전송한다.

        cancel_task_request 시 RMF가 stop() 콜백을 호출하지 않아
        execution이 남아있는 경우를 커버한다.
        """
        adapter = adapter_with_handle

        # navigate 상태 설정 (이동 중)
        adapter.execution = MagicMock()
        adapter._order.active_order_id = 'order-cancel-req'
        adapter._order.current_task_id = 'compose.dispatch-002'
        adapter._nav.is_navigating = True
        adapter._nav.target_position = [10.0, 10.0]

        # task cancel: task_id가 빈 문자열로 변경 (execution은 유지)
        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[1.0, 0.0, 0.0], battery_soc=0.85,
        )
        adapter.update_handle.more.return_value \
            .current_task_id.return_value = ''
        adapter.update(state, data)
        adapter.cancel_cmd_attempt()

        # execution이 살아있었지만 cancelOrder 전송
        mock_api.stop.assert_called_once()
        assert adapter.execution is None
        assert adapter._order.active_order_id is None

    def test_no_cancel_order_when_no_active_order(
        self, adapter_with_handle, mock_api
    ):
        """Active order가 없으면 cancelOrder를 전송하지 않는다."""
        assert adapter_with_handle._order.active_order_id is None

        adapter_with_handle._reset_order_state()

        mock_api.stop.assert_not_called()


class TestDetourPath:
    """경유지(goal_node)를 경유하는 경로 생성 테스트.

    RMF가 교통 관리를 위해 경유지를 지정한 경우,
    최단 경로가 아닌 경유지를 반드시 거치는 경로를 생성해야 한다.
    """

    @pytest.fixture
    def detour_adapter(self, mock_api, mock_node):
        """T자 그래프로 경유지 테스트용 어댑터 생성.

        Graph:
            A(0,0) --- B(5,0) --- C(10,0)
                         |
                       D(5,5)
        shortest A→C: A→B→C (D를 거치지 않음)
        """
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        nodes = {
            'A': {'x': 0.0, 'y': 0.0, 'attributes': {}},
            'B': {'x': 5.0, 'y': 0.0, 'attributes': {}},
            'C': {'x': 10.0, 'y': 0.0, 'attributes': {}},
            'D': {'x': 5.0, 'y': 5.0, 'attributes': {}},
        }
        edges = {
            'e0': {'start': 'A', 'end': 'B', 'attributes': {}},
            'e1': {'start': 'B', 'end': 'A', 'attributes': {}},
            'e2': {'start': 'B', 'end': 'C', 'attributes': {}},
            'e3': {'start': 'C', 'end': 'B', 'attributes': {}},
            'e4': {'start': 'B', 'end': 'D', 'attributes': {}},
            'e5': {'start': 'D', 'end': 'B', 'attributes': {}},
        }
        graph = create_graph(nodes, edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=nodes, nav_edges=edges, nav_graph=graph,
        )
        robot.configuration = MagicMock()
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'task-001'
        robot.update_handle = mock_handle
        return robot

    def test_path_goes_through_goal_node(
        self, detour_adapter, mock_api
    ):
        """경유지 D를 반드시 거치는 경로 생성 (A→B→D→B→C)."""
        detour_adapter.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'D'
        dest.final_name = 'C'
        dest.waypoint_names = ['A', 'B', 'D', 'B', 'C']
        dest.position = [5.0, 5.0, 0.0]
        dest.map = 'L1'
        execution = MagicMock()

        detour_adapter.navigate(dest, execution)
        detour_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        # D를 반드시 거쳐야 함
        assert 'D' in node_ids
        # D가 C보다 먼저 나와야 함
        assert node_ids.index('D') < node_ids.index('C')
        # 경로: A → B → D → B → C
        assert node_ids == ['A', 'B', 'D', 'B', 'C']

    def test_base_horizon_split_with_detour(
        self, detour_adapter, mock_api
    ):
        """경유지까지 Base, 이후 Horizon으로 분리."""
        detour_adapter.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'D'
        dest.final_name = 'C'
        dest.waypoint_names = ['A', 'B', 'D', 'B', 'C']
        dest.position = [5.0, 5.0, 0.0]
        dest.map = 'L1'
        execution = MagicMock()

        detour_adapter.navigate(dest, execution)
        detour_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]

        # D(index=2)까지 Base, 이후 Horizon
        for i, node in enumerate(nodes):
            node_id = node.node_id
            if node_id == 'D':
                d_index = i
                break
        for i, node in enumerate(nodes):
            if i <= d_index:
                assert node.released is True, (
                    f'{node.node_id} should be base (released)'
                )
            else:
                assert node.released is False, (
                    f'{node.node_id} should be horizon (not released)'
                )

    def test_direct_path_when_goal_is_final(
        self, detour_adapter, mock_api
    ):
        """경유지 == 최종목적지면 최단 경로 사용."""
        detour_adapter.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'C'
        dest.final_name = 'C'
        dest.position = [10.0, 0.0, 0.0]
        dest.map = 'L1'
        execution = MagicMock()

        detour_adapter.navigate(dest, execution)
        detour_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        # 최단 경로: A → B → C (D를 거치지 않음)
        assert node_ids == ['A', 'B', 'C']
        assert 'D' not in node_ids


class TestStartNodeFix:
    """Start_node 결정 로직 테스트."""

    def test_uses_current_position(
        self, adapter_with_handle, mock_api
    ):
        """Navigate에서 현재 위치를 start_node로 사용한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()
        adapter_with_handle.navigate(dest, execution)
        adapter_with_handle.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        # First node should be wp1 (nearest to 0,0)
        if nodes:
            assert nodes[0].node_id == 'wp1'


class TestTJunctionDetourWithPlannedPath:
    """T자 교차로 회피 시나리오: planned_path에 전체 회피경로 포함.

    Graph:
        A(0,0) --- B(5,0) --- C(10,0)
                     |
                   D(5,5)

    시나리오: Robot1(A→C) 이동 중 Robot2와 충돌 회피를 위해
    D로 우회. RMF planner가 전체 경로 [A,B,D,B,C]를 planned_path로
    publish하고, navigate(dest=B, final=C)를 호출한다.
    """

    @pytest.fixture
    def t_adapter(self, mock_api, mock_node):
        """T자 그래프 어댑터 (detour_adapter와 동일 토폴로지)."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        nodes = {
            'A': {'x': 0.0, 'y': 0.0, 'attributes': {}},
            'B': {'x': 5.0, 'y': 0.0, 'attributes': {}},
            'C': {'x': 10.0, 'y': 0.0, 'attributes': {}},
            'D': {'x': 5.0, 'y': 5.0, 'attributes': {}},
        }
        edges = {
            'e0': {'start': 'A', 'end': 'B', 'attributes': {}},
            'e1': {'start': 'B', 'end': 'A', 'attributes': {}},
            'e2': {'start': 'B', 'end': 'C', 'attributes': {}},
            'e3': {'start': 'C', 'end': 'B', 'attributes': {}},
            'e4': {'start': 'B', 'end': 'D', 'attributes': {}},
            'e5': {'start': 'D', 'end': 'B', 'attributes': {}},
        }
        graph = create_graph(nodes, edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=nodes, nav_edges=edges, nav_graph=graph,
        )
        robot.configuration = MagicMock()
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'task-001'
        robot.update_handle = mock_handle
        return robot

    def test_planned_path_full_detour_route(
        self, t_adapter, mock_api
    ):
        """planned_path=[A,B,D,B,C] → 전체 회피경로 그대로 사용."""
        t_adapter.position = [0.0, 0.0, 0.0]  # at A

        dest = MagicMock()
        dest.name = 'B'
        dest.final_name = 'C'
        dest.waypoint_names = ['A', 'B', 'D', 'B', 'C']
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'L1'
        execution = MagicMock()

        t_adapter.navigate(dest, execution)
        t_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        # 전체 경로: A → B → D → B → C
        assert node_ids == ['A', 'B', 'D', 'B', 'C']

    def test_planned_path_detour_3tier_split(
        self, t_adapter, mock_api
    ):
        """3-tier 분리: Base=[A,B], Horizon-RMF=[D,B,C], ext=[]."""
        t_adapter.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'B'
        dest.final_name = 'C'
        dest.waypoint_names = ['A', 'B', 'D', 'B', 'C']
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'L1'
        execution = MagicMock()

        t_adapter.navigate(dest, execution)
        t_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]

        # tier1 (Base): A, B → released=True
        assert nodes[0].node_id == 'A'
        assert nodes[0].released is True
        assert nodes[1].node_id == 'B'
        assert nodes[1].released is True

        # tier2 (Horizon-RMF): D, B, C → released=False
        assert nodes[2].node_id == 'D'
        assert nodes[2].released is False
        assert nodes[3].node_id == 'B'
        assert nodes[3].released is False
        assert nodes[4].node_id == 'C'
        assert nodes[4].released is False

    def test_planned_path_detour_no_tier3_extension(
        self, t_adapter, mock_api
    ):
        """C가 planned_path에 포함되어 있으므로 tier3 확장 불필요."""
        t_adapter.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'B'
        dest.final_name = 'C'
        dest.waypoint_names = ['A', 'B', 'D', 'B', 'C']
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'L1'
        execution = MagicMock()

        t_adapter.navigate(dest, execution)
        t_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        # 정확히 5개 노드 (확장 없음)
        assert len(node_ids) == 5
        # 마지막 노드가 C
        assert node_ids[-1] == 'C'

    def test_planned_path_detour_second_navigate(
        self, t_adapter, mock_api
    ):
        """D 도착 후 두 번째 navigate(dest=B, final=C).

        Robot이 D에 도착, RMF가 다시 waypoint_names=[D,B,C].
        navigate(dest=B, final=C) → D(base)→B(base)→C(horizon).
        """
        # 첫 navigate (task 시작)
        t_adapter.position = [0.0, 0.0, 0.0]
        dest1 = MagicMock()
        dest1.name = 'B'
        dest1.final_name = 'C'
        dest1.waypoint_names = ['A', 'B', 'D', 'B', 'C']
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'L1'
        execution1 = MagicMock()
        t_adapter.navigate(dest1, execution1)
        t_adapter.cancel_cmd_attempt()

        # D에 도착
        t_adapter.position = [5.0, 5.0, 0.0]  # at D

        dest2 = MagicMock()
        dest2.name = 'B'
        dest2.final_name = 'C'
        dest2.waypoint_names = ['D', 'B', 'C']
        dest2.position = [5.0, 0.0, 0.0]
        dest2.map = 'L1'
        execution2 = MagicMock()
        t_adapter.navigate(dest2, execution2)
        t_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        # D → B → C
        assert node_ids == ['D', 'B', 'C']
        # D, B = Base (dest=B까지)
        assert nodes[0].released is True   # D
        assert nodes[1].released is True   # B
        # C = Horizon
        assert nodes[2].released is False  # C

    def test_planned_path_detour_final_navigate(
        self, t_adapter, mock_api
    ):
        """B 도착 후 마지막 navigate(dest=C, final=C).

        Robot이 B에 도착, RMF가 waypoint_names=[B,C].
        navigate(dest=C, final=C) → B(base)→C(base), 모두 released.
        """
        # 첫 navigate (task 시작)
        t_adapter.position = [0.0, 0.0, 0.0]
        dest1 = MagicMock()
        dest1.name = 'B'
        dest1.final_name = 'C'
        dest1.waypoint_names = ['A', 'B', 'D', 'B', 'C']
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'L1'
        t_adapter.navigate(dest1, MagicMock())
        t_adapter.cancel_cmd_attempt()

        # B에 도착, 마지막 segment
        t_adapter.position = [5.0, 0.0, 0.0]  # at B

        dest3 = MagicMock()
        dest3.name = 'C'
        dest3.final_name = 'C'
        dest3.waypoint_names = ['B', 'C']
        dest3.position = [10.0, 0.0, 0.0]
        dest3.map = 'L1'
        t_adapter.navigate(dest3, MagicMock())
        t_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        # B → C, 모두 Base (dest == final)
        assert node_ids == ['B', 'C']
        assert nodes[0].released is True   # B
        assert nodes[1].released is True   # C


class TestSparsePathInterpolation:
    """Sparse planned_path (중간 노드 생략) 보간 테스트.

    Graph (직렬):
        n1 -- n2 -- n3 -- n4 -- n5 -- n6 -- n7

    RMF planned_path가 [n1, n3, n5, n7]처럼 중간 노드를 생략하면
    compute_path로 보간하여 [n1, n2, n3, n4, n5, n6, n7]을 만든다.
    """

    @pytest.fixture
    def linear_adapter(self, mock_api, mock_node):
        """직렬 7노드 그래프 어댑터."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        nodes = {
            f'n{i}': {'x': float(i), 'y': 0.0, 'attributes': {}}
            for i in range(1, 8)
        }
        edges = {}
        for i in range(1, 7):
            edges[f'e{i}f'] = {
                'start': f'n{i}', 'end': f'n{i+1}',
                'attributes': {},
            }
            edges[f'e{i}r'] = {
                'start': f'n{i+1}', 'end': f'n{i}',
                'attributes': {},
            }
        graph = create_graph(nodes, edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=nodes, nav_edges=edges, nav_graph=graph,
        )
        robot.configuration = MagicMock()
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'task-001'
        robot.update_handle = mock_handle
        return robot

    def test_sparse_path_interpolated(
        self, linear_adapter, mock_api
    ):
        """[n1,n3,n5,n7] → [n1,n2,n3,n4,n5,n6,n7]로 보간."""
        linear_adapter.position = [1.0, 0.0, 0.0]  # at n1

        dest = MagicMock()
        dest.name = 'n3'
        dest.final_name = 'n7'
        dest.waypoint_names = ['n1', 'n3', 'n5', 'n7']
        dest.position = [3.0, 0.0, 0.0]
        dest.map = 'L1'

        linear_adapter.navigate(dest, MagicMock())
        linear_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        assert node_ids == ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7']

    def test_sparse_path_3tier_split(
        self, linear_adapter, mock_api
    ):
        """보간 후 3-tier 분리: dest=n3, final=n7."""
        linear_adapter.position = [1.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'n3'
        dest.final_name = 'n7'
        dest.waypoint_names = ['n1', 'n3', 'n5', 'n7']
        dest.position = [3.0, 0.0, 0.0]
        dest.map = 'L1'

        linear_adapter.navigate(dest, MagicMock())
        linear_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]

        # tier1 (Base): n1, n2, n3 → released=True
        for i in range(3):
            assert nodes[i].released is True, (
                f'{nodes[i].node_id} should be base'
            )
        # tier2 (Horizon-RMF): n4, n5, n6, n7 → released=False
        for i in range(3, 7):
            assert nodes[i].released is False, (
                f'{nodes[i].node_id} should be horizon'
            )

    def test_adjacent_path_unchanged(
        self, linear_adapter, mock_api
    ):
        """이미 연속된 경로 [n1,n2,n3]은 변경 없음."""
        linear_adapter.position = [1.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'n2'
        dest.final_name = 'n3'
        dest.waypoint_names = ['n1', 'n2', 'n3']
        dest.position = [2.0, 0.0, 0.0]
        dest.map = 'L1'

        linear_adapter.navigate(dest, MagicMock())
        linear_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        assert node_ids == ['n1', 'n2', 'n3']

    def test_sparse_path_includes_pre_destination_nodes(
        self, linear_adapter, mock_api
    ):
        """waypoint_names에 destination 이전 노드 포함 시 중복 없음.

        waypoint_names=[n1,n3,n5], dest=n2, final=n7
        → interpolated=[n1,n2,n3,n4,n5]
        → start=n1부터 slice → [n1,n2,n3,n4,n5]
        → tier3 extension → [n1,n2,n3,n4,n5,n6,n7]
        → 중복 노드 없어야 함.
        """
        linear_adapter.position = [1.0, 0.0, 0.0]  # at n1

        dest = MagicMock()
        dest.name = 'n2'
        dest.final_name = 'n7'
        dest.waypoint_names = ['n1', 'n3', 'n5']
        dest.position = [2.0, 0.0, 0.0]
        dest.map = 'L1'

        linear_adapter.navigate(dest, MagicMock())
        linear_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        # 전체 경로: 중복 없이 n1→n2→n3→n4→n5→n6→n7
        assert node_ids == [
            'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7',
        ]
        # 중복 노드 없음
        for i, nid in enumerate(node_ids):
            assert nid not in node_ids[i+1:i+2], (
                f'Duplicate adjacent node: {nid}'
            )

        # Base: n1, n2 (dest까지), Horizon: n3~n7
        assert nodes[0].released is True   # n1
        assert nodes[1].released is True   # n2 (dest)
        assert nodes[2].released is False  # n3
        assert nodes[6].released is False  # n7


class TestStitchingSequenceId:
    """Order update 시 sequenceId stitching 테스트."""

    def test_first_order_seq_starts_at_zero(
        self, adapter_with_handle, mock_api
    ):
        """첫 번째 order의 sequenceId가 0부터 시작한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        assert nodes[0].sequence_id == 0

    def test_order_update_seq_continues_from_stitch(
        self, adapter_with_handle, mock_api
    ):
        """Order update 시 stitching node의 sequenceId가 유지된다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # 첫 navigate: wp1→wp2→wp3, dest=wp2 (base_end_index=1)
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp3'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        adapter_with_handle.navigate(dest1, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        first_nodes = mock_api.navigate.call_args[0][2]
        first_node_ids = [n.node_id for n in first_nodes]

        # wp2의 sequenceId 확인 (stitching point)
        wp2_idx = first_node_ids.index('wp2')
        stitch_seq = first_nodes[wp2_idx].sequence_id

        # 두 번째 navigate (order update): wp2→wp3
        adapter_with_handle.position = [5.0, 0.0, 0.0]
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp3'
        dest2.waypoint_names = ['wp2', 'wp3']
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        adapter_with_handle.navigate(dest2, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        second_nodes = mock_api.navigate.call_args[0][2]
        # stitching node (첫 노드)의 sequenceId == 이전 Base 마지막 노드
        assert second_nodes[0].sequence_id == stitch_seq

    def test_new_order_resets_seq_to_zero(
        self, adapter_with_handle, mock_api
    ):
        """Negotiation 후 새 order는 sequenceId 0부터 시작한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # 첫 navigate
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp3'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        exec1 = MagicMock()
        adapter_with_handle.navigate(dest1, exec1)
        adapter_with_handle.cancel_cmd_attempt()

        # stop → negotiation pause
        activity = MagicMock()
        exec1.identifier.is_same.return_value = True
        adapter_with_handle.stop(activity)

        # navigate → cancel + new order (새 orderID)
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp3'
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        adapter_with_handle.navigate(dest2, MagicMock())
        # 스레드 완료 대기
        if adapter_with_handle._issue_cmd_thread is not None:
            adapter_with_handle._issue_cmd_thread.join(timeout=5.0)

        # 새 order의 sequenceId는 0부터
        nodes = mock_api.navigate.call_args[0][2]
        assert nodes[0].sequence_id == 0

    def test_reset_order_clears_stitch_seq(
        self, adapter_with_handle, mock_api
    ):
        """_reset_order_state가 _last_stitch_seq_id를 초기화한다."""
        adapter_with_handle._order.last_stitch_seq_id = 42

        adapter_with_handle._reset_order_state()

        assert adapter_with_handle._order.last_stitch_seq_id == 0


class TestExecuteActionAsOrderUpdate:
    """execute_action()이 active order 시 nodeAction order update를 전송."""

    def test_action_with_active_order_sends_navigate(
        self, adapter_with_handle, mock_api
    ):
        """Active order 있으면 api.navigate()로 order update 전송."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # 먼저 navigate로 active order 생성
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        order_id = adapter_with_handle._order.active_order_id
        assert order_id is not None
        mock_api.navigate.reset_mock()

        # execute_action → order update (navigate 호출)
        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        # api.navigate가 호출됨 (start_activity가 아님)
        mock_api.navigate.assert_called_once()
        mock_api.start_activity.assert_not_called()

    def test_action_without_active_order_sends_new_order(
        self, adapter_with_handle, mock_api
    ):
        """Active order 없으면 단일 노드 order로 action을 전송."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]
        assert adapter_with_handle._order.active_order_id is None

        adapter_with_handle.execute_action(
            'pick', {}, MagicMock()
        )
        adapter_with_handle.cancel_cmd_attempt()

        mock_api.start_activity.assert_not_called()
        mock_api.navigate.assert_called_once()

        call_args = mock_api.navigate.call_args
        nodes = call_args[0][2]
        edges = call_args[0][3]
        order_id = call_args[0][5]
        update_id = call_args[0][6]

        assert len(nodes) == 1
        assert len(edges) == 0
        assert order_id.startswith('order_')
        assert update_id == 0
        assert len(nodes[0].actions) == 1
        assert nodes[0].actions[0].action_type == 'pick'

    def test_action_order_update_uses_same_order_id(
        self, adapter_with_handle, mock_api
    ):
        """Order update가 같은 orderID를 사용한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        order_id = adapter_with_handle._order.active_order_id
        mock_api.navigate.reset_mock()

        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args
        # positional args: (name, cmd_id, nodes, edges, map, order_id, update_id)
        assert call_args[0][5] == order_id

    def test_action_order_update_increments_update_id(
        self, adapter_with_handle, mock_api
    ):
        """Order update의 update_id가 증가한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.order_update_id == 0
        mock_api.navigate.reset_mock()

        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.order_update_id == 1
        call_args = mock_api.navigate.call_args
        assert call_args[0][6] == 1  # order_update_id

    def test_action_node_has_action_attached(
        self, adapter_with_handle, mock_api
    ):
        """Order update의 노드에 action이 첨부된다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()
        mock_api.navigate.reset_mock()

        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action(
            'pick', {'station': 'A'}, MagicMock()
        )
        adapter_with_handle.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        # 첫 노드(base)에 action 첨부
        assert len(nodes[0].actions) == 1
        action = nodes[0].actions[0]
        assert action.action_type == 'pick'
        assert action.blocking_type.value == 'HARD'
        assert len(action.action_parameters) == 1
        assert action.action_parameters[0].key == 'station'

    def test_action_tracks_action_id(
        self, adapter_with_handle, mock_api
    ):
        """Order update가 track_action_id를 전달한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()
        mock_api.navigate.reset_mock()

        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        call_kwargs = mock_api.navigate.call_args[1]
        assert 'track_action_id' in call_kwargs
        assert call_kwargs['track_action_id'].startswith('pick_')

    def test_action_base_node_is_current_position(
        self, adapter_with_handle, mock_api
    ):
        """Action order update의 base 노드가 현재 위치이다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()
        mock_api.navigate.reset_mock()

        # 현재 위치를 wp2(5,0)으로 설정
        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        # Base 노드 = wp2
        assert nodes[0].node_id == 'wp2'
        assert nodes[0].released is True

    def test_action_includes_horizon_to_final_dest(
        self, adapter_with_handle, mock_api
    ):
        """Action order update가 최종 목적지까지 horizon을 포함한다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()
        mock_api.navigate.reset_mock()

        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]
        # wp2(base) → wp3(horizon) (final_destination=wp3)
        assert node_ids == ['wp2', 'wp3']
        assert nodes[0].released is True   # base
        assert nodes[1].released is False  # horizon

    def test_action_no_horizon_when_at_final_dest(
        self, adapter_with_handle, mock_api
    ):
        """최종 목적지에서 action 시 horizon 없음."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        adapter_with_handle.navigate(dest, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()
        mock_api.navigate.reset_mock()

        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]
        assert node_ids == ['wp2']
        assert nodes[0].released is True


class TestCartDeliveryFlow:
    """Cart delivery 전체 플로우 테스트.

    Scenario: wp1 → wp2(pickup) → wp3(dropoff)
    Phase 1: navigate to wp2
    Phase 2: execute 'pick' action at wp2
    Phase 3: navigate to wp3
    Phase 4: execute 'drop' action at wp3
    """

    def test_full_cart_delivery_flow(
        self, adapter_with_handle, mock_api
    ):
        """Cart delivery: navigate→pick→navigate→drop."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # Phase 1: navigate to wp2 (pickup)
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp2'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        adapter_with_handle.navigate(dest1, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        order_id = adapter_with_handle._order.active_order_id
        assert order_id is not None
        assert adapter_with_handle._order.order_update_id == 0

        # Phase 2: pick action at wp2
        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action(
            'pick', {'station': 'A'}, MagicMock()
        )
        adapter_with_handle.cancel_cmd_attempt()

        # 같은 orderID, update_id 증가
        assert adapter_with_handle._order.active_order_id == order_id
        assert adapter_with_handle._order.order_update_id == 1

        # Phase 3: navigate to wp3 (dropoff)
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp3'
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        adapter_with_handle.navigate(dest2, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        # 같은 orderID, update_id 증가
        assert adapter_with_handle._order.active_order_id == order_id
        assert adapter_with_handle._order.order_update_id == 2

        # Phase 4: drop action at wp3
        adapter_with_handle.position = [5.0, 5.0, 0.0]
        adapter_with_handle.execute_action(
            'drop', {'station': 'B'}, MagicMock()
        )
        adapter_with_handle.cancel_cmd_attempt()

        assert adapter_with_handle._order.active_order_id == order_id
        assert adapter_with_handle._order.order_update_id == 3

        # 전체 api.navigate 호출: 4회
        # (nav1 + action1 + nav2 + action2)
        assert mock_api.navigate.call_count == 4
        # instantAction은 사용되지 않음
        mock_api.start_activity.assert_not_called()

    def test_cart_delivery_action_nodes_have_actions(
        self, adapter_with_handle, mock_api
    ):
        """Cart delivery에서 action order update의 노드에 action 첨부."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # Phase 1: navigate
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp2'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        adapter_with_handle.navigate(dest1, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        # Phase 2: pick
        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        # pick order update 확인
        pick_call = mock_api.navigate.call_args_list[1]
        pick_nodes = pick_call[0][2]
        assert len(pick_nodes[0].actions) == 1
        assert pick_nodes[0].actions[0].action_type == 'pick'

        # track_action_id 확인
        assert 'track_action_id' in pick_call[1]
        assert pick_call[1]['track_action_id'].startswith('pick_')

    def test_cart_delivery_stitch_seq_continuity(
        self, adapter_with_handle, mock_api
    ):
        """Cart delivery에서 sequenceId가 올바르게 이어진다."""
        adapter_with_handle.position = [0.0, 0.0, 0.0]

        # Phase 1: navigate to wp2
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp2'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        adapter_with_handle.navigate(dest1, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        nav1_nodes = mock_api.navigate.call_args[0][2]
        # wp1(seq=0), wp2(seq=2) → stitch_seq = 2
        wp2_seq = None
        for n in nav1_nodes:
            if n.node_id == 'wp2':
                wp2_seq = n.sequence_id
        assert wp2_seq is not None

        # Phase 2: pick action at wp2
        adapter_with_handle.position = [5.0, 0.0, 0.0]
        adapter_with_handle.execute_action('pick', {}, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        pick_nodes = mock_api.navigate.call_args[0][2]
        # action order update의 첫 노드 seq == stitch_seq
        assert pick_nodes[0].sequence_id == wp2_seq

        # Phase 3: navigate to wp3
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp3'
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        adapter_with_handle.navigate(dest2, MagicMock())
        adapter_with_handle.cancel_cmd_attempt()

        nav2_nodes = mock_api.navigate.call_args[0][2]
        # stitch node의 seq == wp2_seq (action 이후에도 유지)
        assert nav2_nodes[0].sequence_id == wp2_seq

    def test_reset_order_clears_last_map(
        self, adapter_with_handle
    ):
        """_reset_order_state가 _last_map을 초기화한다."""
        adapter_with_handle._order.last_map = 'map1'

        adapter_with_handle._reset_order_state()

        assert adapter_with_handle._order.last_map is None


class TestCharging:
    """충전 (startCharging/stopCharging) 테스트.

    Graph (charger 포함):
        wp1(0,0) --- wp2(5,0) --- wp3(5,5)
                                    |
                                charger_1(5,10)

    설계:
    - startCharging: charger 앞 노드에 nodeAction으로 부착
    - startCharging FINISHED = 도킹+충전 시작 완료 → execution.finished()
    - stopCharging: 다음 order의 첫 번째 노드에 nodeAction으로 부착
    - adapter는 SOC를 모니터링하지 않음
    """

    @pytest.fixture
    def charging_adapter(self, mock_api, mock_node):
        """Charger 노드가 포함된 어댑터."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        nodes = {
            'wp1': {'x': 0.0, 'y': 0.0, 'attributes': {}},
            'wp2': {'x': 5.0, 'y': 0.0, 'attributes': {}},
            'wp3': {'x': 5.0, 'y': 5.0, 'attributes': {}},
            'charger_1': {
                'x': 5.0, 'y': 10.0,
                'attributes': {'is_charger': True},
            },
        }
        edges = {
            'e0': {'start': 'wp1', 'end': 'wp2', 'attributes': {}},
            'e1': {'start': 'wp2', 'end': 'wp1', 'attributes': {}},
            'e2': {'start': 'wp2', 'end': 'wp3', 'attributes': {}},
            'e3': {'start': 'wp3', 'end': 'wp2', 'attributes': {}},
            'e4': {
                'start': 'wp3', 'end': 'charger_1',
                'attributes': {},
            },
            'e5': {
                'start': 'charger_1', 'end': 'wp3',
                'attributes': {},
            },
        }
        graph = create_graph(nodes, edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=nodes, nav_edges=edges, nav_graph=graph,
        )
        robot.configuration = MagicMock()
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'charge-task-001'
        robot.update_handle = mock_handle
        robot.position = [0.0, 0.0, 0.0]
        return robot

    def test_navigate_to_charger_sets_charging_pending(
        self, charging_adapter, mock_api
    ):
        """is_charger 속성 노드로 navigate 시 _is_charging_pending이 True."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        assert charging_adapter._charging.is_pending is True
        assert charging_adapter._charging.station_name == 'charger_1'

    def test_navigate_to_non_charger_no_charging(
        self, charging_adapter, mock_api
    ):
        """is_charger 속성이 없는 노드로 navigate 시 충전 비활성."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp3'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        assert charging_adapter._charging.is_pending is False
        assert charging_adapter._charging.station_name is None

    def test_charging_order_excludes_charger_node(
        self, charging_adapter, mock_api
    ):
        """충전 order에서 charger 노드가 제외된다."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        node_ids = [n.node_id for n in nodes]

        assert 'charger_1' not in node_ids

    def test_charging_order_has_start_charging_action(
        self, charging_adapter, mock_api
    ):
        """충전 order의 마지막 base 노드에 startCharging 부착."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]

        # 마지막 노드에 startCharging action이 있어야 함
        last_node = nodes[-1]
        assert len(last_node.actions) >= 1
        charge_action = last_node.actions[-1]
        assert charge_action.action_type == 'startCharging'

    def test_start_charging_action_has_station_name(
        self, charging_adapter, mock_api
    ):
        """Verify startCharging action has stationName parameter."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]
        last_node = nodes[-1]
        charge_action = last_node.actions[-1]

        assert len(charge_action.action_parameters) == 1
        param = charge_action.action_parameters[0]
        assert param.key == 'stationName'
        assert param.value == 'charger_1'

    def test_arrival_at_pre_charger_transitions_to_charging(
        self, charging_adapter, mock_api
    ):
        """Pre-charger 노드 도착 시 _is_charging 전환, finished 미호출."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        charging_adapter.navigate(dest, execution)
        charging_adapter.cancel_cmd_attempt()

        # pre-charger 노드(wp3)에 도착 시뮬레이션
        state = MagicMock()
        target = charging_adapter._nav.target_position
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.50,
        )

        charging_adapter.update(state, data)

        execution.finished.assert_not_called()
        assert charging_adapter._charging.is_active is True
        assert charging_adapter._charging.is_pending is False
        assert charging_adapter._nav.is_navigating is False
        assert charging_adapter.execution is execution

    def test_charging_completes_when_action_finished(
        self, charging_adapter, mock_api
    ):
        """Charging completes when startCharging action reports FINISHED."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        charging_adapter.navigate(dest, execution)
        charging_adapter.cancel_cmd_attempt()

        # Phase 1: pre-charger 도착
        state = MagicMock()
        target = charging_adapter._nav.target_position
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.50,
        )
        charging_adapter.update(state, data)
        assert charging_adapter._charging.is_active is True

        # Phase 2: AGV가 startCharging action FINISHED 보고
        mock_api.is_command_completed.return_value = True
        charging_adapter.update(state, data)

        execution.finished.assert_called_once()
        assert charging_adapter.execution is None
        assert charging_adapter._charging.is_active is False
        assert charging_adapter._charging.was_charging is True

    def test_charging_not_complete_while_action_running(
        self, charging_adapter, mock_api
    ):
        """Charging waits while startCharging action is still running."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        charging_adapter.navigate(dest, execution)
        charging_adapter.cancel_cmd_attempt()

        # pre-charger 도착
        state = MagicMock()
        target = charging_adapter._nav.target_position
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.50,
        )
        charging_adapter.update(state, data)

        # is_command_completed == False (아직 도킹/충전 시작 안됨)
        mock_api.is_command_completed.return_value = False
        charging_adapter.update(state, data)

        execution.finished.assert_not_called()
        assert charging_adapter._charging.is_active is True
        assert charging_adapter._charging.was_charging is False

    def test_stop_during_charging_sets_was_charging(
        self, charging_adapter, mock_api
    ):
        """충전 중 stop() 호출 시 _was_charging=True로 설정."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        charging_adapter.navigate(dest, execution)
        charging_adapter.cancel_cmd_attempt()

        # pre-charger 도착
        state = MagicMock()
        target = charging_adapter._nav.target_position
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.50,
        )
        charging_adapter.update(state, data)
        assert charging_adapter._charging.is_active is True

        # negotiation → stop
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        charging_adapter.stop(activity)
        charging_adapter.cancel_cmd_attempt()

        # stopCharging은 즉시 전송하지 않음
        mock_api.start_activity.assert_not_called()
        # 대신 _was_charging 플래그 설정
        assert charging_adapter._charging.was_charging is True
        assert charging_adapter._charging.is_active is False
        assert charging_adapter._charging.is_pending is False

    def test_reset_order_clears_charging_state_but_preserves_was(
        self, charging_adapter
    ):
        """_reset_order_state가 충전 상태를 초기화하되 _was_charging은 보존."""
        charging_adapter._charging.is_active = True
        charging_adapter._charging.is_pending = True
        charging_adapter._charging.station_name = 'charger_1'
        charging_adapter._charging.action_id = 'some_id'
        charging_adapter._charging.was_charging = True

        charging_adapter._reset_order_state()

        assert charging_adapter._charging.is_active is False
        assert charging_adapter._charging.is_pending is False
        assert charging_adapter._charging.station_name is None
        assert charging_adapter._charging.action_id is None
        # _was_charging은 보존됨
        assert charging_adapter._charging.was_charging is True

    def test_next_navigate_after_charging_has_stop_charging(
        self, charging_adapter, mock_api
    ):
        """충전 완료 후 다음 navigate에 stopCharging nodeAction 부착."""
        # 1. 충전 navigate
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        charging_adapter.navigate(dest, execution)
        charging_adapter.cancel_cmd_attempt()

        # pre-charger 도착 + startCharging FINISHED
        state = MagicMock()
        target = charging_adapter._nav.target_position
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.50,
        )
        charging_adapter.update(state, data)
        mock_api.is_command_completed.return_value = True
        charging_adapter.update(state, data)
        assert charging_adapter._charging.was_charging is True

        # task 종료 시뮬레이션
        charging_adapter._reset_order_state()
        assert charging_adapter._charging.was_charging is True

        # 2. 새로운 navigate (go_to_place)
        charging_adapter.position = [5.0, 5.0, 0.0]
        mock_api.navigate.reset_mock()
        mock_api.is_command_completed.return_value = False

        dest2 = MagicMock()
        dest2.name = 'wp2'
        dest2.final_name = 'wp2'
        dest2.position = [5.0, 0.0, 0.0]
        dest2.map = 'map1'
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'new-task-001'
        charging_adapter.update_handle = mock_handle

        charging_adapter.navigate(dest2, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        call_args = mock_api.navigate.call_args[0]
        nodes = call_args[2]

        # 첫 번째 노드에 stopCharging nodeAction 부착 확인
        first_node = nodes[0]
        stop_actions = [
            a for a in first_node.actions
            if a.action_type == 'stopCharging'
        ]
        assert len(stop_actions) == 1
        assert charging_adapter._charging.was_charging is False

    def test_was_charging_persists_through_reset(
        self, charging_adapter
    ):
        """_was_charging은 _reset_order_state 이후에도 유지된다."""
        charging_adapter._charging.was_charging = True
        charging_adapter._reset_order_state()
        assert charging_adapter._charging.was_charging is True

    def test_charging_navigate_uses_track_action_id(
        self, charging_adapter, mock_api
    ):
        """충전 navigate에서 track_action_id가 전달된다."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        # track_action_id가 navigate 호출에 포함됨
        call_kwargs = mock_api.navigate.call_args[1]
        assert 'track_action_id' in call_kwargs
        assert call_kwargs['track_action_id'] is not None
        assert 'startCharging' in call_kwargs['track_action_id']

    def test_full_charging_cycle(
        self, charging_adapter, mock_api
    ):
        """전체 충전 흐름: navigate → 도착 → action완료 → 다음 order."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        # 1. navigate (dock 감지 → 충전 pending)
        charging_adapter.navigate(dest, execution)
        charging_adapter.cancel_cmd_attempt()

        assert charging_adapter._charging.is_pending is True
        assert charging_adapter._nav.is_navigating is True
        assert charging_adapter._charging.is_active is False

        # order에 charger 노드 미포함 확인
        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]
        assert 'charger_1' not in node_ids

        # startCharging action 확인
        has_start_charging = any(
            a.action_type == 'startCharging'
            for n in nodes for a in n.actions
        )
        assert has_start_charging

        # 2. 이동 중 (도착 전)
        state = MagicMock()
        target = charging_adapter._nav.target_position
        data_moving = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[2.0, 0.0, 0.0],  # 멀리 있음
            battery_soc=0.30,
        )
        charging_adapter.update(state, data_moving)
        assert charging_adapter._nav.is_navigating is True
        assert charging_adapter._charging.is_active is False
        execution.finished.assert_not_called()

        # 3. pre-charger 노드 도착
        data_arrived = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.40,
        )
        charging_adapter.update(state, data_arrived)
        assert charging_adapter._charging.is_active is True
        assert charging_adapter._nav.is_navigating is False
        execution.finished.assert_not_called()

        # 4. 충전 중 (action 미완료)
        mock_api.is_command_completed.return_value = False
        data_charging = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.70,
        )
        charging_adapter.update(state, data_charging)
        assert charging_adapter._charging.is_active is True
        execution.finished.assert_not_called()

        # 5. startCharging action FINISHED → 충전 task 완료
        mock_api.is_command_completed.return_value = True
        charging_adapter.update(state, data_charging)

        execution.finished.assert_called_once()
        assert charging_adapter.execution is None
        assert charging_adapter._charging.is_active is False
        assert charging_adapter._charging.was_charging is True

        # 6. task 종료 → order reset
        charging_adapter._reset_order_state()
        assert charging_adapter._charging.was_charging is True

        # 7. 다음 order에서 stopCharging nodeAction 부착
        mock_api.navigate.reset_mock()
        mock_api.is_command_completed.return_value = False
        charging_adapter.position = [5.0, 5.0, 0.0]
        dest2 = MagicMock()
        dest2.name = 'wp1'
        dest2.final_name = 'wp1'
        dest2.position = [0.0, 0.0, 0.0]
        dest2.map = 'map1'
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'goto-task-001'
        charging_adapter.update_handle = mock_handle

        charging_adapter.navigate(dest2, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        nodes2 = mock_api.navigate.call_args[0][2]
        first_node = nodes2[0]
        stop_actions = [
            a for a in first_node.actions
            if a.action_type == 'stopCharging'
        ]
        assert len(stop_actions) == 1
        assert charging_adapter._charging.was_charging is False

    def test_intermediate_navigate_excludes_charger(
        self, charging_adapter, mock_api
    ):
        """중간 dest로 navigate 시에도 charger가 order에 포함되지 않는다.

        final_destination이 charger이지만 dest는 중간 노드(wp2)인 경우,
        Tier 2로 charger까지 경로가 확장되지만 charger는 order에서 제거된다.
        """
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]
        assert 'charger_1' not in node_ids
        # wp3 (pre-charger)가 horizon으로 포함
        assert 'wp3' in node_ids

    def test_intermediate_navigate_no_start_charging(
        self, charging_adapter, mock_api
    ):
        """중간 dest navigate 시 startCharging이 부착되지 않는다."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        has_start_charging = any(
            a.action_type == 'startCharging'
            for n in nodes for a in n.actions
        )
        assert not has_start_charging

    def test_intermediate_navigate_base_at_dest(
        self, charging_adapter, mock_api
    ):
        """중간 dest navigate 시 base가 dest까지, 나머지 horizon."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'

        charging_adapter.navigate(dest, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        # wp1(base) → wp2(base) → wp3(horizon)
        for n in nodes:
            if n.node_id in ('wp1', 'wp2'):
                assert n.released is True, (
                    f'{n.node_id} should be base'
                )
            else:
                assert n.released is False, (
                    f'{n.node_id} should be horizon'
                )


class TestChargingDecommission:
    """충전 중 decommission / SOC 기반 recommission 테스트.

    startCharging 완료 후 SOC가 recharge_soc에 도달할 때까지
    로봇을 decommission 상태로 유지하여 Task 할당을 차단한다.
    """

    @pytest.fixture
    def charging_adapter(self, mock_api, mock_node):
        """Charger 노드가 포함된 어댑터 (recharge_soc=0.8)."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        nodes = {
            'wp1': {'x': 0.0, 'y': 0.0, 'attributes': {}},
            'wp2': {'x': 5.0, 'y': 0.0, 'attributes': {}},
            'wp3': {'x': 5.0, 'y': 5.0, 'attributes': {}},
            'charger_1': {
                'x': 5.0, 'y': 10.0,
                'attributes': {'is_charger': True},
            },
        }
        edges = {
            'e0': {'start': 'wp1', 'end': 'wp2', 'attributes': {}},
            'e1': {'start': 'wp2', 'end': 'wp1', 'attributes': {}},
            'e2': {'start': 'wp2', 'end': 'wp3', 'attributes': {}},
            'e3': {'start': 'wp3', 'end': 'wp2', 'attributes': {}},
            'e4': {
                'start': 'wp3', 'end': 'charger_1',
                'attributes': {},
            },
            'e5': {
                'start': 'charger_1', 'end': 'wp3',
                'attributes': {},
            },
        }
        graph = create_graph(nodes, edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=nodes, nav_edges=edges, nav_graph=graph,
            recharge_soc=0.8,
        )
        robot.configuration = MagicMock()
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'charge-task-001'
        robot.update_handle = mock_handle
        robot.position = [0.0, 0.0, 0.0]
        return robot

    def _complete_charging(self, adapter, mock_api):
        """충전 navigate → pre-charger 도착 → startCharging FINISHED."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        adapter.navigate(dest, execution)
        adapter.cancel_cmd_attempt()

        # pre-charger 도착
        state = MagicMock()
        target = adapter._nav.target_position
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.30,
        )
        adapter.update(state, data)

        # startCharging FINISHED
        mock_api.is_command_completed.return_value = True
        adapter.update(state, data)

        return execution

    def test_decommission_on_charging_start(
        self, charging_adapter, mock_api
    ):
        """Charging 완료 시 decommission 플래그가 설정된다."""
        self._complete_charging(charging_adapter, mock_api)

        assert charging_adapter._charging.is_decommissioned is True
        assert charging_adapter._charging.was_charging is True

    def test_stays_decommissioned_while_soc_low(
        self, charging_adapter, mock_api
    ):
        """SOC가 recharge_soc 미만이면 decommission이 유지된다."""
        self._complete_charging(charging_adapter, mock_api)

        # SOC 0.5 < recharge_soc 0.8 → decommission 유지
        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 5.0, 0.0],
            battery_soc=0.5,
        )
        mock_api.is_command_completed.return_value = False
        charging_adapter.update(state, data)

        assert charging_adapter._charging.is_decommissioned is True

        more_handle = (
            charging_adapter.update_handle.more.return_value
        )
        more_handle.set_commission.assert_called()
        commission = more_handle.commission.return_value
        assert commission.accept_dispatched_tasks is False
        assert commission.accept_direct_tasks is False
        assert commission.perform_idle_behavior is False

    def test_recommission_when_soc_reaches_threshold(
        self, charging_adapter, mock_api
    ):
        """SOC가 정확히 recharge_soc에 도달하면 recommission된다."""
        self._complete_charging(charging_adapter, mock_api)

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 5.0, 0.0],
            battery_soc=0.8,  # == recharge_soc
        )
        mock_api.is_command_completed.return_value = False
        charging_adapter.update(state, data)

        assert charging_adapter._charging.is_decommissioned is False
        assert charging_adapter._last_commission is None

    def test_recommission_above_threshold(
        self, charging_adapter, mock_api
    ):
        """SOC가 recharge_soc를 초과해도 recommission된다."""
        self._complete_charging(charging_adapter, mock_api)

        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[5.0, 5.0, 0.0],
            battery_soc=0.95,  # > recharge_soc
        )
        mock_api.is_command_completed.return_value = False
        charging_adapter.update(state, data)

        assert charging_adapter._charging.is_decommissioned is False
        assert charging_adapter._last_commission is None

    def test_stop_during_charging_clears_decommission(
        self, charging_adapter, mock_api
    ):
        """충전 중 negotiation stop 시 decommission 해제."""
        dest = MagicMock()
        dest.name = 'charger_1'
        dest.final_name = 'charger_1'
        dest.position = [5.0, 10.0, 0.0]
        dest.map = 'map1'
        execution = MagicMock()

        charging_adapter.navigate(dest, execution)
        charging_adapter.cancel_cmd_attempt()

        # pre-charger 도착 → _is_charging = True
        state = MagicMock()
        target = charging_adapter._nav.target_position
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[target[0], target[1], 0.0],
            battery_soc=0.30,
        )
        charging_adapter.update(state, data)
        assert charging_adapter._charging.is_active is True

        # negotiation stop
        activity = MagicMock()
        execution.identifier.is_same.return_value = True
        charging_adapter.stop(activity)
        charging_adapter.cancel_cmd_attempt()

        assert charging_adapter._charging.is_decommissioned is False
        assert charging_adapter._charging.was_charging is True

    def test_navigate_with_stop_charging_clears_flag(
        self, charging_adapter, mock_api
    ):
        """Navigate에서 stopCharging 부착 시 decommission 해제."""
        self._complete_charging(charging_adapter, mock_api)
        assert charging_adapter._charging.is_decommissioned is True

        # task 종료 → order reset
        charging_adapter._reset_order_state()
        assert charging_adapter._charging.is_decommissioned is True

        # 새 navigate → stopCharging 부착
        charging_adapter.position = [5.0, 5.0, 0.0]
        mock_api.navigate.reset_mock()
        mock_api.is_command_completed.return_value = False

        dest2 = MagicMock()
        dest2.name = 'wp2'
        dest2.final_name = 'wp2'
        dest2.position = [5.0, 0.0, 0.0]
        dest2.map = 'map1'
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'new-task-001'
        charging_adapter.update_handle = mock_handle

        charging_adapter.navigate(dest2, MagicMock())
        charging_adapter.cancel_cmd_attempt()

        assert charging_adapter._charging.is_decommissioned is False
        assert charging_adapter._charging.was_charging is False

    def test_no_decommission_when_not_charging(
        self, charging_adapter, mock_api
    ):
        """충전이 아닌 일반 상태에서는 decommission이 적용 안 됨."""
        state = MagicMock()
        data = RobotUpdateData(
            robot_name='AGV-001', map_name='map1',
            position=[0.0, 0.0, 0.0],
            battery_soc=0.3,
        )
        mock_api.get_commission_state.return_value = CommissionState(
            True, True, True
        )

        charging_adapter.update(state, data)

        assert charging_adapter._charging.is_decommissioned is False

    def test_default_recharge_soc(
        self, mock_api, mock_node,
        sample_nav_nodes, sample_nav_edges,
    ):
        """기본 recharge_soc는 1.0이다."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        graph = create_graph(sample_nav_nodes, sample_nav_edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=sample_nav_nodes,
            nav_edges=sample_nav_edges,
            nav_graph=graph,
        )
        assert robot.recharge_soc == 1.0

    def test_decommission_persists_through_reset(
        self, charging_adapter, mock_api
    ):
        """_is_charging_decommissioned은 _reset_order_state 이후 유지."""
        self._complete_charging(charging_adapter, mock_api)
        assert charging_adapter._charging.is_decommissioned is True

        charging_adapter._reset_order_state()

        assert charging_adapter._charging.is_decommissioned is True


class TestPickDropFlow:
    """pickDrop Base/Horizon 분리 테스트.

    pickDrop=True 속성이 있는 destination 노드를 horizon으로 유지하고,
    execute_action에서 released로 전환 + action 부착.
    Phase 1+2 = order_A, Phase 3+4 = order_B (별도 orderID).

    Graph:
        wp1(0,0) --- wp2(5,0) --- wp3(5,5)
        wp2: pickDrop=True (pickup station)
        wp3: pickDrop=True (dropoff station)
    """

    @pytest.fixture
    def pick_drop_adapter(self, mock_api, mock_node):
        """Create adapter with pick_drop node attributes."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        nodes = {
            'wp1': {'x': 0.0, 'y': 0.0, 'attributes': {}},
            'wp2': {
                'x': 5.0, 'y': 0.0,
                'attributes': {'pickDrop': True},
            },
            'wp3': {
                'x': 5.0, 'y': 5.0,
                'attributes': {'pickDrop': True},
            },
            'wp4': {'x': 0.0, 'y': 5.0, 'attributes': {}},
        }
        edges = {
            'e0': {'start': 'wp1', 'end': 'wp2', 'attributes': {}},
            'e1': {'start': 'wp2', 'end': 'wp1', 'attributes': {}},
            'e2': {'start': 'wp2', 'end': 'wp3', 'attributes': {}},
            'e3': {'start': 'wp3', 'end': 'wp2', 'attributes': {}},
            'e4': {'start': 'wp3', 'end': 'wp4', 'attributes': {}},
            'e5': {'start': 'wp4', 'end': 'wp3', 'attributes': {}},
            'e6': {'start': 'wp4', 'end': 'wp1', 'attributes': {}},
            'e7': {'start': 'wp1', 'end': 'wp4', 'attributes': {}},
        }
        graph = create_graph(nodes, edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=nodes, nav_edges=edges, nav_graph=graph,
        )
        robot.configuration = MagicMock()
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'cart-delivery-001'
        robot.update_handle = mock_handle
        robot.position = [0.0, 0.0, 0.0]
        return robot

    def test_pickdrop_navigate_removes_dest_from_path(
        self, pick_drop_adapter, mock_api
    ):
        """Verify pickDrop dest is removed from path."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'

        pick_drop_adapter.navigate(dest, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]

        # wp2(pickDrop)가 제거되어 wp1만 남음
        assert node_ids == ['wp1']
        assert nodes[0].released is True

    def test_pickdrop_navigate_target_pre_dest(
        self, pick_drop_adapter, mock_api
    ):
        """Navigate target position is set to pre-destination node."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'

        pick_drop_adapter.navigate(dest, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        # wp1(0,0) 좌표가 도착 판정 대상
        assert pick_drop_adapter._nav.target_position == [
            0.0, 0.0,
        ]

    def test_pickdrop_action_releases_dest(
        self, pick_drop_adapter, mock_api
    ):
        """Action order update releases all nodes, action on last node."""
        # Phase 1: navigate to wp2
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        pick_drop_adapter.navigate(dest, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()
        mock_api.navigate.reset_mock()

        # Phase 2: pick action
        pick_drop_adapter.position = [0.0, 0.0, 0.0]  # at wp1
        pick_drop_adapter.execute_action(
            'pick', {'loadType': 'Tool'}, MagicMock()
        )
        pick_drop_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]

        # 모든 노드 base (released)
        for node in nodes:
            assert node.released is True, (
                f'{node.node_id} should be released'
            )

        # action이 마지막 노드(wp2)에 부착
        last_node = nodes[-1]
        assert len(last_node.actions) == 1
        assert last_node.actions[0].action_type == 'pick'
        assert last_node.actions[0].blocking_type.value == 'HARD'

    def test_pickdrop_action_resets_order(
        self, pick_drop_adapter, mock_api
    ):
        """Order lifecycle resets after pick_drop action."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        pick_drop_adapter.navigate(dest, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        assert pick_drop_adapter._order.active_order_id is not None

        pick_drop_adapter.position = [0.0, 0.0, 0.0]
        pick_drop_adapter.execute_action('pick', {}, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        assert pick_drop_adapter._order.active_order_id is None
        assert pick_drop_adapter._order.order_update_id == 0
        assert pick_drop_adapter._order.last_stitch_seq_id == 0
        assert pick_drop_adapter._pick_drop.destination is None

    def test_pickdrop_full_cart_delivery(
        self, pick_drop_adapter, mock_api
    ):
        """Phase1+2=orderA, Phase3+4=orderB (다른 orderID)."""
        # Phase 1: navigate to wp2 (pickup)
        dest1 = MagicMock()
        dest1.name = 'wp2'
        dest1.final_name = 'wp2'
        dest1.position = [5.0, 0.0, 0.0]
        dest1.map = 'map1'
        pick_drop_adapter.navigate(dest1, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        order_a = pick_drop_adapter._order.active_order_id
        assert order_a is not None
        assert pick_drop_adapter._order.order_update_id == 0

        # Phase 2: pick action at wp2
        pick_drop_adapter.position = [0.0, 0.0, 0.0]
        pick_drop_adapter.execute_action(
            'pick', {'loadType': 'Tool'}, MagicMock()
        )
        pick_drop_adapter.cancel_cmd_attempt()

        # order 리셋됨
        assert pick_drop_adapter._order.active_order_id is None

        # Phase 3: navigate to wp3 (dropoff)
        pick_drop_adapter.position = [5.0, 0.0, 0.0]
        dest2 = MagicMock()
        dest2.name = 'wp3'
        dest2.final_name = 'wp3'
        dest2.position = [5.0, 5.0, 0.0]
        dest2.map = 'map1'
        pick_drop_adapter.navigate(dest2, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        order_b = pick_drop_adapter._order.active_order_id
        assert order_b is not None
        assert order_b != order_a  # 다른 orderID
        assert pick_drop_adapter._order.order_update_id == 0

        # Phase 4: drop action at wp3
        pick_drop_adapter.position = [5.0, 0.0, 0.0]
        pick_drop_adapter.execute_action(
            'drop', {'stationName': 'wp3'}, MagicMock()
        )
        pick_drop_adapter.cancel_cmd_attempt()

        # order 리셋됨
        assert pick_drop_adapter._order.active_order_id is None

    def test_pickdrop_robot_at_destination(
        self, pick_drop_adapter, mock_api
    ):
        """로봇이 이미 pickDrop dest에 있으면 즉시 완료."""
        pick_drop_adapter.position = [5.0, 0.0, 0.0]  # at wp2

        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        dest.waypoint_names = ['wp2']
        execution = MagicMock()

        pick_drop_adapter.navigate(dest, execution)

        # order 미생성, 즉시 완료
        execution.finished.assert_called_once()
        assert pick_drop_adapter.execution is None
        assert pick_drop_adapter._nav.is_navigating is False
        mock_api.navigate.assert_not_called()

    def test_pickdrop_go_to_place_reset(
        self, pick_drop_adapter, mock_api
    ):
        """Task end with pick_drop pending sends cancelOrder."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        pick_drop_adapter.navigate(dest, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        assert pick_drop_adapter._pick_drop.destination == 'wp2'

        pick_drop_adapter._reset_order_state()
        pick_drop_adapter.cancel_cmd_attempt()

        # cancelOrder 전송됨
        mock_api.stop.assert_called_once()
        assert pick_drop_adapter._pick_drop.destination is None

    def test_pickdrop_seq_continuity(
        self, pick_drop_adapter, mock_api
    ):
        """Sequence ID continuity within pick_drop order."""
        dest = MagicMock()
        dest.name = 'wp2'
        dest.final_name = 'wp2'
        dest.position = [5.0, 0.0, 0.0]
        dest.map = 'map1'
        pick_drop_adapter.navigate(dest, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        # Phase 1 nodes: wp1만 (wp2 제거됨)
        nav_nodes = mock_api.navigate.call_args[0][2]
        nav_edges = mock_api.navigate.call_args[0][3]
        assert len(nav_nodes) == 1
        assert nav_nodes[0].sequence_id == 0
        assert len(nav_edges) == 0

        mock_api.navigate.reset_mock()

        # Phase 2: pick action
        pick_drop_adapter.position = [0.0, 0.0, 0.0]
        pick_drop_adapter.execute_action('pick', {}, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        action_nodes = mock_api.navigate.call_args[0][2]
        # stitch_seq was 0 (base_end_index=0 → wp1)
        # action update: seq starts from 0
        assert action_nodes[0].sequence_id == 0

    def test_non_pickdrop_unaffected(
        self, pick_drop_adapter, mock_api
    ):
        """경로에 pickDrop 노드가 없으면 기본 동작 유지."""
        pick_drop_adapter.position = [0.0, 5.0, 0.0]  # at wp4

        dest = MagicMock()
        dest.name = 'wp1'
        dest.final_name = 'wp1'
        dest.position = [0.0, 0.0, 0.0]
        dest.map = 'map1'

        pick_drop_adapter.navigate(dest, MagicMock())
        pick_drop_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        # 경로에 pickDrop 없으므로 모든 노드 base
        for node in nodes:
            assert node.released is True, (
                f'{node.node_id} should be released (no pickDrop)'
            )
        assert pick_drop_adapter._pick_drop.destination is None


class TestPickDropStationRemoval:
    """pickDrop Station Node Removal 테스트.

    pickDrop 속성이 destination의 직전 노드(staging node)에 있고,
    destination 자체는 실제 카트/드롭 위치(station node)인 시나리오.
    Station node는 VDA5050 order에서 제거되고,
    action은 staging node에 부착된다.

    Graph:
        wp1(0,0)↔wp2(5,0)↔wp3(5,5,pickDrop)↔wp4(10,5)
        wp4↔wp5(10,0,pickDrop)↔wp6(15,0)
    """

    @pytest.fixture
    def station_adapter(self, mock_api, mock_node):
        """Create adapter for station node removal tests."""
        from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
            create_graph,
        )
        nodes = {
            'wp1': {'x': 0.0, 'y': 0.0, 'attributes': {}},
            'wp2': {'x': 5.0, 'y': 0.0, 'attributes': {}},
            'wp3': {
                'x': 5.0, 'y': 5.0,
                'attributes': {'pickDrop': True},
            },
            'wp4': {'x': 10.0, 'y': 5.0, 'attributes': {}},
            'wp5': {
                'x': 10.0, 'y': 0.0,
                'attributes': {'pickDrop': True},
            },
            'wp6': {'x': 15.0, 'y': 0.0, 'attributes': {}},
        }
        edges = {
            'e0': {'start': 'wp1', 'end': 'wp2', 'attributes': {}},
            'e1': {'start': 'wp2', 'end': 'wp1', 'attributes': {}},
            'e2': {'start': 'wp2', 'end': 'wp3', 'attributes': {}},
            'e3': {'start': 'wp3', 'end': 'wp2', 'attributes': {}},
            'e4': {'start': 'wp3', 'end': 'wp4', 'attributes': {}},
            'e5': {'start': 'wp4', 'end': 'wp3', 'attributes': {}},
            'e6': {'start': 'wp4', 'end': 'wp5', 'attributes': {}},
            'e7': {'start': 'wp5', 'end': 'wp4', 'attributes': {}},
            'e8': {'start': 'wp5', 'end': 'wp6', 'attributes': {}},
            'e9': {'start': 'wp6', 'end': 'wp5', 'attributes': {}},
        }
        graph = create_graph(nodes, edges)
        robot = RobotAdapter(
            name='AGV-001', api=mock_api, node=mock_node,
            fleet_handle=MagicMock(),
            nav_nodes=nodes, nav_edges=edges, nav_graph=graph,
        )
        robot.configuration = MagicMock()
        mock_handle = MagicMock()
        mock_handle.more.return_value.current_task_id \
            .return_value = 'cart-delivery-002'
        robot.update_handle = mock_handle
        robot.position = [0.0, 0.0, 0.0]
        return robot

    def test_station_removal_path(
        self, station_adapter, mock_api
    ):
        """navigate(dest=wp4) → wp4(station)과 wp3(pickDrop) 모두 제거."""
        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'

        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]

        assert 'wp4' not in node_ids
        assert 'wp3' not in node_ids
        assert node_ids[-1] == 'wp2'

    def test_station_removal_pick_drop_dest(
        self, station_adapter, mock_api
    ):
        """_pick_drop_destination == wp3 (staging node)."""
        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'

        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()

        assert station_adapter._pick_drop.destination == 'wp3'

    def test_station_removal_station_saved(
        self, station_adapter, mock_api
    ):
        """_pick_drop_station_node == wp4 (station node)."""
        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'

        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()

        assert station_adapter._pick_drop.station_node == 'wp4'

    def test_station_removal_all_base(
        self, station_adapter, mock_api
    ):
        """wp3,wp4 제거 후 남은 wp1,wp2는 모두 base."""
        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'

        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        for node in nodes:
            assert node.released is True, (
                f'{node.node_id} should be base'
            )

    def test_station_removal_navigate_target(
        self, station_adapter, mock_api
    ):
        """_navigate_target_position == wp2 좌표 (pre-staging)."""
        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'

        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()

        # wp2(5,0) — pre-pickDrop node
        assert station_adapter._nav.target_position == [
            5.0, 0.0,
        ]

    def test_station_removal_action_order_update(
        self, station_adapter, mock_api
    ):
        """Order update: 모든 노드 base, action on staging node."""
        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'
        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()
        mock_api.navigate.reset_mock()

        station_adapter.position = [5.0, 0.0, 0.0]
        station_adapter.execute_action('pick', {}, MagicMock())
        station_adapter.cancel_cmd_attempt()

        nodes = mock_api.navigate.call_args[0][2]
        for node in nodes:
            assert node.released is True, (
                f'{node.node_id} should be base (released)'
            )
        # action on last node (pickDrop dest = wp3)
        assert nodes[-1].node_id == 'wp3'
        assert len(nodes[-1].actions) == 1
        assert nodes[-1].actions[0].action_type == 'pick'

    def test_station_removal_resets(
        self, station_adapter, mock_api
    ):
        """Action 후 _pick_drop_station_node = None."""
        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'
        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()

        assert station_adapter._pick_drop.station_node == 'wp4'

        station_adapter.position = [5.0, 0.0, 0.0]
        station_adapter.execute_action('pick', {}, MagicMock())
        station_adapter.cancel_cmd_attempt()

        assert station_adapter._pick_drop.station_node is None
        assert station_adapter._pick_drop.destination is None

    def test_station_removal_full_delivery(
        self, station_adapter, mock_api
    ):
        """Full delivery: Phase1+2=orderA, Phase3+4=orderB."""
        # Phase 1: navigate to wp4 (pick station)
        dest1 = MagicMock()
        dest1.name = 'wp4'
        dest1.final_name = 'wp4'
        dest1.position = [10.0, 5.0, 0.0]
        dest1.map = 'map1'
        station_adapter.navigate(dest1, MagicMock())
        station_adapter.cancel_cmd_attempt()

        order_a = station_adapter._order.active_order_id
        assert order_a is not None
        assert station_adapter._pick_drop.station_node == 'wp4'

        # Phase 2: pick action
        station_adapter.position = [5.0, 0.0, 0.0]  # at wp2
        station_adapter.execute_action('pick', {}, MagicMock())
        station_adapter.cancel_cmd_attempt()

        # order 리셋
        assert station_adapter._order.active_order_id is None
        assert station_adapter._pick_drop.station_node is None

        # Phase 3: navigate to wp6 (drop station)
        mock_api.navigate.reset_mock()
        station_adapter.position = [5.0, 5.0, 0.0]  # at wp3
        dest2 = MagicMock()
        dest2.name = 'wp6'
        dest2.final_name = 'wp6'
        dest2.position = [15.0, 0.0, 0.0]
        dest2.map = 'map1'
        station_adapter.navigate(dest2, MagicMock())
        station_adapter.cancel_cmd_attempt()

        order_b = station_adapter._order.active_order_id
        assert order_b is not None
        assert order_b != order_a
        assert station_adapter._pick_drop.station_node == 'wp6'

        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]
        assert 'wp6' not in node_ids

        # Phase 4: drop action (stationName은 RMF가 params로 제공)
        mock_api.navigate.reset_mock()
        station_adapter.position = [10.0, 5.0, 0.0]  # at wp4
        station_adapter.execute_action(
            'drop', {'stationName': 'wp6'}, MagicMock()
        )
        station_adapter.cancel_cmd_attempt()

        action_nodes = mock_api.navigate.call_args[0][2]
        action = action_nodes[-1].actions[0]
        param_dict = {
            p.key: p.value for p in action.action_parameters
        }
        assert param_dict.get('stationName') == 'wp6'
        assert station_adapter._order.active_order_id is None

    def test_station_removal_at_staging_node(
        self, station_adapter, mock_api
    ):
        """이미 staging node에 있을 때 → 즉시 완료."""
        station_adapter.position = [5.0, 5.0, 0.0]  # at wp3

        dest = MagicMock()
        dest.name = 'wp4'
        dest.final_name = 'wp4'
        dest.position = [10.0, 5.0, 0.0]
        dest.map = 'map1'
        dest.waypoint_names = ['wp3', 'wp4']
        execution = MagicMock()

        station_adapter.navigate(dest, execution)

        # station removal → path=[wp3], pickDrop early return
        execution.finished.assert_called_once()
        assert station_adapter.execution is None
        assert station_adapter._nav.is_navigating is False

    def test_direct_pickdrop_also_removes_dest(
        self, station_adapter, mock_api
    ):
        """Dest 자체에 pickDrop 있는 시나리오도 dest를 path에서 제거."""
        station_adapter.position = [0.0, 0.0, 0.0]

        # wp3 자체가 pickDrop
        dest = MagicMock()
        dest.name = 'wp3'
        dest.final_name = 'wp3'
        dest.position = [5.0, 5.0, 0.0]
        dest.map = 'map1'

        station_adapter.navigate(dest, MagicMock())
        station_adapter.cancel_cmd_attempt()

        # dest(wp3)에 pickDrop
        assert station_adapter._pick_drop.destination == 'wp3'
        # station node removal은 발생하지 않음
        assert station_adapter._pick_drop.station_node is None

        nodes = mock_api.navigate.call_args[0][2]
        node_ids = [n.node_id for n in nodes]

        # wp3은 path에서 제거됨
        assert 'wp3' not in node_ids
        # wp1, wp2만 남고 모두 base
        assert node_ids == ['wp1', 'wp2']
        for node in nodes:
            assert node.released is True
