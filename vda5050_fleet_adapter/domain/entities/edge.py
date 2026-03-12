"""VDA5050 엣지 엔티티."""

from dataclasses import dataclass, field

from vda5050_fleet_adapter.domain.entities.action import Action
from vda5050_fleet_adapter.domain.value_objects.physical import Corridor
from vda5050_fleet_adapter.domain.value_objects.trajectory import Trajectory


@dataclass
class Edge:
    """Order 내 그래프 엣지 (노드 간 경로).

    Args:
        edge_id: 엣지 고유 ID.
        sequence_id: 그래프 내 순서 (홀수: 1, 3, 5...).
        released: Base(True) 또는 Horizon(False).
        start_node_id: 시작 노드 ID.
        end_node_id: 종료 노드 ID.
        max_speed: 최대 속도 (m/s).
        orientation: 주행 방향 (rad).
        rotation_allowed: 회전 허용 여부.
        trajectory: NURBS 경로 정의.
        corridor: 장애물 회피 경계.
        actions: 엣지 주행 중 실행할 액션 목록.
    """

    edge_id: str
    sequence_id: int
    released: bool
    start_node_id: str
    end_node_id: str
    max_speed: float | None = None
    orientation: float | None = None
    rotation_allowed: bool | None = None
    trajectory: Trajectory | None = None
    corridor: Corridor | None = None
    actions: list[Action] = field(default_factory=list)


@dataclass
class EdgeState:
    """State 메시지 내 남은 엣지 상태.

    Args:
        edge_id: 엣지 고유 ID.
        sequence_id: 그래프 내 순서.
        released: Base 여부.
        edge_description: 엣지 설명.
    """

    edge_id: str
    sequence_id: int
    released: bool
    edge_description: str = ''
