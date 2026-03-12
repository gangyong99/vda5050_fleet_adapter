"""Vda5050RobotAPI 유닛 테스트."""

import json
from unittest.mock import MagicMock

import pytest

from vda5050_fleet_adapter.domain.entities.agv_state import AgvState
from vda5050_fleet_adapter.domain.entities.battery import BatteryState
from vda5050_fleet_adapter.domain.entities.edge import Edge
from vda5050_fleet_adapter.domain.entities.error import AgvError
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.node import Node
from vda5050_fleet_adapter.domain.entities.safety import SafetyState
from vda5050_fleet_adapter.domain.enums import (
    ActionStatus,
    ConnectionState,
    ErrorLevel,
    EStopType,
    OperatingMode,
)
from vda5050_fleet_adapter.domain.value_objects.position import (
    AgvPosition,
    NodePosition,
)
from vda5050_fleet_adapter.infra.mqtt.vda5050_robot_api import (
    Vda5050RobotAPI,
)
from vda5050_fleet_adapter.usecase.ports.robot_api import (
    CommissionState,
    RobotAPIResult,
)


@pytest.fixture
def mock_mqtt():
    """Mock MqttClient."""
    mqtt = MagicMock()
    mqtt.is_connected = True
    return mqtt


@pytest.fixture
def api(mock_mqtt):
    """Vda5050RobotAPI instance with mock MQTT."""
    return Vda5050RobotAPI(
        mqtt_client=mock_mqtt,
        prefix='uagv/v2/TestCo',
        manufacturer='TestCo',
    )


class TestNavigate:
    """navigate() 테스트."""

    def test_navigate_publishes_order(self, api, mock_mqtt):
        """navigate가 MQTT로 Order를 발행한다."""
        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
            Node(
                node_id='wp2', sequence_id=2, released=True,
                node_position=NodePosition(x=5.0, y=0.0, map_id='map1'),
            ),
        ]
        edges = [
            Edge(
                edge_id='e1', sequence_id=1, released=True,
                start_node_id='wp1', end_node_id='wp2',
            ),
        ]

        result = api.navigate('AGV-001', 1, nodes, edges, 'map1')

        assert result == RobotAPIResult.SUCCESS
        mock_mqtt.publish.assert_called_once()
        topic = mock_mqtt.publish.call_args[0][0]
        assert topic == 'uagv/v2/TestCo/AGV-001/order'
        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['orderId'].startswith('order_1_')
        assert len(data['nodes']) == 2
        assert len(data['edges']) == 1

    def test_navigate_uses_qos_0(self, api, mock_mqtt):
        """navigate가 QoS 0을 사용한다."""
        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
        ]
        api.navigate('AGV-001', 1, nodes, [], 'map1')

        assert mock_mqtt.publish.call_args[1].get('qos', 0) == 0

    def test_navigate_retries_when_disconnected(self, api, mock_mqtt):
        """MQTT 미연결 시 RETRY를 반환한다."""
        mock_mqtt.is_connected = False
        result = api.navigate('AGV-001', 1, [], [], 'map1')
        assert result == RobotAPIResult.RETRY

    def test_navigate_stores_cmd_order_mapping(self, api, mock_mqtt):
        """navigate가 cmd_id → order_id 매핑을 저장한다."""
        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
        ]
        api.navigate('AGV-001', 42, nodes, [], 'map1')
        assert 42 in api._cmd_order_map.get('AGV-001', {})

    def test_navigate_uses_provided_order_id(self, api, mock_mqtt):
        """제공된 order_id를 사용한다."""
        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
        ]
        result = api.navigate(
            'AGV-001', 1, nodes, [], 'map1',
            order_id='custom_order_123',
        )

        assert result == RobotAPIResult.SUCCESS
        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['orderId'] == 'custom_order_123'

    def test_navigate_auto_generates_order_id_when_empty(self, api, mock_mqtt):
        """order_id가 빈 문자열이면 자동 생성한다."""
        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
        ]
        api.navigate('AGV-001', 5, nodes, [], 'map1', order_id='')

        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['orderId'].startswith('order_5_')

    def test_navigate_uses_provided_order_update_id(self, api, mock_mqtt):
        """order_update_id가 payload에 반영된다."""
        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
        ]
        api.navigate(
            'AGV-001', 1, nodes, [], 'map1',
            order_id='order_1_abc', order_update_id=3,
        )

        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['orderUpdateId'] == 3


class TestStop:
    """stop() 테스트."""

    def test_stop_publishes_cancel_order(self, api, mock_mqtt):
        """stop이 cancelOrder instant action을 발행한다."""
        result = api.stop('AGV-001', 1)

        assert result == RobotAPIResult.SUCCESS
        mock_mqtt.publish.assert_called_once()
        topic = mock_mqtt.publish.call_args[0][0]
        assert topic == 'uagv/v2/TestCo/AGV-001/instantActions'
        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['actions'][0]['actionType'] == 'cancelOrder'

    def test_stop_retries_when_disconnected(self, api, mock_mqtt):
        """MQTT 미연결 시 RETRY를 반환한다."""
        mock_mqtt.is_connected = False
        result = api.stop('AGV-001', 1)
        assert result == RobotAPIResult.RETRY


class TestPause:
    """pause() 테스트."""

    def test_pause_publishes_start_pause(self, api, mock_mqtt):
        """pause가 startPause instant action을 발행한다."""
        result = api.pause('AGV-001', 1)

        assert result == RobotAPIResult.SUCCESS
        mock_mqtt.publish.assert_called_once()
        topic = mock_mqtt.publish.call_args[0][0]
        assert topic == 'uagv/v2/TestCo/AGV-001/instantActions'
        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['actions'][0]['actionType'] == 'startPause'

    def test_pause_retries_when_disconnected(self, api, mock_mqtt):
        """MQTT 미연결 시 RETRY를 반환한다."""
        mock_mqtt.is_connected = False
        result = api.pause('AGV-001', 1)
        assert result == RobotAPIResult.RETRY

    def test_pause_action_has_hard_blocking(self, api, mock_mqtt):
        """Start-pause action이 HARD blocking type이다."""
        api.pause('AGV-001', 1)

        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['actions'][0]['blockingType'] == 'HARD'


class TestStartActivity:
    """start_activity() 테스트."""

    def test_start_activity_publishes_action(self, api, mock_mqtt):
        """start_activity가 instant action을 발행한다."""
        result = api.start_activity(
            'AGV-001', 1, 'charge', {'station': 'cs1'}
        )

        assert result == RobotAPIResult.SUCCESS
        mock_mqtt.publish.assert_called_once()
        topic = mock_mqtt.publish.call_args[0][0]
        assert topic == 'uagv/v2/TestCo/AGV-001/instantActions'
        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['actions'][0]['actionType'] == 'charge'
        params = data['actions'][0]['actionParameters']
        assert any(p['key'] == 'station' for p in params)


class TestGetData:
    """get_data() 테스트."""

    def test_get_data_returns_none_without_state(self, api):
        """상태 미수신 시 None을 반환한다."""
        assert api.get_data('AGV-001') is None

    def test_get_data_returns_cached_state(self, api):
        """캐시된 상태를 반환한다."""
        state = MagicMock()
        state.agv_position = AgvPosition(
            x=1.0, y=2.0, theta=0.5, map_id='map1'
        )
        state.battery_state = BatteryState(battery_charge=80.0)
        api._state_cache['AGV-001'] = state

        data = api.get_data('AGV-001')
        assert data is not None
        assert data.robot_name == 'AGV-001'
        assert data.map_name == 'map1'
        assert data.position == [1.0, 2.0, 0.5]
        assert abs(data.battery_soc - 0.8) < 0.01


class TestIsCommandCompleted:
    """is_command_completed() 테스트."""

    def test_returns_false_without_state(self, api):
        """상태 미수신 시 False를 반환한다."""
        assert not api.is_command_completed('AGV-001', 1)

    def test_order_completed_when_no_nodes_and_not_driving(self, api):
        """nodeStates가 비고 driving=False이면 완료."""
        order_id = 'order_1_abc'
        api._cmd_order_map['AGV-001'] = {1: order_id}

        state = MagicMock()
        state.order_id = order_id
        state.node_states = []
        state.driving = False
        state.action_states = []
        state.has_fatal_error = False
        api._state_cache['AGV-001'] = state

        assert api.is_command_completed('AGV-001', 1)

    def test_order_not_completed_when_driving(self, api):
        """driving=True이면 미완료."""
        order_id = 'order_1_abc'
        api._cmd_order_map['AGV-001'] = {1: order_id}

        state = MagicMock()
        state.order_id = order_id
        state.node_states = []
        state.driving = True
        state.action_states = []
        state.has_fatal_error = False
        api._state_cache['AGV-001'] = state

        assert not api.is_command_completed('AGV-001', 1)

    def test_order_not_completed_when_released_nodes_remain(self, api):
        """Released(base) 노드가 남아있으면 미완료."""
        order_id = 'order_1_abc'
        api._cmd_order_map['AGV-001'] = {1: order_id}

        released_node = MagicMock()
        released_node.released = True
        state = MagicMock()
        state.order_id = order_id
        state.node_states = [released_node]
        state.driving = False
        state.action_states = []
        state.has_fatal_error = False
        api._state_cache['AGV-001'] = state

        assert not api.is_command_completed('AGV-001', 1)

    def test_order_completed_with_only_horizon_nodes(self, api):
        """Horizon 노드만 남고 driving=False이면 완료."""
        order_id = 'order_1_abc'
        api._cmd_order_map['AGV-001'] = {1: order_id}

        horizon_node1 = MagicMock()
        horizon_node1.released = False
        horizon_node2 = MagicMock()
        horizon_node2.released = False
        state = MagicMock()
        state.order_id = order_id
        state.node_states = [horizon_node1, horizon_node2]
        state.driving = False
        state.action_states = []
        state.has_fatal_error = False
        api._state_cache['AGV-001'] = state

        assert api.is_command_completed('AGV-001', 1)

    def test_action_completed_when_finished(self, api):
        """Action status가 FINISHED이면 완료."""
        action_id = 'charge_1_abc'
        api._cmd_order_map['AGV-001'] = {1: action_id}

        action_state = MagicMock()
        action_state.action_id = action_id
        action_state.action_status = ActionStatus.FINISHED

        state = MagicMock()
        state.order_id = ''
        state.node_states = []
        state.driving = False
        state.action_states = [action_state]
        state.has_fatal_error = False
        api._state_cache['AGV-001'] = state

        assert api.is_command_completed('AGV-001', 1)

    def test_action_not_completed_when_failed(self, api):
        """Action status가 FAILED이면 완료 처리하지 않고 대기."""
        action_id = 'charge_1_abc'
        api._cmd_order_map['AGV-001'] = {1: action_id}

        action_state = MagicMock()
        action_state.action_id = action_id
        action_state.action_status = ActionStatus.FAILED

        state = MagicMock()
        state.order_id = ''
        state.node_states = []
        state.driving = False
        state.action_states = [action_state]
        state.has_fatal_error = False
        api._state_cache['AGV-001'] = state

        assert not api.is_command_completed('AGV-001', 1)

    def test_order_not_completed_when_fatal_error(self, api):
        """FATAL 에러가 있으면 order 완료 처리하지 않고 대기."""
        order_id = 'order_1_abc'
        api._cmd_order_map['AGV-001'] = {1: order_id}

        state = MagicMock()
        state.order_id = order_id
        state.node_states = []
        state.driving = False
        state.action_states = []
        state.has_fatal_error = True
        api._state_cache['AGV-001'] = state

        assert not api.is_command_completed('AGV-001', 1)

    def test_order_completed_when_warning_only(self, api):
        """WARNING만 있으면 order 완료 처리 허용."""
        order_id = 'order_1_abc'
        api._cmd_order_map['AGV-001'] = {1: order_id}

        state = MagicMock()
        state.order_id = order_id
        state.node_states = []
        state.driving = False
        state.action_states = []
        state.has_fatal_error = False
        api._state_cache['AGV-001'] = state

        assert api.is_command_completed('AGV-001', 1)

    def test_action_not_completed_when_fatal_error(self, api):
        """FATAL 에러가 있으면 action FINISHED여도 완료 처리하지 않고 대기."""
        action_id = 'pick_1_abc'
        api._cmd_order_map['AGV-001'] = {1: action_id}

        action_state = MagicMock()
        action_state.action_id = action_id
        action_state.action_status = ActionStatus.FINISHED

        state = MagicMock()
        state.order_id = ''
        state.node_states = []
        state.driving = False
        state.action_states = [action_state]
        state.has_fatal_error = True
        api._state_cache['AGV-001'] = state

        assert not api.is_command_completed('AGV-001', 1)


class TestOnStateMessage:
    """_on_state_message() 테스트."""

    def test_state_message_updates_cache(self, api):
        """State 메시지 수신 시 캐시가 업데이트된다."""
        state_json = json.dumps({
            'headerId': 1,
            'timestamp': '2026-01-01T00:00:00.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'orderId': 'order-001',
            'orderUpdateId': 0,
            'lastNodeId': 'wp1',
            'lastNodeSequenceId': 0,
            'driving': True,
            'operatingMode': 'AUTOMATIC',
            'nodeStates': [],
            'edgeStates': [],
            'actionStates': [],
            'errors': [],
            'safetyState': {'eStop': 'NONE', 'fieldViolation': False},
            'batteryState': {'batteryCharge': 80.0, 'charging': False},
            'agvPosition': {
                'x': 1.0, 'y': 2.0, 'theta': 0.5,
                'mapId': 'map1', 'positionInitialized': True,
            },
        })

        api._on_state_message('AGV-001', state_json.encode('utf-8'))

        assert 'AGV-001' in api._state_cache
        cached = api._state_cache['AGV-001']
        assert cached.order_id == 'order-001'
        assert cached.driving is True


class TestConnectionState:
    """Connection 메시지 캐시 테스트."""

    def test_connection_message_updates_cache(self, api):
        """Connection 메시지 수신 시 캐시가 업데이트된다."""
        conn_json = json.dumps({
            'headerId': 1,
            'timestamp': '2026-01-01T00:00:00.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'connectionState': 'ONLINE',
        })

        api._on_connection_message(
            'AGV-001', conn_json.encode('utf-8')
        )

        assert api._connection_cache['AGV-001'] == ConnectionState.ONLINE

    def test_connection_cache_returns_latest_state(self, api):
        """여러 상태 변경 시 마지막 상태를 반환한다."""
        for state_val in ['ONLINE', 'CONNECTIONBROKEN', 'OFFLINE']:
            conn_json = json.dumps({
                'headerId': 1,
                'timestamp': '2026-01-01T00:00:00.000Z',
                'version': '2.0.0',
                'manufacturer': 'TestCo',
                'serialNumber': 'AGV-001',
                'connectionState': state_val,
            })
            api._on_connection_message(
                'AGV-001', conn_json.encode('utf-8')
            )

        assert api._connection_cache['AGV-001'] == ConnectionState.OFFLINE


class TestConnectionCheck:
    """명령 전송 전 연결 확인 테스트."""

    def test_navigate_retries_when_robot_offline(self, api, mock_mqtt):
        """OFFLINE 로봇에 navigate 시 RETRY를 반환한다."""
        api._connection_cache['AGV-001'] = ConnectionState.OFFLINE
        result = api.navigate('AGV-001', 1, [], [], 'map1')
        assert result == RobotAPIResult.RETRY
        mock_mqtt.publish.assert_not_called()

    def test_navigate_retries_when_robot_connectionbroken(
        self, api, mock_mqtt
    ):
        """CONNECTIONBROKEN 시 RETRY를 반환한다."""
        api._connection_cache['AGV-001'] = ConnectionState.CONNECTIONBROKEN
        result = api.navigate('AGV-001', 1, [], [], 'map1')
        assert result == RobotAPIResult.RETRY
        mock_mqtt.publish.assert_not_called()

    def test_navigate_succeeds_when_robot_online(self, api, mock_mqtt):
        """ONLINE 로봇에 navigate가 성공한다."""
        api._connection_cache['AGV-001'] = ConnectionState.ONLINE
        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
        ]
        result = api.navigate('AGV-001', 1, nodes, [], 'map1')
        assert result == RobotAPIResult.SUCCESS

    def test_navigate_succeeds_when_no_connection_state(
        self, api, mock_mqtt
    ):
        """연결 상태 미수신 시 명령을 허용한다."""
        result = api.navigate(
            'AGV-001', 1,
            [Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            )],
            [], 'map1',
        )
        assert result == RobotAPIResult.SUCCESS

    def test_stop_retries_when_robot_offline(self, api, mock_mqtt):
        """OFFLINE 로봇에 stop 시 RETRY를 반환한다."""
        api._connection_cache['AGV-001'] = ConnectionState.OFFLINE
        result = api.stop('AGV-001', 1)
        assert result == RobotAPIResult.RETRY
        mock_mqtt.publish.assert_not_called()

    def test_start_activity_retries_when_robot_offline(
        self, api, mock_mqtt
    ):
        """OFFLINE 로봇에 activity 시 RETRY를 반환한다."""
        api._connection_cache['AGV-001'] = ConnectionState.OFFLINE
        result = api.start_activity(
            'AGV-001', 1, 'charge', {'station': 'cs1'}
        )
        assert result == RobotAPIResult.RETRY
        mock_mqtt.publish.assert_not_called()


class TestSubscribeRobot:
    """subscribe_robot() 테스트."""

    def test_subscribes_state_and_connection(self, api, mock_mqtt):
        """로봇 구독 시 state와 connection 토픽을 구독한다."""
        api.subscribe_robot('AGV-001')

        assert mock_mqtt.subscribe.call_count == 2
        topics = [c[0][0] for c in mock_mqtt.subscribe.call_args_list]
        assert 'uagv/v2/TestCo/AGV-001/state' in topics
        assert 'uagv/v2/TestCo/AGV-001/connection' in topics

    def test_connection_subscribes_with_qos_1(self, api, mock_mqtt):
        """Connection 토픽이 QoS=1로 구독된다."""
        api.subscribe_robot('AGV-001')

        for call in mock_mqtt.subscribe.call_args_list:
            topic = call[0][0]
            if topic.endswith('/connection'):
                assert call[1]['qos'] == 1
                break
        else:
            pytest.fail('connection topic subscription not found')


class TestBuildTopic:
    """_build_topic() 테스트."""

    def test_build_topic_format(self, api):
        """토픽 형식이 올바르다."""
        topic = api._build_topic('AGV-001', 'order')
        assert topic == 'uagv/v2/TestCo/AGV-001/order'

    def test_build_topic_state(self, api):
        """State 토픽 형식이 올바르다."""
        topic = api._build_topic('AGV-001', 'state')
        assert topic == 'uagv/v2/TestCo/AGV-001/state'


def _make_agv_state(
    operating_mode: OperatingMode = OperatingMode.AUTOMATIC,
    errors: list[AgvError] | None = None,
    e_stop: EStopType = EStopType.NONE,
) -> AgvState:
    """최소 AgvState를 생성한다."""
    return AgvState(
        header=Header(
            version='2.0.0',
            manufacturer='TestCo',
            serial_number='AGV-001',
        ),
        operating_mode=operating_mode,
        errors=errors or [],
        safety_state=SafetyState(e_stop=e_stop),
    )


class TestGetCommissionState:
    """get_commission_state() 테스트."""

    def test_returns_none_without_state(self, api):
        """상태 미수신 시 None을 반환한다."""
        assert api.get_commission_state('AGV-001') is None

    def test_commissioned_when_automatic_and_online(self, api):
        """AUTOMATIC + ONLINE → 전체 commission."""
        api._state_cache['AGV-001'] = _make_agv_state()
        api._connection_cache['AGV-001'] = ConnectionState.ONLINE

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(True, True, True)

    def test_commissioned_when_no_connection_received(self, api):
        """Connection 미수신 시 정상 간주."""
        api._state_cache['AGV-001'] = _make_agv_state()

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(True, True, True)

    def test_decommissioned_when_offline(self, api):
        """OFFLINE → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state()
        api._connection_cache['AGV-001'] = ConnectionState.OFFLINE

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)

    def test_decommissioned_when_connectionbroken(self, api):
        """CONNECTIONBROKEN → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state()
        api._connection_cache['AGV-001'] = ConnectionState.CONNECTIONBROKEN

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)

    def test_decommissioned_when_manual_mode(self, api):
        """MANUAL → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state(
            operating_mode=OperatingMode.MANUAL,
        )

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)

    def test_decommissioned_when_service_mode(self, api):
        """SERVICE → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state(
            operating_mode=OperatingMode.SERVICE,
        )

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)

    def test_decommissioned_when_teachin_mode(self, api):
        """TEACHIN → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state(
            operating_mode=OperatingMode.TEACHIN,
        )

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)

    def test_decommissioned_when_fatal_error(self, api):
        """FATAL error → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state(
            errors=[AgvError(
                error_type='hw_fail',
                error_level=ErrorLevel.FATAL,
            )],
        )

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)

    def test_decommissioned_when_estop(self, api):
        """Emergency stop active → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state(
            e_stop=EStopType.MANUAL,
        )

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)

    def test_partial_when_semiautomatic(self, api):
        """SEMIAUTOMATIC → dispatch만 false."""
        api._state_cache['AGV-001'] = _make_agv_state(
            operating_mode=OperatingMode.SEMIAUTOMATIC,
        )

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, True, True)

    def test_decommission_overrides_semiautomatic_with_fatal(self, api):
        """SEMIAUTOMATIC + FATAL → 전체 decommission."""
        api._state_cache['AGV-001'] = _make_agv_state(
            operating_mode=OperatingMode.SEMIAUTOMATIC,
            errors=[AgvError(
                error_type='hw_fail',
                error_level=ErrorLevel.FATAL,
            )],
        )

        result = api.get_commission_state('AGV-001')

        assert result == CommissionState(False, False, False)


@pytest.fixture
def api_with_download_map(mock_mqtt):
    """Vda5050RobotAPI with downloadMap config."""
    return Vda5050RobotAPI(
        mqtt_client=mock_mqtt,
        prefix='uagv/v2/TestCo',
        manufacturer='TestCo',
        download_map_config={
            'map_id': 'L1',
            'map_download_url': 'http://example.com/map.tar.gz',
            'map_version': '2.4.1',
        },
    )


class TestDownloadMap:
    """DownloadMap 기능 테스트."""

    def test_no_config_means_always_ready(self, api):
        """download_map config가 없으면 항상 ready."""
        assert api.is_download_map_ready('AGV-001') is True

    def test_not_ready_before_send(self, api_with_download_map):
        """Before sending downloadMap, ready is False."""
        assert (
            api_with_download_map.is_download_map_ready('AGV-001')
            is False
        )

    def test_send_on_online_transition(
        self, api_with_download_map, mock_mqtt
    ):
        """ONLINE 전환 시 downloadMap instantAction을 전송한다."""
        conn_json = json.dumps({
            'headerId': 1,
            'timestamp': '2026-01-01T00:00:00.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'connectionState': 'ONLINE',
        })
        api_with_download_map._on_connection_message(
            'AGV-001', conn_json.encode('utf-8')
        )

        mock_mqtt.publish.assert_called_once()
        topic = mock_mqtt.publish.call_args[0][0]
        assert topic == 'uagv/v2/TestCo/AGV-001/instantActions'
        payload = mock_mqtt.publish.call_args[0][1]
        data = json.loads(payload)
        assert data['actions'][0]['actionType'] == 'downloadMap'
        params = data['actions'][0]['actionParameters']
        param_keys = {p['key']: p['value'] for p in params}
        assert param_keys['mapId'] == 'L1'
        assert param_keys['mapDownloadUrl'] == (
            'http://example.com/map.tar.gz'
        )
        assert param_keys['mapVersion'] == '2.4.1'

    def test_no_send_when_already_online(
        self, api_with_download_map, mock_mqtt
    ):
        """이미 ONLINE 상태에서 ONLINE 수신 시 재전송하지 않는다."""
        api_with_download_map._connection_cache['AGV-001'] = (
            ConnectionState.ONLINE
        )
        conn_json = json.dumps({
            'headerId': 2,
            'timestamp': '2026-01-01T00:00:01.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'connectionState': 'ONLINE',
        })
        api_with_download_map._on_connection_message(
            'AGV-001', conn_json.encode('utf-8')
        )

        mock_mqtt.publish.assert_not_called()

    def test_resend_on_reconnection(
        self, api_with_download_map, mock_mqtt
    ):
        """OFFLINE → ONLINE 재연결 시 downloadMap을 재전송한다."""
        # 첫 번째 ONLINE 전환
        conn_online = json.dumps({
            'headerId': 1,
            'timestamp': '2026-01-01T00:00:00.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'connectionState': 'ONLINE',
        })
        api_with_download_map._on_connection_message(
            'AGV-001', conn_online.encode('utf-8')
        )
        first_action_id = (
            api_with_download_map._download_map_pending['AGV-001']
        )

        # OFFLINE 전환
        conn_offline = json.dumps({
            'headerId': 2,
            'timestamp': '2026-01-01T00:00:01.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'connectionState': 'OFFLINE',
        })
        api_with_download_map._on_connection_message(
            'AGV-001', conn_offline.encode('utf-8')
        )

        # 재연결 ONLINE
        conn_online2 = json.dumps({
            'headerId': 3,
            'timestamp': '2026-01-01T00:00:02.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'connectionState': 'ONLINE',
        })
        api_with_download_map._on_connection_message(
            'AGV-001', conn_online2.encode('utf-8')
        )

        assert mock_mqtt.publish.call_count == 2
        second_action_id = (
            api_with_download_map._download_map_pending['AGV-001']
        )
        assert first_action_id != second_action_id

    def test_ready_when_action_finished(self, api_with_download_map):
        """action_status가 FINISHED이면 ready."""
        api_with_download_map._download_map_pending['AGV-001'] = (
            'downloadMap_abc'
        )

        action_state = MagicMock()
        action_state.action_id = 'downloadMap_abc'
        action_state.action_status = ActionStatus.FINISHED

        state = MagicMock()
        state.action_states = [action_state]
        api_with_download_map._state_cache['AGV-001'] = state

        assert (
            api_with_download_map.is_download_map_ready('AGV-001')
            is True
        )

    def test_ready_when_action_failed(self, api_with_download_map):
        """action_status가 FAILED이면 ready (실패해도 진행)."""
        api_with_download_map._download_map_pending['AGV-001'] = (
            'downloadMap_abc'
        )

        action_state = MagicMock()
        action_state.action_id = 'downloadMap_abc'
        action_state.action_status = ActionStatus.FAILED

        state = MagicMock()
        state.action_states = [action_state]
        api_with_download_map._state_cache['AGV-001'] = state

        assert (
            api_with_download_map.is_download_map_ready('AGV-001')
            is True
        )

    def test_not_ready_when_action_running(self, api_with_download_map):
        """action_status가 RUNNING이면 아직 ready가 아니다."""
        api_with_download_map._download_map_pending['AGV-001'] = (
            'downloadMap_abc'
        )

        action_state = MagicMock()
        action_state.action_id = 'downloadMap_abc'
        action_state.action_status = ActionStatus.RUNNING

        state = MagicMock()
        state.action_states = [action_state]
        api_with_download_map._state_cache['AGV-001'] = state

        assert (
            api_with_download_map.is_download_map_ready('AGV-001')
            is False
        )

    def test_navigate_retries_when_map_not_ready(
        self, api_with_download_map, mock_mqtt
    ):
        """Navigate returns RETRY when downloadMap not ready."""
        api_with_download_map._download_map_pending['AGV-001'] = (
            'downloadMap_abc'
        )

        action_state = MagicMock()
        action_state.action_id = 'downloadMap_abc'
        action_state.action_status = ActionStatus.RUNNING

        state = MagicMock()
        state.action_states = [action_state]
        api_with_download_map._state_cache['AGV-001'] = state

        nodes = [
            Node(
                node_id='wp1', sequence_id=0, released=True,
                node_position=NodePosition(x=0.0, y=0.0, map_id='map1'),
            ),
        ]
        result = api_with_download_map.navigate(
            'AGV-001', 1, nodes, [], 'map1'
        )
        assert result == RobotAPIResult.RETRY

    def test_no_config_no_send(self, api, mock_mqtt):
        """Config 없으면 ONLINE 전환해도 downloadMap을 전송하지 않는다."""
        conn_json = json.dumps({
            'headerId': 1,
            'timestamp': '2026-01-01T00:00:00.000Z',
            'version': '2.0.0',
            'manufacturer': 'TestCo',
            'serialNumber': 'AGV-001',
            'connectionState': 'ONLINE',
        })
        api._on_connection_message(
            'AGV-001', conn_json.encode('utf-8')
        )

        mock_mqtt.publish.assert_not_called()
