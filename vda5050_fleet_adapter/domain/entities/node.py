"""VDA5050 노드 엔티티."""

from dataclasses import dataclass, field

from vda5050_fleet_adapter.domain.entities.action import Action
from vda5050_fleet_adapter.domain.value_objects.position import NodePosition


@dataclass
class Node:
    """Order 내 그래프 노드.

    Args:
        node_id: 노드 고유 ID.
        sequence_id: 그래프 내 순서 (짝수: 0, 2, 4...).
        released: Base(True) 또는 Horizon(False).
        node_position: 노드 위치 (첫 주문 시 필수).
        actions: 노드 도착 시 실행할 액션 목록.
    """

    node_id: str
    sequence_id: int
    released: bool
    node_position: NodePosition | None = None
    actions: list[Action] = field(default_factory=list)


@dataclass
class NodeState:
    """State 메시지 내 남은 노드 상태.

    Args:
        node_id: 노드 고유 ID.
        sequence_id: 그래프 내 순서.
        released: Base 여부.
        node_description: 노드 설명.
        node_position: 노드 위치.
    """

    node_id: str
    sequence_id: int
    released: bool
    node_description: str = ''
    node_position: NodePosition | None = None
