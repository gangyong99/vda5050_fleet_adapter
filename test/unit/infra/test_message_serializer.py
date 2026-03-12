"""메시지 직렬화/역직렬화 단위 테스트."""

import json

import pytest

from vda5050_fleet_adapter.domain.entities.action import (
    Action,
    ActionParameter,
)
from vda5050_fleet_adapter.domain.entities.connection import Connection
from vda5050_fleet_adapter.domain.entities.edge import Edge
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.node import Node
from vda5050_fleet_adapter.domain.entities.order import Order
from vda5050_fleet_adapter.domain.enums import (
    ActionStatus,
    BlockingType,
    ConnectionState,
    ErrorLevel,
    EStopType,
    MapStatus,
    OperatingMode,
)
from vda5050_fleet_adapter.domain.value_objects.physical import Corridor
from vda5050_fleet_adapter.infra.mqtt.message_serializer import (
    _camel_to_snake,
    _snake_to_camel,
    deserialize_connection,
    deserialize_order,
    deserialize_state,
    serialize_connection,
    serialize_instant_actions,
    serialize_order,
)


class TestCaseConversion:
    @pytest.mark.parametrize(
        'snake, camel',
        [
            ('order_id', 'orderId'),
            ('node_position', 'nodePosition'),
            ('max_speed', 'maxSpeed'),
            ('allowed_deviation_xy', 'allowedDeviationXY'),
            ('e_stop', 'eStop'),
            ('vx', 'vx'),
        ],
    )
    def test_snake_to_camel(self, snake, camel):
        assert _snake_to_camel(snake) == camel

    @pytest.mark.parametrize(
        'camel, snake',
        [
            ('orderId', 'order_id'),
            ('nodePosition', 'node_position'),
            ('eStop', 'e_stop'),
        ],
    )
    def test_camel_to_snake(self, camel, snake):
        assert _camel_to_snake(camel) == snake


class TestOrderSerialization:
    def test_roundtrip(self, sample_order):
        json_str = serialize_order(sample_order)
        parsed = json.loads(json_str)

        assert parsed['orderId'] == 'order-001'
        assert parsed['orderUpdateId'] == 0
        assert len(parsed['nodes']) == 3
        assert len(parsed['edges']) == 2

        result = deserialize_order(json_str)
        assert result.order_id == sample_order.order_id
        assert len(result.nodes) == len(sample_order.nodes)
        assert len(result.edges) == len(sample_order.edges)

    def test_camel_case_keys_in_json(self, sample_order):
        json_str = serialize_order(sample_order)
        parsed = json.loads(json_str)

        assert 'nodeId' in json.dumps(parsed['nodes'][0])
        assert 'sequenceId' in json.dumps(parsed['nodes'][0])
        assert 'edgeId' in json.dumps(parsed['edges'][0])

    def test_node_position_serialized(self, sample_order):
        json_str = serialize_order(sample_order)
        parsed = json.loads(json_str)

        pos = parsed['nodes'][0]['nodePosition']
        assert pos['x'] == 1.0
        assert pos['y'] == 2.0
        assert pos['mapId'] == 'map1'

    def test_none_fields_omitted(self):
        header = Header(
            version='2.0.0', manufacturer='T', serial_number='A1',
        )
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[Node(node_id='n0', sequence_id=0, released=True)],
        )
        json_str = serialize_order(order)
        parsed = json.loads(json_str)

        node = parsed['nodes'][0]
        assert 'nodePosition' not in node

    def test_actions_in_nodes(self):
        header = Header(
            version='2.0.0', manufacturer='T', serial_number='A1',
        )
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[
                Node(
                    node_id='n0', sequence_id=0, released=True,
                    actions=[
                        Action(
                            action_type='pick', action_id='a1',
                            blocking_type=BlockingType.HARD,
                            action_parameters=[
                                ActionParameter(key='type', value='EPAL'),
                            ],
                        ),
                    ],
                ),
            ],
        )
        json_str = serialize_order(order)
        result = deserialize_order(json_str)

        assert len(result.nodes[0].actions) == 1
        assert result.nodes[0].actions[0].action_type == 'pick'
        assert result.nodes[0].actions[0].action_parameters[0].value == 'EPAL'

    def test_edge_with_corridor(self):
        header = Header(
            version='2.0.0', manufacturer='T', serial_number='A1',
        )
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[
                Node(node_id='n0', sequence_id=0, released=True),
                Node(node_id='n2', sequence_id=2, released=True),
            ],
            edges=[
                Edge(
                    edge_id='e1', sequence_id=1, released=True,
                    start_node_id='n0', end_node_id='n2',
                    corridor=Corridor(left_width=1.0, right_width=0.5),
                ),
            ],
        )
        json_str = serialize_order(order)
        result = deserialize_order(json_str)

        assert result.edges[0].corridor is not None
        assert result.edges[0].corridor.left_width == 1.0
        assert result.edges[0].corridor.right_width == 0.5


class TestStateSerialization:
    def test_full_state_deserialization(self):
        data = {
            'headerId': 1, 'timestamp': '2024-01-15T10:00:00.000Z',
            'version': '2.0.0', 'manufacturer': 'T', 'serialNumber': 'A1',
            'orderId': 'o1', 'orderUpdateId': 0,
            'lastNodeId': 'n0', 'lastNodeSequenceId': 0,
            'driving': True, 'newBaseRequest': False,
            'distanceSinceLastNode': 1.5,
            'operatingMode': 'AUTOMATIC', 'paused': False,
            'nodeStates': [
                {'nodeId': 'n2', 'sequenceId': 2, 'released': True},
            ],
            'edgeStates': [
                {'edgeId': 'e1', 'sequenceId': 1, 'released': True},
            ],
            'actionStates': [
                {'actionId': 'a1', 'actionType': 'pick',
                 'actionStatus': 'RUNNING'},
            ],
            'agvPosition': {
                'x': 1.0, 'y': 2.0, 'theta': 0.5, 'mapId': 'm1',
                'positionInitialized': True, 'localizationScore': 0.9,
            },
            'velocity': {'vx': 1.0, 'vy': 0.0, 'omega': 0.1},
            'loads': [
                {'loadId': 'L1', 'loadType': 'EPAL', 'weight': 500},
            ],
            'batteryState': {
                'batteryCharge': 75.0, 'charging': True,
                'batteryVoltage': 48.0,
            },
            'errors': [
                {'errorType': 'driveError', 'errorLevel': 'WARNING',
                 'errorDescription': 'motor overheat',
                 'errorReferences': [
                     {'referenceKey': 'nodeId', 'referenceValue': 'n0'},
                 ]},
            ],
            'information': [
                {'infoType': 'general', 'infoLevel': 'INFO',
                 'infoDescription': 'ok'},
            ],
            'safetyState': {'eStop': 'NONE', 'fieldViolation': False},
            'maps': [
                {'mapId': 'm1', 'mapVersion': '1.0',
                 'mapStatus': 'ENABLED'},
            ],
        }
        state = deserialize_state(json.dumps(data))

        assert state.order_id == 'o1'
        assert state.driving is True
        assert state.distance_since_last_node == 1.5
        assert state.operating_mode == OperatingMode.AUTOMATIC
        assert state.agv_position.x == 1.0
        assert state.agv_position.localization_score == 0.9
        assert state.velocity.omega == 0.1
        assert len(state.node_states) == 1
        assert len(state.edge_states) == 1
        assert state.action_states[0].action_status == ActionStatus.RUNNING
        assert state.loads[0].weight == 500
        assert state.battery_state.charging is True
        assert state.battery_state.battery_voltage == 48.0
        assert state.errors[0].error_level == ErrorLevel.WARNING
        assert len(state.errors[0].error_references) == 1
        assert state.safety_state.e_stop == EStopType.NONE
        assert state.maps[0].map_status == MapStatus.ENABLED

    def test_minimal_state(self):
        data = {
            'headerId': 1, 'timestamp': '2024-01-15T10:00:00.000Z',
            'version': '2.0.0', 'manufacturer': 'T', 'serialNumber': 'A1',
        }
        state = deserialize_state(json.dumps(data))
        assert state.order_id == ''
        assert state.agv_position is None
        assert state.battery_state is None
        assert len(state.errors) == 0


class TestConnectionSerialization:
    def test_roundtrip(self, sample_header):
        conn = Connection(
            header=sample_header,
            connection_state=ConnectionState.ONLINE,
        )
        json_str = serialize_connection(conn)
        result = deserialize_connection(json_str)

        assert result.connection_state == ConnectionState.ONLINE
        assert result.header.manufacturer == 'TestCo'

    @pytest.mark.parametrize(
        'state',
        [ConnectionState.ONLINE, ConnectionState.OFFLINE,
         ConnectionState.CONNECTIONBROKEN],
    )
    def test_all_connection_states(self, sample_header, state):
        conn = Connection(header=sample_header, connection_state=state)
        json_str = serialize_connection(conn)
        result = deserialize_connection(json_str)
        assert result.connection_state == state


class TestInstantActionsSerialization:
    def test_serialize(self, sample_header):
        actions = [
            Action(
                action_type='startPause', action_id='p1',
                blocking_type=BlockingType.HARD,
            ),
        ]
        json_str = serialize_instant_actions(sample_header, actions)
        parsed = json.loads(json_str)

        assert 'actions' in parsed
        assert parsed['actions'][0]['actionType'] == 'startPause'
        assert parsed['actions'][0]['blockingType'] == 'HARD'
