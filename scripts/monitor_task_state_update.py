#!/usr/bin/env python3
"""task_state_update 토픽 모니터링 스크립트.

ParkRobot, ChargeBattery 등 자동 생성 task도 발행되는지 확인용.

Usage:
    ros2 run vda5050_fleet_adapter monitor_task_state_update
    # 또는 직접 실행:
    python3 scripts/monitor_task_state_update.py
"""

import json
import re

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from std_msgs.msg import String


PLACE_PATTERN = re.compile(r'\[place:([^\]]+)\]')


class TaskStateMonitor(Node):

    def __init__(self):
        super().__init__('task_state_monitor')
        qos = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            String, '/task_state_update', self._on_task_state, qos
        )
        self._seen = set()
        self.get_logger().info('Monitoring /task_state_update ...')

    def _on_task_state(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        data = payload.get('data', {})
        booking = data.get('booking', {})
        booking_id = booking.get('id', 'N/A')
        requester = booking.get('requester', 'N/A')
        category = data.get('category', 'N/A')
        status = data.get('status', 'N/A')
        assigned = data.get('assigned_to', {})
        robot = assigned.get('name', 'N/A')

        # 최종 목적지 추출: phases[-1].category에서 [place:NAME]
        phases = data.get('phases', {})
        final_dest = None
        if phases:
            last_phase_key = max(phases.keys(), key=int)
            last_phase = phases[last_phase_key]
            phase_cat = last_phase.get('category', '')
            match = PLACE_PATTERN.search(phase_cat)
            if match:
                final_dest = match.group(1)

        # 중복 제거 (같은 booking_id + status)
        key = f'{booking_id}:{status}'
        if key in self._seen:
            return
        self._seen.add(key)

        self.get_logger().info(
            f'\n'
            f'  booking_id : {booking_id}\n'
            f'  requester  : {requester}\n'
            f'  category   : {category}\n'
            f'  status     : {status}\n'
            f'  robot      : {robot}\n'
            f'  final_dest : {final_dest}\n'
            f'  phases     : {[p.get("category", "") for p in phases.values()]}'
        )


def main():
    rclpy.init()
    node = TaskStateMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
