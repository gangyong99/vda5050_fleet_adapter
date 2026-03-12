"""공통 테스트 fixture."""

import pytest

from vda5050_fleet_adapter.domain.entities.action import ActionState
from vda5050_fleet_adapter.domain.entities.agv_state import AgvState
from vda5050_fleet_adapter.domain.entities.battery import BatteryState
from vda5050_fleet_adapter.domain.entities.edge import Edge
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.node import Node, NodeState
from vda5050_fleet_adapter.domain.entities.order import Order
from vda5050_fleet_adapter.domain.entities.safety import SafetyState
from vda5050_fleet_adapter.domain.enums import (
    ActionStatus,
    EStopType,
    OperatingMode,
)
from vda5050_fleet_adapter.domain.value_objects.position import (
    AgvPosition,
    NodePosition,
    Velocity,
)
from vda5050_fleet_adapter.usecase.ports.config_port import (
    FleetManagerConfig,
    MqttConfig,
)


@pytest.fixture
def sample_header():
    """VDA5050 메시지 헤더 샘플."""
    return Header(
        version='2.0.0',
        manufacturer='TestCo',
        serial_number='AGV-001',
    )


@pytest.fixture
def sample_node_position():
    """노드 위치 샘플."""
    return NodePosition(x=1.0, y=2.0, map_id='map1', theta=0.5)


@pytest.fixture
def sample_nodes(sample_node_position):
    """VDA5050 노드 목록 샘플."""
    return [
        Node(
            node_id='n0',
            sequence_id=0,
            released=True,
            node_position=sample_node_position,
        ),
        Node(
            node_id='n2',
            sequence_id=2,
            released=True,
            node_position=NodePosition(x=5.0, y=6.0, map_id='map1'),
        ),
        Node(
            node_id='n4',
            sequence_id=4,
            released=False,
            node_position=NodePosition(x=10.0, y=12.0, map_id='map1'),
        ),
    ]


@pytest.fixture
def sample_edges():
    """VDA5050 엣지 목록 샘플."""
    return [
        Edge(
            edge_id='e1',
            sequence_id=1,
            released=True,
            start_node_id='n0',
            end_node_id='n2',
            max_speed=2.0,
        ),
        Edge(
            edge_id='e3',
            sequence_id=3,
            released=False,
            start_node_id='n2',
            end_node_id='n4',
        ),
    ]


@pytest.fixture
def sample_order(sample_header, sample_nodes, sample_edges):
    """VDA5050 주문 샘플."""
    return Order(
        header=sample_header,
        order_id='order-001',
        order_update_id=0,
        nodes=sample_nodes,
        edges=sample_edges,
    )


@pytest.fixture
def sample_agv_position():
    """AGV 위치 샘플."""
    return AgvPosition(
        x=1.5, y=2.5, theta=0.3, map_id='map1',
        position_initialized=True, localization_score=0.95,
    )


@pytest.fixture
def sample_agv_state(sample_header, sample_agv_position):
    """AGV 상태 샘플."""
    return AgvState(
        header=sample_header,
        order_id='order-001',
        order_update_id=0,
        last_node_id='n0',
        last_node_sequence_id=0,
        driving=True,
        operating_mode=OperatingMode.AUTOMATIC,
        agv_position=sample_agv_position,
        velocity=Velocity(vx=1.0),
        battery_state=BatteryState(battery_charge=85.0, charging=False),
        safety_state=SafetyState(e_stop=EStopType.NONE),
        node_states=[
            NodeState(node_id='n2', sequence_id=2, released=True),
        ],
        action_states=[
            ActionState(
                action_id='a1',
                action_type='pick',
                action_status=ActionStatus.WAITING,
            ),
        ],
    )


@pytest.fixture
def sample_mqtt_config():
    """MQTT 설정 샘플."""
    return MqttConfig(broker_host='localhost', broker_port=1883)


@pytest.fixture
def sample_fleet_manager_config():
    """Fleet Manager 설정 샘플."""
    return FleetManagerConfig(
        ip='127.0.0.1',
        prefix='uagv/v2/TestCo',
        port=1883,
    )


@pytest.fixture
def sample_nav_nodes():
    """내비게이션 그래프 노드 샘플."""
    return {
        'wp1': {'x': 0.0, 'y': 0.0, 'attributes': {}},
        'wp2': {'x': 5.0, 'y': 0.0, 'attributes': {}},
        'wp3': {'x': 5.0, 'y': 5.0, 'attributes': {}},
        'wp4': {'x': 0.0, 'y': 5.0, 'attributes': {}},
    }


@pytest.fixture
def sample_nav_edges():
    """내비게이션 그래프 엣지 샘플."""
    return {
        'edge0': {'start': 'wp1', 'end': 'wp2', 'attributes': {}},
        'edge1': {'start': 'wp2', 'end': 'wp1', 'attributes': {}},
        'edge2': {'start': 'wp2', 'end': 'wp3', 'attributes': {}},
        'edge3': {'start': 'wp3', 'end': 'wp2', 'attributes': {}},
        'edge4': {'start': 'wp3', 'end': 'wp4', 'attributes': {}},
        'edge5': {'start': 'wp4', 'end': 'wp3', 'attributes': {}},
        'edge6': {'start': 'wp4', 'end': 'wp1', 'attributes': {}},
        'edge7': {'start': 'wp1', 'end': 'wp4', 'attributes': {}},
    }
