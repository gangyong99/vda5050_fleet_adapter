"""내비게이션 그래프 파싱 및 좌표 변환 유틸리티.

RMF nav graph 파싱, 좌표 변환, 경로 탐색,
VDA5050 Node/Edge 생성 기능을 제공한다.
"""

from __future__ import annotations

import dataclasses
import logging
import math
from typing import Any
import uuid

import networkx as nx
import nudged
from vda5050_fleet_adapter.domain.entities.edge import Edge
from vda5050_fleet_adapter.domain.entities.node import Node
from vda5050_fleet_adapter.domain.enums import CorridorRefPoint
from vda5050_fleet_adapter.domain.value_objects.physical import Corridor
from vda5050_fleet_adapter.domain.value_objects.position import NodePosition
from vda5050_fleet_adapter.domain.value_objects.trajectory import (
    ControlPoint,
    Trajectory,
)
import yaml

logger = logging.getLogger(__name__)


def parse_nav_graph(
    nav_graph_path: str, level: str = 'L1'
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    """RMF 내비게이션 그래프 파일을 파싱한다.

    Args:
        nav_graph_path: nav graph YAML 파일 경로.
        level: 사용할 레벨 이름.

    Returns:
        (nodes, edges, index_to_name) 튜플.
        nodes: {name: {x, y, attributes}} 형태.
        edges: {name: {start, end, attributes}} 형태.
        index_to_name: vertex index → waypoint name 매핑 리스트.
    """
    with open(nav_graph_path, 'r') as f:
        nav_graph = yaml.safe_load(f)

    vertices = nav_graph['levels'][level]['vertices']
    lanes = nav_graph['levels'][level]['lanes']

    # vertex 인덱스 → 이름 매핑 (빈 이름이나 중복은 node{i}로 대체)
    nodes: dict[str, dict[str, Any]] = {}
    index_to_name: list[str] = []
    for i, vertex in enumerate(vertices):
        attrs = vertex[2] if len(vertex) > 2 else {}
        name = attrs.get('name', '') if isinstance(attrs, dict) else ''
        if not name or name in nodes:
            name = f'node{i}'
        index_to_name.append(name)
        nodes[name] = {
            'x': float(vertex[0]),
            'y': float(vertex[1]),
            'attributes': attrs,
        }

    # lane은 이미 방향별로 분리되어 있으므로 그대로 사용
    edges: dict[str, dict[str, Any]] = {}
    for i, lane in enumerate(lanes):
        start_node = index_to_name[lane[0]]
        end_node = index_to_name[lane[1]]
        attrs = lane[2] if len(lane) > 2 else {}
        edge_name = f'edge{i}'
        edges[edge_name] = {
            'start': start_node,
            'end': end_node,
            'attributes': attrs,
        }

    logger.info(
        'Parsed nav graph: %d nodes, %d edges', len(nodes), len(edges)
    )
    return nodes, edges, index_to_name


def compute_transforms(
    rmf_coords: list[list[float]],
    robot_coords: list[list[float]],
) -> nudged.Transform:
    """RMF ↔ 로봇 좌표계 변환을 계산한다.

    Args:
        rmf_coords: RMF 좌표 기준점 [[x,y], ...].
        robot_coords: 로봇 좌표 기준점 [[x,y], ...].

    Returns:
        nudged Transform 객체 (rmf → robot).
    """
    tf = nudged.estimate(rmf_coords, robot_coords)
    mse = nudged.estimate_error(tf, rmf_coords, robot_coords)
    logger.info('Coordinate transform MSE: %.6f', mse)
    return tf


def transform_coords(
    x: float, y: float, theta: float,
    rotation: float, scale: float, translation: list[float],
) -> tuple[float, float, float]:
    """RMF 좌표를 로봇 좌표로 변환한다.

    Args:
        x: RMF x 좌표.
        y: RMF y 좌표.
        theta: RMF 방향 (rad).
        rotation: 회전 각도 (rad).
        scale: 스케일 팩터.
        translation: [tx, ty] 이동 벡터.

    Returns:
        (x', y', theta') 변환된 좌표.
    """
    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    x_rot = x * cos_r - y * sin_r
    y_rot = x * sin_r + y * cos_r
    x_out = x_rot * scale + translation[0]
    y_out = y_rot * scale + translation[1]
    theta_out = theta + rotation
    return x_out, y_out, theta_out


def inverse_transform_coords(
    x: float, y: float, theta: float,
    rotation: float, scale: float, translation: list[float],
) -> tuple[float, float, float]:
    """로봇 좌표를 RMF 좌표로 역변환한다.

    Args:
        x: 로봇 x 좌표.
        y: 로봇 y 좌표.
        theta: 로봇 방향 (rad).
        rotation: 회전 각도 (rad).
        scale: 스케일 팩터.
        translation: [tx, ty] 이동 벡터.

    Returns:
        (x', y', theta') RMF 좌표.
    """
    x_t = x - translation[0]
    y_t = y - translation[1]
    x_s = x_t / scale if scale != 0 else x_t
    y_s = y_t / scale if scale != 0 else y_t
    cos_r = math.cos(-rotation)
    sin_r = math.sin(-rotation)
    x_out = x_s * cos_r - y_s * sin_r
    y_out = x_s * sin_r + y_s * cos_r
    theta_out = theta - rotation
    return x_out, y_out, theta_out


def apply_transformations(
    nodes: dict[str, dict[str, Any]],
    rotation: float,
    scale: float,
    translation: list[float],
) -> None:
    """노드 좌표에 변환을 적용한다 (in-place).

    Args:
        nodes: 노드 dict (parse_nav_graph 반환값).
        rotation: 회전 각도 (rad).
        scale: 스케일 팩터.
        translation: [tx, ty] 이동 벡터.
    """
    for name, node in nodes.items():
        x_new, y_new, _ = transform_coords(
            node['x'], node['y'], 0.0, rotation, scale, translation
        )
        node['x'] = x_new
        node['y'] = y_new
        logger.debug(
            'Transformed node %s: x=%.3f, y=%.3f', name, x_new, y_new
        )


def create_graph(
    nodes: dict[str, dict[str, Any]],
    edges: dict[str, dict[str, Any]],
) -> nx.Graph:
    """Networkx 그래프를 생성한다.

    Args:
        nodes: 노드 dict.
        edges: 엣지 dict.

    Returns:
        가중치 그래프.
    """
    graph = nx.Graph()
    for edge_name, edge in edges.items():
        start = edge['start']
        end = edge['end']
        dx = nodes[start]['x'] - nodes[end]['x']
        dy = nodes[start]['y'] - nodes[end]['y']
        weight = math.sqrt(dx * dx + dy * dy)
        graph.add_edge(start, end, weight=weight)
    return graph


def find_nearest_node(
    nodes: dict[str, dict[str, Any]], x: float, y: float
) -> str | None:
    """가장 가까운 노드를 찾는다.

    Args:
        nodes: 노드 dict.
        x: x 좌표.
        y: y 좌표.

    Returns:
        가장 가까운 노드 이름 또는 None.
    """
    nearest: str | None = None
    min_dist = float('inf')
    for name, node in nodes.items():
        dx = x - node['x']
        dy = y - node['y']
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < min_dist:
            min_dist = dist
            nearest = name
    return nearest


def compute_path(
    graph: nx.Graph, start: str, goal: str
) -> list[str] | None:
    """최단 경로를 계산한다.

    Args:
        graph: networkx 그래프.
        start: 시작 노드 이름.
        goal: 목표 노드 이름.

    Returns:
        노드 이름 리스트 또는 경로 없으면 None.
    """
    try:
        return nx.shortest_path(graph, source=start, target=goal, weight='weight')
    except nx.NetworkXNoPath:
        logger.warning('No path from %s to %s', start, goal)
        return None
    except nx.NodeNotFound as e:
        logger.warning('Node not found: %s', e)
        return None


def find_edge_name(
    edges: dict[str, dict[str, Any]],
    start_node: str,
    end_node: str,
) -> str | None:
    """두 노드 사이의 엣지 이름을 찾는다.

    Args:
        edges: 엣지 dict.
        start_node: 시작 노드.
        end_node: 종료 노드.

    Returns:
        엣지 이름 또는 None.
    """
    for edge_name, edge in edges.items():
        if edge['start'] == start_node and edge['end'] == end_node:
            return edge_name
    return None


def _normalize_angle(angle: float) -> float:
    """각도를 -π ~ π 범위로 정규화한다.

    Args:
        angle: 정규화할 각도 (rad).

    Returns:
        -π ~ π 범위의 각도.
    """
    return math.atan2(math.sin(angle), math.cos(angle))


def _compute_heading(x1: float, y1: float, x2: float, y2: float) -> float:
    """두 좌표 간 heading을 계산한다.

    Args:
        x1: 시작점 x.
        y1: 시작점 y.
        x2: 끝점 x.
        y2: 끝점 y.

    Returns:
        heading (rad), atan2(dy, dx).
    """
    return math.atan2(y2 - y1, x2 - x1)


def build_vda5050_nodes_edges(
    path: list[str],
    nodes: dict[str, dict[str, Any]],
    map_id: str,
    seq_start: int = 0,
    base_end_index: int | None = None,
    edges: dict[str, dict[str, Any]] | None = None,
    turn_angle_threshold: float = 0.2618,
    allowed_deviation_theta: float = 0.2618,
) -> tuple[list[Node], list[Edge]]:
    """경로에서 VDA5050 Node/Edge 목록을 생성한다.

    Base/Horizon 분리: base_end_index 이하의 노드는 Base(released=True),
    초과하는 노드는 Horizon(released=False)으로 설정된다.
    엣지는 end 노드의 released 상태를 따른다 (i < base_end_index면 Base).

    Args:
        path: 노드 이름 리스트 (경로).
        nodes: 노드 dict (좌표 포함).
        map_id: 맵 ID.
        seq_start: 시작 시퀀스 번호.
        base_end_index: 마지막 Base 노드의 path 인덱스.
            None이면 모든 노드를 Base로 설정 (기존 동작).
        edges: nav graph 엣지 dict (속성 포함). None이면 속성 미적용.
        turn_angle_threshold: Base 도착 노드에 theta를 설정하는
            최소 회전각 (rad). 기본 0.2618 (15°).
        allowed_deviation_theta: theta 설정 시 허용 오차 (rad).
            기본 0.2618 (15°).

    Returns:
        (vda_nodes, vda_edges) 튜플.
    """
    if base_end_index is None:
        base_end_index = len(path) - 1

    # Edge 속성 룩업 인덱스: {(start, end): attributes}
    edge_lookup: dict[tuple[str, str], dict] = {}
    if edges is not None:
        for edge_data in edges.values():
            key = (edge_data['start'], edge_data['end'])
            edge_lookup[key] = edge_data.get('attributes', {})

    vda_nodes: list[Node] = []
    vda_edges: list[Edge] = []

    for i, node_name in enumerate(path):
        seq = seq_start + i * 2
        nd = nodes[node_name]
        released = (i <= base_end_index)

        # Node 속성: allowedDeviationXY
        attrs = nd.get('attributes', {})
        allowed_dev = attrs.get('allowedDeviationXY')

        vda_nodes.append(
            Node(
                node_id=node_name,
                sequence_id=seq,
                released=released,
                node_position=NodePosition(
                    x=nd['x'],
                    y=nd['y'],
                    map_id=map_id,
                    allowed_deviation_xy=allowed_dev,
                ),
            )
        )

    # Base 도착 노드에 theta 설정:
    # base 이후 horizon이 있고 회전각이 threshold 이상이면
    # 출발 heading을 theta로 설정하여 회전 완료 후 도착을 보고한다.
    if (
        base_end_index >= 1
        and base_end_index < len(path) - 1
    ):
        prev_nd = nodes[path[base_end_index - 1]]
        base_nd = nodes[path[base_end_index]]
        next_nd = nodes[path[base_end_index + 1]]
        heading_in = _compute_heading(
            prev_nd['x'], prev_nd['y'], base_nd['x'], base_nd['y'],
        )
        heading_out = _compute_heading(
            base_nd['x'], base_nd['y'], next_nd['x'], next_nd['y'],
        )
        turn_angle = abs(_normalize_angle(heading_out - heading_in))
        if turn_angle >= turn_angle_threshold:
            edge_orientation = edge_lookup.get(
                (path[base_end_index], path[base_end_index + 1]),
                {},
            ).get('orientation', 0.0) or 0.0
            theta = _normalize_angle(heading_out + edge_orientation)
            old_pos = vda_nodes[base_end_index].node_position
            new_pos = dataclasses.replace(
                old_pos,
                theta=theta,
                allowed_deviation_theta=allowed_deviation_theta,
            )
            vda_nodes[base_end_index] = dataclasses.replace(
                vda_nodes[base_end_index], node_position=new_pos,
            )
            logger.debug(
                'Base node %s theta=%.3f (turn=%.1f°, threshold=%.1f°)',
                path[base_end_index], theta,
                math.degrees(turn_angle),
                math.degrees(turn_angle_threshold),
            )

    for i in range(len(path) - 1):
        seq = seq_start + i * 2 + 1
        edge_id = f'{path[i]}_{path[i + 1]}_{uuid.uuid4().hex[:8]}'
        released = (i < base_end_index)

        # Edge 속성 룩업
        edge_attrs = edge_lookup.get((path[i], path[i + 1]), {})

        # corridor 파싱
        corridor = None
        if 'corridor' in edge_attrs:
            c = edge_attrs['corridor']
            corridor = Corridor(
                left_width=c['leftWidth'],
                right_width=c['rightWidth'],
                corridor_ref_point=CorridorRefPoint(
                    c.get('corridorRefPoint', 'KINEMATICCENTER')
                ),
            )

        # trajectory 파싱
        trajectory = None
        if 'trajectory' in edge_attrs:
            t = edge_attrs['trajectory']
            trajectory = Trajectory(
                degree=t['degree'],
                knot_vector=tuple(t.get('knotVector', [])),
                control_points=tuple(
                    ControlPoint(
                        x=cp['x'], y=cp['y'],
                        weight=cp.get('weight', 1.0),
                    )
                    for cp in t.get('controlPoints', [])
                ),
            )

        vda_edges.append(
            Edge(
                edge_id=edge_id,
                sequence_id=seq,
                released=released,
                start_node_id=path[i],
                end_node_id=path[i + 1],
                max_speed=edge_attrs.get('maxSpeed'),
                rotation_allowed=edge_attrs.get('rotationAllowed'),
                corridor=corridor,
                trajectory=trajectory,
            )
        )

    return vda_nodes, vda_edges
