"""VDA5050 AGV 상태 엔티티 (State 메시지의 도메인 모델)."""

from dataclasses import dataclass, field

from vda5050_fleet_adapter.domain.entities.action import ActionState
from vda5050_fleet_adapter.domain.entities.battery import BatteryState
from vda5050_fleet_adapter.domain.entities.edge import EdgeState
from vda5050_fleet_adapter.domain.entities.error import AgvError, AgvInformation
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.load import Load
from vda5050_fleet_adapter.domain.entities.map_state import AgvMap
from vda5050_fleet_adapter.domain.entities.node import NodeState
from vda5050_fleet_adapter.domain.entities.safety import SafetyState
from vda5050_fleet_adapter.domain.enums import OperatingMode
from vda5050_fleet_adapter.domain.value_objects.position import (
    AgvPosition,
    Velocity,
)


@dataclass
class AgvState:
    """VDA5050 AGV 전체 상태.

    AGV → Master로 전송되는 State 메시지의 도메인 모델이다.
    상태 변경 시 또는 최대 30초 간격으로 발행한다.

    Args:
        header: 공통 메시지 헤더.
        order_id: 현재 실행 중인 주문 ID (없으면 빈 문자열).
        order_update_id: 현재 주문 업데이트 번호.
        last_node_id: 마지막 통과/현재 위치 노드 ID.
        last_node_sequence_id: 마지막 노드의 시퀀스 ID.
        driving: 주행 중 여부.
        new_base_request: 새 Base 요청 여부.
        distance_since_last_node: 마지막 노드 이후 이동 거리 (m).
        operating_mode: AGV 운영 모드.
        paused: 일시 정지 여부.
        node_states: 남은 노드 상태 목록.
        edge_states: 남은 엣지 상태 목록.
        action_states: 액션 실행 상태 목록.
        agv_position: AGV 현재 위치.
        velocity: AGV 현재 속도.
        loads: 적재 화물 목록.
        battery_state: 배터리 상태.
        errors: 에러 목록.
        information: 정보 목록.
        safety_state: 안전 상태.
        maps: 로드된 맵 목록.
    """

    header: Header
    order_id: str = ''
    order_update_id: int = 0
    last_node_id: str = ''
    last_node_sequence_id: int = 0
    driving: bool = False
    new_base_request: bool = False
    distance_since_last_node: float | None = None
    operating_mode: OperatingMode = OperatingMode.AUTOMATIC
    paused: bool = False

    node_states: list[NodeState] = field(default_factory=list)
    edge_states: list[EdgeState] = field(default_factory=list)
    action_states: list[ActionState] = field(default_factory=list)

    agv_position: AgvPosition | None = None
    velocity: Velocity | None = None
    loads: list[Load] = field(default_factory=list)
    battery_state: BatteryState | None = None

    errors: list[AgvError] = field(default_factory=list)
    information: list[AgvInformation] = field(default_factory=list)
    safety_state: SafetyState = field(default_factory=SafetyState)
    maps: list[AgvMap] = field(default_factory=list)

    @property
    def has_active_order(self) -> bool:
        """현재 실행 중인 주문이 있는지 여부."""
        return bool(self.order_id)

    @property
    def has_errors(self) -> bool:
        """에러가 존재하는지 여부."""
        return len(self.errors) > 0

    @property
    def has_fatal_error(self) -> bool:
        """FATAL 레벨 에러가 존재하는지 여부."""
        from vda5050_fleet_adapter.domain.enums import ErrorLevel
        return any(e.error_level == ErrorLevel.FATAL for e in self.errors)

    @property
    def is_emergency_stopped(self) -> bool:
        """비상 정지 상태인지 여부."""
        from vda5050_fleet_adapter.domain.enums import EStopType
        return self.safety_state.e_stop != EStopType.NONE

    def get_action_state(self, action_id: str) -> ActionState | None:
        """특정 액션의 실행 상태를 조회한다.

        Args:
            action_id: 조회할 액션 ID.

        Returns:
            해당 ActionState 또는 None.
        """
        for action_state in self.action_states:
            if action_state.action_id == action_id:
                return action_state
        return None
