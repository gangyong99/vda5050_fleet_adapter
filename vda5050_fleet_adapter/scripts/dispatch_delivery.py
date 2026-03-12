#!/usr/bin/env python3

# Copyright 2025 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Dispatch a delivery task with VDA5050 pick/drop actions."""

import argparse
import asyncio
import json
import sys
import uuid

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSDurabilityPolicy as Durability
from rclpy.qos import QoSHistoryPolicy as History
from rclpy.qos import QoSProfile
from rclpy.qos import QoSReliabilityPolicy as Reliability
from rmf_task_msgs.msg import ApiRequest, ApiResponse


def build_delivery_payload(
    pickup: str,
    dropoff: str,
    load_type: str,
    load_id: str,
    station_name: str,
    fleet: str | None = None,
    robot: str | None = None,
    start_time_ms: int = 0,
    priority: int = 0,
) -> dict:
    """Build the JSON payload for a delivery task request.

    Args:
        pickup: Pickup waypoint name.
        dropoff: Dropoff waypoint name.
        load_type: Type of the load to pick (e.g. "Tool", "Pallet").
        load_id: Unique ID of the load/cart (e.g. "SP4ECTR002").
        station_name: Name of the dropoff station (e.g. "1004").
        fleet: Fleet name for robot_task_request (optional).
        robot: Robot name for robot_task_request (optional).
        start_time_ms: Earliest start time in unix milliseconds.
        priority: Priority value for the request.

    Returns:
        A dict representing the task API request payload.
    """
    payload: dict = {}
    if fleet and robot:
        payload['type'] = 'robot_task_request'
        payload['robot'] = robot
        payload['fleet'] = fleet
    else:
        payload['type'] = 'dispatch_task_request'

    request: dict = {}
    request['unix_millis_earliest_start_time'] = start_time_ms
    if priority:
        request['priority'] = {'value': priority}
    request['category'] = 'compose'

    description: dict = {}
    description['category'] = 'delivery'
    description['phases'] = []

    # Phase 1: go to pickup -> pick
    phase1_activities = [
        {
            'category': 'go_to_place',
            'description': pickup,
        },
        {
            'category': 'perform_action',
            'description': {
                'unix_millis_action_duration_estimate': 10000,
                'category': 'pick',
                'description': {
                    'loadType': load_type,
                    'loadID': load_id,
                },
                'use_tool_sink': False,
            },
        },
    ]

    # Phase 2: go to dropoff -> drop
    phase2_activities = [
        {
            'category': 'go_to_place',
            'description': dropoff,
        },
        {
            'category': 'perform_action',
            'description': {
                'unix_millis_action_duration_estimate': 10000,
                'category': 'drop',
                'description': {
                    'stationName': station_name,
                },
                'use_tool_sink': False,
            },
        },
    ]

    description['phases'].append({
        'activity': {
            'category': 'sequence',
            'description': {'activities': phase1_activities},
        },
    })
    description['phases'].append({
        'activity': {
            'category': 'sequence',
            'description': {'activities': phase2_activities},
        },
    })

    request['description'] = description
    payload['request'] = request
    return payload


class TaskRequester(Node):
    """ROS 2 node that dispatches a delivery task via task_api_requests."""

    def __init__(self, argv: list[str] = sys.argv):
        """Initialize TaskRequester and publish the delivery request."""
        super().__init__('dispatch_delivery')
        parser = argparse.ArgumentParser(
            description='Dispatch a delivery task with pick/drop actions')
        parser.add_argument(
            '-p', '--pickup', required=True, type=str,
            help='Pickup waypoint name')
        parser.add_argument(
            '-d', '--dropoff', required=True, type=str,
            help='Dropoff waypoint name')
        parser.add_argument(
            '--load_type', required=True, type=str,
            help='Load type for pick action (e.g. Tool, Pallet)')
        parser.add_argument(
            '--load_id', required=True, type=str,
            help='Load/cart ID for pick action (e.g. SP4ECTR002)')
        parser.add_argument(
            '--station_name', required=True, type=str,
            help='Station name for drop action (e.g. 1004)')
        parser.add_argument(
            '-F', '--fleet', type=str,
            help='Fleet name (use with -R for robot_task_request)')
        parser.add_argument(
            '-R', '--robot', type=str,
            help='Robot name (use with -F for robot_task_request)')
        parser.add_argument(
            '-st', '--start_time', type=int, default=0,
            help='Start time from now in seconds (default: 0)')
        parser.add_argument(
            '-pt', '--priority', type=int, default=0,
            help='Priority value for this request (default: 0)')
        parser.add_argument(
            '--use_sim_time', action='store_true',
            help='Use sim time (default: false)')

        self.args = parser.parse_args(argv[1:])
        self.response: asyncio.Future = asyncio.Future()

        transient_qos = QoSProfile(
            history=History.KEEP_LAST,
            depth=1,
            reliability=Reliability.RELIABLE,
            durability=Durability.TRANSIENT_LOCAL)

        self.pub = self.create_publisher(
            ApiRequest, 'task_api_requests', transient_qos)

        if self.args.use_sim_time:
            self.get_logger().info('Using Sim Time')
            param = Parameter('use_sim_time', Parameter.Type.BOOL, True)
            self.set_parameters([param])

        # Compute start time in milliseconds
        now = self.get_clock().now().to_msg()
        now.sec = now.sec + self.args.start_time
        start_time_ms = now.sec * 1000 + round(now.nanosec / 10**6)

        payload = build_delivery_payload(
            pickup=self.args.pickup,
            dropoff=self.args.dropoff,
            load_type=self.args.load_type,
            load_id=self.args.load_id,
            station_name=self.args.station_name,
            fleet=self.args.fleet,
            robot=self.args.robot,
            start_time_ms=start_time_ms,
            priority=self.args.priority,
        )

        msg = ApiRequest()
        msg.request_id = 'delivery_' + str(uuid.uuid4())
        msg.json_msg = json.dumps(payload)

        def receive_response(response_msg: ApiResponse) -> None:
            if response_msg.request_id == msg.request_id:
                self.response.set_result(
                    json.loads(response_msg.json_msg))

        self.sub = self.create_subscription(
            ApiResponse, 'task_api_responses', receive_response, 10)

        print(f'Json msg payload: \n{json.dumps(payload, indent=2)}')
        self.pub.publish(msg)


def main(argv: list[str] = sys.argv) -> None:
    """Dispatch a delivery task with VDA5050 pick/drop actions."""
    rclpy.init(args=sys.argv)
    args_without_ros = rclpy.utilities.remove_ros_args(sys.argv)

    task_requester = TaskRequester(args_without_ros)
    rclpy.spin_until_future_complete(
        task_requester, task_requester.response, timeout_sec=5.0)
    if task_requester.response.done():
        print(f'Got response: \n{task_requester.response.result()}')
    else:
        print('Did not get a response')
    rclpy.shutdown()


if __name__ == '__main__':
    main(sys.argv)
