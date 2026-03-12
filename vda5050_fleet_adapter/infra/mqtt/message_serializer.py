"""VDA5050 메시지 JSON 직렬화/역직렬화.

도메인 엔티티 ↔ VDA5050 JSON (camelCase) 변환을 담당한다.
snake_case(도메인) ↔ camelCase(VDA5050 프로토콜) 변환은
이 모듈에서만 처리한다.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
import re
from typing import Any

from vda5050_fleet_adapter.domain.entities.action import (
    Action,
    ActionParameter,
    ActionState,
)
from vda5050_fleet_adapter.domain.entities.agv_state import AgvState
from vda5050_fleet_adapter.domain.entities.battery import BatteryState
from vda5050_fleet_adapter.domain.entities.connection import Connection
from vda5050_fleet_adapter.domain.entities.edge import Edge, EdgeState
from vda5050_fleet_adapter.domain.entities.error import (
    AgvError,
    AgvInformation,
    ErrorReference,
)
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.load import Load
from vda5050_fleet_adapter.domain.entities.map_state import AgvMap
from vda5050_fleet_adapter.domain.entities.node import Node, NodeState
from vda5050_fleet_adapter.domain.entities.order import Order
from vda5050_fleet_adapter.domain.entities.safety import SafetyState
from vda5050_fleet_adapter.domain.enums import (
    ActionStatus,
    BlockingType,
    ConnectionState,
    CorridorRefPoint,
    ErrorLevel,
    EStopType,
    InfoLevel,
    MapStatus,
    OperatingMode,
)
from vda5050_fleet_adapter.domain.value_objects.physical import (
    BoundingBoxReference,
    Corridor,
    LoadDimensions,
)
from vda5050_fleet_adapter.domain.value_objects.position import (
    AgvPosition,
    NodePosition,
    Velocity,
)
from vda5050_fleet_adapter.domain.value_objects.trajectory import (
    ControlPoint,
    Trajectory,
)


# -- snake_case ↔ camelCase 변환 --

_SNAKE_RE = re.compile(r'_([a-z])')
_CAMEL_RE = re.compile(r'([A-Z])')

# VDA5050에서 특별한 매핑이 필요한 필드
_SPECIAL_SNAKE_TO_CAMEL: dict[str, str] = {
    'e_stop': 'eStop',
    'vx': 'vx',
    'vy': 'vy',
    'allowed_deviation_xy': 'allowedDeviationXY',
}

_SPECIAL_CAMEL_TO_SNAKE: dict[str, str] = {
    v: k for k, v in _SPECIAL_SNAKE_TO_CAMEL.items()
}


def _snake_to_camel(name: str) -> str:
    """snake_case → camelCase 변환."""
    if name in _SPECIAL_SNAKE_TO_CAMEL:
        return _SPECIAL_SNAKE_TO_CAMEL[name]
    return _SNAKE_RE.sub(lambda m: m.group(1).upper(), name)


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    if name in _SPECIAL_CAMEL_TO_SNAKE:
        return _SPECIAL_CAMEL_TO_SNAKE[name]
    return _CAMEL_RE.sub(r'_\1', name).lower()


# -- 직렬화 (도메인 → JSON) --

def _serialize_value(value: Any) -> Any:
    """단일 값을 JSON 호환 타입으로 변환한다."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value)
    return value


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """dataclass를 camelCase JSON dict로 변환한다."""
    result: dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if value is None:
            continue
        camel_key = _snake_to_camel(f.name)
        result[camel_key] = _serialize_value(value)
    return result


def serialize_order(order: Order) -> str:
    """Order를 VDA5050 JSON 문자열로 직렬화한다."""
    data = _dataclass_to_dict(order.header)
    data['orderId'] = order.order_id
    data['orderUpdateId'] = order.order_update_id
    if order.zone_set_id:
        data['zoneSetId'] = order.zone_set_id
    data['nodes'] = [_dataclass_to_dict(n) for n in order.nodes]
    data['edges'] = [_dataclass_to_dict(e) for e in order.edges]
    return json.dumps(data, ensure_ascii=False)


def serialize_instant_actions(
    header: Header, actions: list[Action]
) -> str:
    """InstantActions를 VDA5050 JSON 문자열로 직렬화한다."""
    data = _dataclass_to_dict(header)
    data['actions'] = [_dataclass_to_dict(a) for a in actions]
    return json.dumps(data, ensure_ascii=False)


def serialize_connection(connection: Connection) -> str:
    """Connection을 VDA5050 JSON 문자열로 직렬화한다."""
    data = _dataclass_to_dict(connection.header)
    data['connectionState'] = connection.connection_state.value
    return json.dumps(data, ensure_ascii=False)


# -- 역직렬화 (JSON → 도메인) --

def _map_keys_to_snake(data: dict[str, Any]) -> dict[str, Any]:
    """dict의 키를 camelCase → snake_case로 변환한다."""
    return {_camel_to_snake(k): v for k, v in data.items()}


def _parse_header(data: dict[str, Any]) -> Header:
    """JSON dict에서 Header를 파싱한다."""
    return Header(
        header_id=data.get('headerId', 0),
        timestamp=datetime.fromisoformat(
            data['timestamp'].replace('Z', '+00:00')
        ) if 'timestamp' in data else datetime.now(),
        version=data.get('version', '2.0.0'),
        manufacturer=data.get('manufacturer', ''),
        serial_number=data.get('serialNumber', ''),
    )


def _parse_action_parameter(data: dict[str, Any]) -> ActionParameter:
    return ActionParameter(key=data['key'], value=data['value'])


def _parse_action(data: dict[str, Any]) -> Action:
    return Action(
        action_type=data['actionType'],
        action_id=data['actionId'],
        blocking_type=BlockingType(data['blockingType']),
        action_description=data.get('actionDescription', ''),
        action_parameters=[
            _parse_action_parameter(p)
            for p in data.get('actionParameters', [])
        ],
    )


def _parse_node_position(data: dict[str, Any]) -> NodePosition:
    return NodePosition(
        x=data['x'],
        y=data['y'],
        map_id=data['mapId'],
        theta=data.get('theta'),
        allowed_deviation_xy=data.get('allowedDeviationXY'),
        allowed_deviation_theta=data.get('allowedDeviationTheta'),
    )


def _parse_node(data: dict[str, Any]) -> Node:
    pos = None
    if 'nodePosition' in data and data['nodePosition'] is not None:
        pos = _parse_node_position(data['nodePosition'])
    return Node(
        node_id=data['nodeId'],
        sequence_id=data['sequenceId'],
        released=data['released'],
        node_position=pos,
        actions=[_parse_action(a) for a in data.get('actions', [])],
    )


def _parse_corridor(data: dict[str, Any]) -> Corridor:
    return Corridor(
        left_width=data['leftWidth'],
        right_width=data['rightWidth'],
        corridor_ref_point=CorridorRefPoint(
            data.get('corridorRefPoint', 'KINEMATICCENTER')
        ),
    )


def _parse_control_point(data: dict[str, Any]) -> ControlPoint:
    return ControlPoint(
        x=data['x'], y=data['y'], weight=data.get('weight', 1.0)
    )


def _parse_trajectory(data: dict[str, Any]) -> Trajectory:
    return Trajectory(
        degree=data['degree'],
        knot_vector=tuple(data.get('knotVector', [])),
        control_points=tuple(
            _parse_control_point(cp)
            for cp in data.get('controlPoints', [])
        ),
    )


def _parse_edge(data: dict[str, Any]) -> Edge:
    trajectory = None
    if 'trajectory' in data and data['trajectory'] is not None:
        trajectory = _parse_trajectory(data['trajectory'])
    corridor = None
    if 'corridor' in data and data['corridor'] is not None:
        corridor = _parse_corridor(data['corridor'])
    return Edge(
        edge_id=data['edgeId'],
        sequence_id=data['sequenceId'],
        released=data['released'],
        start_node_id=data['startNodeId'],
        end_node_id=data['endNodeId'],
        max_speed=data.get('maxSpeed'),
        orientation=data.get('orientation'),
        rotation_allowed=data.get('rotationAllowed'),
        trajectory=trajectory,
        corridor=corridor,
        actions=[_parse_action(a) for a in data.get('actions', [])],
    )


def deserialize_order(payload: str) -> Order:
    """VDA5050 JSON 문자열을 Order로 역직렬화한다."""
    data = json.loads(payload)
    return Order(
        header=_parse_header(data),
        order_id=data['orderId'],
        order_update_id=data['orderUpdateId'],
        zone_set_id=data.get('zoneSetId', ''),
        nodes=[_parse_node(n) for n in data.get('nodes', [])],
        edges=[_parse_edge(e) for e in data.get('edges', [])],
    )


def _parse_agv_position(data: dict[str, Any]) -> AgvPosition:
    return AgvPosition(
        x=data['x'],
        y=data['y'],
        theta=data['theta'],
        map_id=data['mapId'],
        position_initialized=data.get('positionInitialized', True),
        localization_score=data.get('localizationScore'),
    )


def _parse_velocity(data: dict[str, Any]) -> Velocity:
    return Velocity(
        vx=data.get('vx', 0.0),
        vy=data.get('vy', 0.0),
        omega=data.get('omega', 0.0),
    )


def _parse_node_state(data: dict[str, Any]) -> NodeState:
    pos = None
    if 'nodePosition' in data and data['nodePosition'] is not None:
        pos = _parse_node_position(data['nodePosition'])
    return NodeState(
        node_id=data['nodeId'],
        sequence_id=data['sequenceId'],
        released=data['released'],
        node_description=data.get('nodeDescription', ''),
        node_position=pos,
    )


def _parse_edge_state(data: dict[str, Any]) -> EdgeState:
    return EdgeState(
        edge_id=data['edgeId'],
        sequence_id=data['sequenceId'],
        released=data['released'],
        edge_description=data.get('edgeDescription', ''),
    )


def _parse_action_state(data: dict[str, Any]) -> ActionState:
    return ActionState(
        action_id=data['actionId'],
        action_type=data.get('actionType', ''),
        action_status=ActionStatus(data['actionStatus']),
        action_description=data.get('actionDescription', ''),
        result_description=data.get('resultDescription', ''),
    )


def _parse_error_reference(data: dict[str, Any]) -> ErrorReference:
    return ErrorReference(
        reference_key=data['referenceKey'],
        reference_value=data['referenceValue'],
    )


def _parse_agv_error(data: dict[str, Any]) -> AgvError:
    return AgvError(
        error_type=data['errorType'],
        error_level=ErrorLevel(data['errorLevel']),
        error_description=data.get('errorDescription', ''),
        error_hint=data.get('errorHint', ''),
        error_references=[
            _parse_error_reference(r)
            for r in data.get('errorReferences', [])
        ],
    )


def _parse_agv_information(data: dict[str, Any]) -> AgvInformation:
    return AgvInformation(
        info_type=data['infoType'],
        info_level=InfoLevel(data['infoLevel']),
        info_description=data.get('infoDescription', ''),
        info_references=[
            _parse_error_reference(r)
            for r in data.get('infoReferences', [])
        ],
    )


def _parse_bounding_box(data: dict[str, Any]) -> BoundingBoxReference:
    return BoundingBoxReference(
        x=data['x'], y=data['y'], z=data['z'],
        theta=data.get('theta', 0.0),
    )


def _parse_load_dimensions(data: dict[str, Any]) -> LoadDimensions:
    return LoadDimensions(
        length=data['length'],
        width=data['width'],
        height=data.get('height', 0.0),
    )


def _parse_load(data: dict[str, Any]) -> Load:
    bbox = None
    if 'boundingBoxReference' in data and data['boundingBoxReference']:
        bbox = _parse_bounding_box(data['boundingBoxReference'])
    dims = None
    if 'loadDimensions' in data and data['loadDimensions']:
        dims = _parse_load_dimensions(data['loadDimensions'])
    return Load(
        load_id=data.get('loadId', ''),
        load_type=data.get('loadType', ''),
        load_position=data.get('loadPosition', ''),
        bounding_box_reference=bbox,
        load_dimensions=dims,
        weight=data.get('weight'),
    )


def _parse_battery_state(data: dict[str, Any]) -> BatteryState:
    return BatteryState(
        battery_charge=data['batteryCharge'],
        charging=data.get('charging', False),
        battery_voltage=data.get('batteryVoltage'),
        battery_health=data.get('batteryHealth'),
        reach=data.get('reach'),
    )


def _parse_safety_state(data: dict[str, Any]) -> SafetyState:
    return SafetyState(
        e_stop=EStopType(data.get('eStop', 'NONE')),
        field_violation=data.get('fieldViolation', False),
    )


def _parse_agv_map(data: dict[str, Any]) -> AgvMap:
    return AgvMap(
        map_id=data['mapId'],
        map_version=data['mapVersion'],
        map_status=MapStatus(data.get('mapStatus', 'DISABLED')),
    )


def deserialize_state(payload: str) -> AgvState:
    """VDA5050 JSON 문자열을 AgvState로 역직렬화한다."""
    data = json.loads(payload)

    agv_pos = None
    if 'agvPosition' in data and data['agvPosition']:
        agv_pos = _parse_agv_position(data['agvPosition'])

    velocity = None
    if 'velocity' in data and data['velocity']:
        velocity = _parse_velocity(data['velocity'])

    battery = None
    if 'batteryState' in data and data['batteryState']:
        battery = _parse_battery_state(data['batteryState'])

    safety = SafetyState()
    if 'safetyState' in data and data['safetyState']:
        safety = _parse_safety_state(data['safetyState'])

    return AgvState(
        header=_parse_header(data),
        order_id=data.get('orderId', ''),
        order_update_id=data.get('orderUpdateId', 0),
        last_node_id=data.get('lastNodeId', ''),
        last_node_sequence_id=data.get('lastNodeSequenceId', 0),
        driving=data.get('driving', False),
        new_base_request=data.get('newBaseRequest', False),
        distance_since_last_node=data.get('distanceSinceLastNode'),
        operating_mode=OperatingMode(
            data.get('operatingMode', 'AUTOMATIC')
        ),
        paused=data.get('paused', False),
        node_states=[
            _parse_node_state(n) for n in data.get('nodeStates', [])
        ],
        edge_states=[
            _parse_edge_state(e) for e in data.get('edgeStates', [])
        ],
        action_states=[
            _parse_action_state(a) for a in data.get('actionStates', [])
        ],
        agv_position=agv_pos,
        velocity=velocity,
        loads=[_parse_load(ld) for ld in data.get('loads', [])],
        battery_state=battery,
        errors=[_parse_agv_error(e) for e in data.get('errors', [])],
        information=[
            _parse_agv_information(i) for i in data.get('information', [])
        ],
        safety_state=safety,
        maps=[_parse_agv_map(m) for m in data.get('maps', [])],
    )


def deserialize_connection(payload: str) -> Connection:
    """VDA5050 JSON 문자열을 Connection으로 역직렬화한다."""
    data = json.loads(payload)
    return Connection(
        header=_parse_header(data),
        connection_state=ConnectionState(data['connectionState']),
    )
