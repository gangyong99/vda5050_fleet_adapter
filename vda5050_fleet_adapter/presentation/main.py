r"""VDA5050 Fleet Adapter 진입점.

mrceki/vda5050_fleet_adapter + rmf_demos_fleet_adapter 패턴을 따른다.

실행: ros2 run vda5050_fleet_adapter fleet_adapter \\
        -c config.yaml -n nav_graph.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
import time

import rclpy
import rclpy.node
from rclpy.parameter import Parameter
import rmf_adapter
from rmf_adapter import Adapter
import rmf_adapter.easy_full_control as rmf_easy
from vda5050_fleet_adapter.infra.mqtt.mqtt_client import MqttClient
from vda5050_fleet_adapter.infra.mqtt.vda5050_robot_api import (
    Vda5050RobotAPI,
)
from vda5050_fleet_adapter.infra.nav_graph.graph_utils import (
    apply_transformations,
    compute_transforms,
    create_graph,
    parse_nav_graph,
)
from vda5050_fleet_adapter.usecase.ports.config_port import MqttConfig
from vda5050_fleet_adapter.usecase.robot_adapter import RobotAdapter
import yaml


def _parallel(func):
    """비동기 병렬 실행 데코레이터."""
    def run_in_parallel(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(
            None, func, *args, **kwargs
        )
    return run_in_parallel


@_parallel
def _update_robot(robot: RobotAdapter) -> None:
    """로봇 상태를 업데이트한다."""
    data = robot.api.get_data(robot.name)
    if data is None:
        robot.node.get_logger().warn(
            f'No state data yet for {robot.name}, '
            f'waiting for MQTT state message...'
        )
        return

    state = rmf_easy.RobotState(
        data.map_name, data.position, data.battery_soc
    )

    if robot.update_handle is None:
        robot.node.get_logger().info(
            f'[{robot.name}] adding robot to fleet_handle...'
        )
        if not robot.api.is_robot_connected(robot.name):
            return
        if not robot.api.is_download_map_ready(robot.name):
            robot.node.get_logger().info(
                f'[{robot.name}] waiting for downloadMap to complete...'
            )
            return
        robot.update_handle = robot.fleet_handle.add_robot(
            robot.name,
            state,
            robot.configuration,
            robot.make_callbacks(),
        )
        return

    robot.update(state, data)


def main(argv: list[str] | None = None) -> None:
    """Fleet Adapter를 시작한다.

    Args:
        argv: 커맨드 라인 인자.
    """
    if argv is None:
        argv = sys.argv

    logging.basicConfig(
        level=logging.INFO,
        format='[%(name)s] %(levelname)s: %(message)s',
    )

    rclpy.init(args=argv)
    rmf_adapter.init_rclcpp()
    args_without_ros = rclpy.utilities.remove_ros_args(argv)

    parser = argparse.ArgumentParser(
        prog='fleet_adapter',
        description='VDA5050 Fleet Adapter for Open-RMF',
    )
    parser.add_argument(
        '-c', '--config_file', type=str, required=True,
        help='Path to the config.yaml file',
    )
    parser.add_argument(
        '-n', '--nav_graph', type=str, required=True,
        help='Path to the nav_graph for this fleet adapter',
    )
    parser.add_argument(
        '-sim', '--use_sim_time', action='store_true',
        help='Use sim time, default: false',
    )
    args = parser.parse_args(args_without_ros[1:])

    config_path = args.config_file
    nav_graph_path = args.nav_graph

    # 1. FleetConfiguration 로드
    fleet_config = rmf_easy.FleetConfiguration.from_config_files(
        config_path, nav_graph_path
    )
    assert fleet_config, f'Failed to parse config file [{config_path}]'

    # 2. YAML config 직접 로드 (fleet_manager 등 추가 설정)
    with open(config_path, 'r') as f:
        config_yaml = yaml.safe_load(f)

    fleet_name = fleet_config.fleet_name
    node = rclpy.node.Node(f'{fleet_name}_command_handle')

    # 3. Adapter 생성
    adapter = Adapter.make(f'{fleet_name}_fleet_adapter')
    assert adapter, (
        'Unable to initialize fleet adapter. '
        'Please ensure RMF Schedule Node is running'
    )

    if args.use_sim_time:
        param = Parameter('use_sim_time', Parameter.Type.BOOL, True)
        node.set_parameters([param])
        adapter.node.use_sim_time()

    adapter.start()
    time.sleep(1.0)

    # 4. Nav graph 파싱
    nav_nodes, nav_edges, _index_to_name = parse_nav_graph(nav_graph_path)
    nav_graph = create_graph(nav_nodes, nav_edges)

    # 5. 좌표 변환 (reference_coordinates 있으면)
    if 'reference_coordinates' in config_yaml:
        for level, coords in config_yaml['reference_coordinates'].items():
            node.get_logger().info(
                f'Computing transforms for {level}'
            )
            tf = compute_transforms(coords['rmf'], coords['robot'])
            from rmf_adapter import Transformation
            rmf_tf = Transformation(
                tf.get_rotation(), tf.get_scale(), tf.get_translation()
            )
            fleet_config.add_robot_coordinates_transformation(
                level, rmf_tf
            )
            apply_transformations(
                nav_nodes,
                tf.get_rotation(),
                tf.get_scale(),
                tf.get_translation(),
            )

    # 6. Fleet handle 생성
    fleet_handle = adapter.add_easy_fleet(fleet_config)

    # 7. MQTT + VDA5050 RobotAPI 생성
    fleet_mgr = config_yaml.get('fleet_manager', {})
    mqtt_config = MqttConfig(
        broker_host=fleet_mgr.get('ip', '127.0.0.1'),
        broker_port=fleet_mgr.get('port', 1883),
    )
    mqtt_client = MqttClient(mqtt_config, client_id=fleet_name)
    prefix = fleet_mgr.get('prefix', 'uagv/v2/manufacturer')
    manufacturer = prefix.split('/')[-1] if '/' in prefix else ''

    download_map_config = config_yaml.get('download_map')
    api = Vda5050RobotAPI(
        mqtt_client, prefix, manufacturer,
        download_map_config=download_map_config,
    )
    api.connect()
    time.sleep(0.5)  # MQTT 연결 대기
    node.get_logger().info(
        f'MQTT connected: {mqtt_client.is_connected}, '
        f'prefix: {prefix}'
    )

    # 8. 로봇별 RobotAdapter 생성
    import math as _math
    arrival_threshold = config_yaml.get('rmf_fleet', {}).get(
        'arrival_threshold', 0.5
    )
    recharge_soc = config_yaml.get('rmf_fleet', {}).get(
        'recharge_soc', 1.0
    )
    turn_angle_threshold = _math.radians(
        config_yaml.get('rmf_fleet', {}).get(
            'turn_angle_threshold', 15.0
        )
    )
    allowed_deviation_theta = _math.radians(
        config_yaml.get('rmf_fleet', {}).get(
            'allowed_deviation_theta', 15.0
        )
    )
    action_completion_delay = config_yaml.get('rmf_fleet', {}).get(
        'action_completion_delay', 0.0
    )
    action_durations = config_yaml.get('rmf_fleet', {}).get(
        'action_durations', {}
    )
    node.get_logger().info(f'known_robots: {fleet_config.known_robots}')
    robots: dict[str, RobotAdapter] = {}
    for robot_name in fleet_config.known_robots:
        robot_config = fleet_config.get_known_robot_configuration(
            robot_name
        )
        api.subscribe_robot(robot_name)
        node.get_logger().info(
            f'Robot registered: {robot_name}, '
            f'state topic: {prefix}/{robot_name}/state'
        )

        robot = RobotAdapter(
            name=robot_name,
            api=api,
            node=node,
            fleet_handle=fleet_handle,
            nav_nodes=nav_nodes,
            nav_edges=nav_edges,
            nav_graph=nav_graph,
            arrival_threshold=arrival_threshold,
            recharge_soc=recharge_soc,
            turn_angle_threshold=turn_angle_threshold,
            allowed_deviation_theta=allowed_deviation_theta,
        )
        robot.action_completion_delay = action_completion_delay
        robot.action_durations = action_durations
        robot.configuration = robot_config
        robots[robot_name] = robot

    # 9. 업데이트 루프
    update_period = 1.0 / config_yaml.get('rmf_fleet', {}).get(
        'robot_state_update_frequency', 10.0
    )

    def update_loop() -> None:
        asyncio.set_event_loop(asyncio.new_event_loop())
        node.get_logger().info(
            f'update_loop started, robots: {list(robots.keys())}'
        )
        while rclpy.ok():
            update_jobs = []
            for robot in robots.values():
                update_jobs.append(_update_robot(robot))

            if not update_jobs:
                time.sleep(update_period)
                continue

            asyncio.get_event_loop().run_until_complete(
                asyncio.wait(update_jobs)
            )

            time.sleep(update_period)

    update_thread = threading.Thread(
        target=update_loop, daemon=True
    )
    update_thread.start()

    # 10. ROS 2 spin
    rclpy_executor = rclpy.executors.SingleThreadedExecutor()
    rclpy_executor.add_node(node)

    try:
        rclpy_executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info('Keyboard interrupt received')
    finally:
        api.disconnect()
        node.destroy_node()
        rclpy_executor.shutdown()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main(sys.argv)
