"""Order 엔티티 단위 테스트."""

import pytest

from vda5050_fleet_adapter.domain.entities.edge import Edge
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.node import Node
from vda5050_fleet_adapter.domain.entities.order import Order
from vda5050_fleet_adapter.domain.exceptions import OrderValidationError


@pytest.fixture
def header():
    return Header(version='2.0.0', manufacturer='T', serial_number='A1')


class TestOrderProperties:
    def test_base_nodes(self, sample_order):
        base = sample_order.base_nodes
        assert len(base) == 2
        assert all(n.released for n in base)

    def test_horizon_nodes(self, sample_order):
        horizon = sample_order.horizon_nodes
        assert len(horizon) == 1
        assert all(not n.released for n in horizon)

    def test_base_edges(self, sample_order):
        base = sample_order.base_edges
        assert len(base) == 1

    def test_horizon_edges(self, sample_order):
        horizon = sample_order.horizon_edges
        assert len(horizon) == 1

    def test_last_base_node(self, sample_order):
        last = sample_order.last_base_node
        assert last is not None
        assert last.node_id == 'n2'

    def test_last_base_node_empty(self, header):
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[Node(node_id='n0', sequence_id=0, released=False)],
        )
        assert order.last_base_node is None


class TestOrderValidation:
    def test_valid_order_passes(self, sample_order):
        sample_order.validate()

    def test_empty_order_id_raises(self, header):
        order = Order(
            header=header, order_id='', order_update_id=0,
            nodes=[Node(node_id='n0', sequence_id=0, released=True)],
        )
        with pytest.raises(OrderValidationError, match='order_id'):
            order.validate()

    def test_empty_nodes_raises(self, header):
        order = Order(
            header=header, order_id='o1', order_update_id=0,
        )
        with pytest.raises(OrderValidationError, match='노드'):
            order.validate()

    def test_odd_node_sequence_id_raises(self, header):
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[Node(node_id='n0', sequence_id=1, released=True)],
        )
        with pytest.raises(OrderValidationError, match='짝수'):
            order.validate()

    def test_even_edge_sequence_id_raises(self, header):
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[
                Node(node_id='n0', sequence_id=0, released=True),
                Node(node_id='n2', sequence_id=2, released=True),
            ],
            edges=[
                Edge(
                    edge_id='e2', sequence_id=2, released=True,
                    start_node_id='n0', end_node_id='n2',
                ),
            ],
        )
        with pytest.raises(OrderValidationError, match='홀수'):
            order.validate()

    def test_edge_missing_start_node_raises(self, header):
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[
                Node(node_id='n0', sequence_id=0, released=True),
                Node(node_id='n2', sequence_id=2, released=True),
            ],
            edges=[
                Edge(
                    edge_id='e1', sequence_id=1, released=True,
                    start_node_id='n_unknown', end_node_id='n2',
                ),
            ],
        )
        with pytest.raises(OrderValidationError, match='start_node_id'):
            order.validate()

    def test_edge_missing_end_node_raises(self, header):
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[
                Node(node_id='n0', sequence_id=0, released=True),
                Node(node_id='n2', sequence_id=2, released=True),
            ],
            edges=[
                Edge(
                    edge_id='e1', sequence_id=1, released=True,
                    start_node_id='n0', end_node_id='n_unknown',
                ),
            ],
        )
        with pytest.raises(OrderValidationError, match='end_node_id'):
            order.validate()

    def test_base_after_horizon_raises(self, header):
        order = Order(
            header=header, order_id='o1', order_update_id=0,
            nodes=[
                Node(node_id='n0', sequence_id=0, released=True),
                Node(node_id='n2', sequence_id=2, released=False),
                Node(node_id='n4', sequence_id=4, released=True),
            ],
        )
        with pytest.raises(OrderValidationError, match='Horizon 이후'):
            order.validate()
