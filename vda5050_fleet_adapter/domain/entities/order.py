"""VDA5050 주문 엔티티."""

from dataclasses import dataclass, field

from vda5050_fleet_adapter.domain.entities.edge import Edge
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.node import Node
from vda5050_fleet_adapter.domain.exceptions import OrderValidationError


@dataclass
class Order:
    """VDA5050 주행 주문.

    방향 그래프(Node + Edge)로 AGV 경로를 정의한다.
    Base(released) 구간은 즉시 주행, Horizon 구간은 교통 제어용이다.

    Args:
        header: 공통 메시지 헤더.
        order_id: 주문 고유 ID.
        order_update_id: 주문 업데이트 번호 (증가).
        nodes: 노드 배열.
        edges: 엣지 배열.
        zone_set_id: 사용할 구역 세트 ID.
    """

    header: Header
    order_id: str
    order_update_id: int
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    zone_set_id: str = ''

    @property
    def base_nodes(self) -> list[Node]:
        """released=True인 Base 노드 목록."""
        return [n for n in self.nodes if n.released]

    @property
    def horizon_nodes(self) -> list[Node]:
        """released=False인 Horizon 노드 목록."""
        return [n for n in self.nodes if not n.released]

    @property
    def base_edges(self) -> list[Edge]:
        """released=True인 Base 엣지 목록."""
        return [e for e in self.edges if e.released]

    @property
    def horizon_edges(self) -> list[Edge]:
        """released=False인 Horizon 엣지 목록."""
        return [e for e in self.edges if not e.released]

    @property
    def last_base_node(self) -> Node | None:
        """Return the last node in the Base section (stitching node)."""
        base = self.base_nodes
        return base[-1] if base else None

    def validate(self) -> None:
        """주문 구조의 유효성을 검증한다.

        Raises:
            OrderValidationError: 유효성 검증 실패 시.
        """
        if not self.order_id:
            raise OrderValidationError('order_id가 비어있습니다.')

        if not self.nodes:
            raise OrderValidationError('노드가 비어있습니다.')

        self._validate_sequence_ids()
        self._validate_edge_connections()
        self._validate_release_consistency()

    def _validate_sequence_ids(self) -> None:
        """노드/엣지 시퀀스 ID 정합성 검증."""
        for node in self.nodes:
            if node.sequence_id % 2 != 0:
                raise OrderValidationError(
                    f'Node [{node.node_id}] sequence_id는 '
                    f'짝수여야 합니다: {node.sequence_id}'
                )

        for edge in self.edges:
            if edge.sequence_id % 2 != 1:
                raise OrderValidationError(
                    f'Edge [{edge.edge_id}] sequence_id는 '
                    f'홀수여야 합니다: {edge.sequence_id}'
                )

    def _validate_edge_connections(self) -> None:
        """엣지의 시작/종료 노드 연결 검증."""
        node_ids = {n.node_id for n in self.nodes}
        for edge in self.edges:
            if edge.start_node_id not in node_ids:
                raise OrderValidationError(
                    f'Edge [{edge.edge_id}]의 start_node_id '
                    f'[{edge.start_node_id}]가 노드 목록에 없습니다.'
                )
            if edge.end_node_id not in node_ids:
                raise OrderValidationError(
                    f'Edge [{edge.edge_id}]의 end_node_id '
                    f'[{edge.end_node_id}]가 노드 목록에 없습니다.'
                )

    def _validate_release_consistency(self) -> None:
        """Base/Horizon 경계의 일관성 검증.

        Base 노드 뒤에 Horizon 노드가 와야 하며,
        Horizon 뒤에 다시 Base가 오면 안 된다.
        """
        sorted_nodes = sorted(self.nodes, key=lambda n: n.sequence_id)
        found_horizon = False
        for node in sorted_nodes:
            if found_horizon and node.released:
                raise OrderValidationError(
                    f'Node [{node.node_id}]: Horizon 이후에 '
                    f'Base 노드가 올 수 없습니다.'
                )
            if not node.released:
                found_horizon = True
