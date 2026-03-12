"""VDA5050 MQTT 기반 RobotAPI 구현.

VDA5050 프로토콜을 통해 AGV와 통신하는 RobotAPI 어댑터.
MQTT로 Order/InstantActions를 발행하고, State를 구독하여
로봇 상태를 캐시한다.
"""

from __future__ import annotations

from datetime import datetime, UTC
import logging
import threading
from typing import Any
import uuid

from vda5050_fleet_adapter.domain.entities.action import Action
from vda5050_fleet_adapter.domain.entities.edge import Edge
from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.entities.node import Node
from vda5050_fleet_adapter.domain.entities.order import Order
from vda5050_fleet_adapter.domain.enums import (
    ActionStatus,
    BlockingType,
    ConnectionState,
    OperatingMode,
)
from vda5050_fleet_adapter.infra.mqtt.message_serializer import (
    deserialize_state,
    serialize_instant_actions,
    serialize_order,
)
from vda5050_fleet_adapter.infra.mqtt.mqtt_client import MqttClient
from vda5050_fleet_adapter.usecase.ports.robot_api import (
    CommissionState,
    RobotAPI,
    RobotAPIResult,
    RobotUpdateData,
)

logger = logging.getLogger(__name__)

# VDA5050 프로토콜 버전
_VDA5050_VERSION = '2.0.0'


class Vda5050RobotAPI(RobotAPI):
    """VDA5050 MQTT 프로토콜 기반 RobotAPI 구현.

    Args:
        mqtt_client: MQTT 클라이언트.
        prefix: MQTT 토픽 prefix (e.g. 'uagv/v2/manufacturer').
        manufacturer: AGV 제조사명.
    """

    def __init__(
        self,
        mqtt_client: MqttClient,
        prefix: str,
        manufacturer: str = '',
        download_map_config: dict | None = None,
    ) -> None:
        """Initialize."""
        self._mqtt = mqtt_client
        self._prefix = prefix
        self._manufacturer = manufacturer
        self._lock = threading.Lock()

        # 로봇별 캐시 상태: {robot_name: AgvState}
        self._state_cache: dict[str, Any] = {}
        # 로봇별 명령 ID 매핑: {robot_name: {cmd_id: order_id}}
        self._cmd_order_map: dict[str, dict[int, str]] = {}
        # 로봇별 완료된 cmd_id: {robot_name: set(cmd_id)}
        self._completed_cmds: dict[str, set[int]] = {}
        # 토픽별 header ID 카운터
        self._header_ids: dict[str, int] = {}
        # 로봇별 연결 상태 캐시: {robot_name: ConnectionState}
        self._connection_cache: dict[str, ConnectionState] = {}
        # downloadMap 설정 및 pending 상태
        self._download_map_config = download_map_config
        self._download_map_pending: dict[str, str | None] = {}

    def subscribe_robot(self, robot_name: str) -> None:
        """로봇의 MQTT 토픽을 구독한다.

        Args:
            robot_name: 구독할 로봇 이름.
        """
        state_topic = self._build_topic(robot_name, 'state')
        self._mqtt.subscribe(
            state_topic,
            lambda t, p: self._on_state_message(robot_name, p),
            qos=0,
        )
        logger.info('Subscribed to %s', state_topic)

        connection_topic = self._build_topic(robot_name, 'connection')
        self._mqtt.subscribe(
            connection_topic,
            lambda t, p: self._on_connection_message(robot_name, p),
            qos=1,
        )
        logger.info('Subscribed to %s', connection_topic)

    def is_robot_connected(self, robot_name: str) -> bool:
        """로봇의 VDA5050 연결 상태가 ONLINE인지 확인한다.

        연결 상태를 수신한 적이 없으면 True(연결 가정)를 반환한다.

        Args:
            robot_name: 로봇 이름.

        Returns:
            ONLINE이거나 상태 미수신이면 True, 그 외 False.
        """
        with self._lock:
            state = self._connection_cache.get(robot_name)
        return state is None or state == ConnectionState.ONLINE

    def is_download_map_ready(self, robot_name: str) -> bool:
        """Check downloadMap action 완료 여부를 확인한다.

        config가 없으면 항상 True. pending action_id가 없으면(미전송) False.
        cached state의 action_states에서 FINISHED/FAILED이면 True.

        Args:
            robot_name: 로봇 이름.

        Returns:
            맵 다운로드 준비 완료 여부.
        """
        if self._download_map_config is None:
            return True

        with self._lock:
            action_id = self._download_map_pending.get(robot_name)
            state = self._state_cache.get(robot_name)

        # 미전송 상태
        if action_id is None:
            return False

        # 이미 완료 확인됨
        if action_id == '':
            return True

        if state is None:
            return False

        for action_state in state.action_states:
            if action_state.action_id == action_id:
                if action_state.action_status in (
                    ActionStatus.FINISHED, ActionStatus.FAILED
                ):
                    with self._lock:
                        self._download_map_pending[robot_name] = ''
                    logger.info(
                        'downloadMap completed: robot=%s, '
                        'action_id=%s, status=%s',
                        robot_name, action_id,
                        action_state.action_status,
                    )
                    return True

        return False

    def _send_download_map(self, robot_name: str) -> None:
        """Send downloadMap instantAction을 전송한다.

        Args:
            robot_name: 로봇 이름.
        """
        if self._download_map_config is None:
            return

        from vda5050_fleet_adapter.domain.entities.action import (
            ActionParameter,
        )

        action_id = f'downloadMap_{uuid.uuid4().hex[:8]}'
        params = [
            ActionParameter(
                key='mapId',
                value=self._download_map_config.get('map_id', ''),
            ),
            ActionParameter(
                key='mapDownloadUrl',
                value=self._download_map_config.get(
                    'map_download_url', ''
                ),
            ),
            ActionParameter(
                key='mapVersion',
                value=self._download_map_config.get(
                    'map_version', ''
                ),
            ),
        ]
        action = Action(
            action_type='downloadMap',
            action_id=action_id,
            blocking_type=BlockingType.NONE,
            action_parameters=params,
        )

        header = self._make_header(robot_name, 'instantActions')
        payload = serialize_instant_actions(header, [action])
        topic = self._build_topic(robot_name, 'instantActions')
        self._mqtt.publish(topic, payload, qos=0)

        with self._lock:
            self._download_map_pending[robot_name] = action_id

        logger.info(
            'downloadMap sent: robot=%s, action_id=%s',
            robot_name, action_id,
        )

    def connect(self) -> None:
        """MQTT 브로커에 연결한다."""
        self._mqtt.connect()

    def disconnect(self) -> None:
        """MQTT 브로커 연결을 종료한다."""
        self._mqtt.disconnect()

    def navigate(
        self,
        robot_name: str,
        cmd_id: int,
        nodes: list[Node],
        edges: list[Edge],
        map_name: str,
        order_id: str = '',
        order_update_id: int = 0,
        *,
        track_action_id: str | None = None,
    ) -> RobotAPIResult:
        """VDA5050 Order를 전송하여 내비게이션을 시작한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 명령 ID.
            nodes: VDA5050 Node 목록.
            edges: VDA5050 Edge 목록.
            map_name: 대상 맵 이름.
            order_id: 외부 지정 Order ID (빈 문자열이면 자동 생성).
            order_update_id: Order update 카운터.
            track_action_id: nodeAction의 action_id. 제공 시 완료 추적에
                order_id 대신 action_id를 사용한다.

        Returns:
            명령 결과.
        """
        if not self._mqtt.is_connected:
            logger.warning('MQTT not connected, will retry navigate')
            return RobotAPIResult.RETRY

        if not self.is_robot_connected(robot_name):
            logger.warning(
                'Robot %s not connected, will retry navigate', robot_name
            )
            return RobotAPIResult.RETRY

        if not self.is_download_map_ready(robot_name):
            logger.warning(
                'Robot %s downloadMap not ready, will retry navigate',
                robot_name,
            )
            return RobotAPIResult.RETRY

        if not order_id:
            order_id = f'order_{cmd_id}_{uuid.uuid4().hex[:8]}'
        header = self._make_header(robot_name, 'order')

        order = Order(
            header=header,
            order_id=order_id,
            order_update_id=order_update_id,
            nodes=nodes,
            edges=edges,
        )

        payload = serialize_order(order)
        topic = self._build_topic(robot_name, 'order')
        self._mqtt.publish(topic, payload, qos=0)

        track_id = track_action_id if track_action_id else order_id
        with self._lock:
            if robot_name not in self._cmd_order_map:
                self._cmd_order_map[robot_name] = {}
            self._cmd_order_map[robot_name][cmd_id] = track_id
            if robot_name not in self._completed_cmds:
                self._completed_cmds[robot_name] = set()

        logger.info(
            'Navigate order sent: robot=%s, cmd_id=%d, order_id=%s, '
            'track_id=%s, nodes=%d, edges=%d',
            robot_name, cmd_id, order_id, track_id,
            len(nodes), len(edges),
        )
        return RobotAPIResult.SUCCESS

    def stop(self, robot_name: str, cmd_id: int) -> RobotAPIResult:
        """Cancel order instant action을 전송한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 명령 ID.

        Returns:
            명령 결과.
        """
        if not self._mqtt.is_connected:
            logger.warning('MQTT not connected, will retry stop')
            return RobotAPIResult.RETRY

        if not self.is_robot_connected(robot_name):
            logger.warning(
                'Robot %s not connected, will retry stop', robot_name
            )
            return RobotAPIResult.RETRY

        header = self._make_header(robot_name, 'instantActions')
        action = Action(
            action_type='cancelOrder',
            action_id=f'cancel_{cmd_id}_{uuid.uuid4().hex[:8]}',
            blocking_type=BlockingType.HARD,
        )

        payload = serialize_instant_actions(header, [action])
        topic = self._build_topic(robot_name, 'instantActions')
        self._mqtt.publish(topic, payload, qos=0)

        logger.info('Stop (cancelOrder) sent: robot=%s', robot_name)
        return RobotAPIResult.SUCCESS

    def pause(self, robot_name: str, cmd_id: int) -> RobotAPIResult:
        """Start-pause instant action을 전송한다.

        Negotiation 발생 시 로봇을 일시정지시키기 위해 사용한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 명령 ID.

        Returns:
            명령 결과.
        """
        if not self._mqtt.is_connected:
            logger.warning('MQTT not connected, will retry pause')
            return RobotAPIResult.RETRY

        header = self._make_header(robot_name, 'instantActions')
        action = Action(
            action_type='startPause',
            action_id=f'pause_{cmd_id}_{uuid.uuid4().hex[:8]}',
            blocking_type=BlockingType.HARD,
        )

        payload = serialize_instant_actions(header, [action])
        topic = self._build_topic(robot_name, 'instantActions')
        self._mqtt.publish(topic, payload, qos=0)

        logger.info('Pause (startPause) sent: robot=%s', robot_name)
        return RobotAPIResult.SUCCESS

    def start_activity(
        self,
        robot_name: str,
        cmd_id: int,
        activity: str,
        action_params: dict,
    ) -> RobotAPIResult:
        """VDA5050 instant action을 전송한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 명령 ID.
            activity: 액션 종류.
            action_params: 액션 파라미터 dict.

        Returns:
            명령 결과.
        """
        if not self._mqtt.is_connected:
            logger.warning('MQTT not connected, will retry activity')
            return RobotAPIResult.RETRY

        if not self.is_robot_connected(robot_name):
            logger.warning(
                'Robot %s not connected, will retry activity', robot_name
            )
            return RobotAPIResult.RETRY

        header = self._make_header(robot_name, 'instantActions')

        from vda5050_fleet_adapter.domain.entities.action import (
            ActionParameter,
        )

        params = [
            ActionParameter(key=k, value=v)
            for k, v in action_params.items()
        ]
        action = Action(
            action_type=activity,
            action_id=f'{activity}_{cmd_id}_{uuid.uuid4().hex[:8]}',
            blocking_type=BlockingType.HARD,
            action_parameters=params,
        )

        payload = serialize_instant_actions(header, [action])
        topic = self._build_topic(robot_name, 'instantActions')
        self._mqtt.publish(topic, payload, qos=0)

        with self._lock:
            if robot_name not in self._cmd_order_map:
                self._cmd_order_map[robot_name] = {}
            self._cmd_order_map[robot_name][cmd_id] = action.action_id

        logger.info(
            'Activity sent: robot=%s, activity=%s, cmd_id=%d',
            robot_name, activity, cmd_id,
        )
        return RobotAPIResult.SUCCESS

    def get_data(self, robot_name: str) -> RobotUpdateData | None:
        """로봇의 현재 상태 데이터를 반환한다.

        Args:
            robot_name: 로봇 이름.

        Returns:
            상태 데이터 또는 아직 수신 전이면 None.
        """
        with self._lock:
            state = self._state_cache.get(robot_name)

        if state is None:
            return None

        position = [0.0, 0.0, 0.0]
        map_name = ''
        if state.agv_position is not None:
            position = [
                state.agv_position.x,
                state.agv_position.y,
                state.agv_position.theta,
            ]
            map_name = state.agv_position.map_id

        battery_soc = 0.0
        if state.battery_state is not None:
            battery_soc = state.battery_state.battery_charge / 100.0

        return RobotUpdateData(
            robot_name=robot_name,
            map_name=map_name,
            position=position,
            battery_soc=battery_soc,
        )

    def get_commission_state(
        self, robot_name: str
    ) -> CommissionState | None:
        """VDA5050 상태 기반 commission 상태를 반환한다.

        operating_mode, errors, safety_state, connection_state를 종합하여
        RMF commission 설정을 결정한다.

        Args:
            robot_name: 로봇 이름.

        Returns:
            commission 상태 또는 상태 미수신 시 None.
        """
        with self._lock:
            state = self._state_cache.get(robot_name)
            conn = self._connection_cache.get(robot_name)

        if state is None:
            return None

        # Decommission 조건 (우선 평가)
        # 1. 연결 끊김
        if conn in (ConnectionState.OFFLINE, ConnectionState.CONNECTIONBROKEN):
            return CommissionState(False, False, False)

        # 2. FATAL 에러
        if state.has_fatal_error:
            return CommissionState(False, False, False)

        # 3. 비상정지
        if state.is_emergency_stopped:
            return CommissionState(False, False, False)

        # 4. 수동 모드
        if state.operating_mode in (
            OperatingMode.MANUAL,
            OperatingMode.SERVICE,
            OperatingMode.TEACHIN,
        ):
            return CommissionState(False, False, False)

        # Partial commission: SEMIAUTOMATIC
        if state.operating_mode == OperatingMode.SEMIAUTOMATIC:
            return CommissionState(False, True, True)

        # Full commission: AUTOMATIC + 정상
        return CommissionState(True, True, True)

    def is_command_completed(
        self, robot_name: str, cmd_id: int
    ) -> bool:
        """명령 완료 여부를 확인한다.

        AGV state의 nodeStates가 비어있고 driving=False이면
        내비게이션이 완료된 것으로 판단한다.
        instantAction의 경우 actionStates에서 FINISHED/FAILED를 확인한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 확인할 명령 ID.

        Returns:
            완료 여부.
        """
        with self._lock:
            if robot_name in self._completed_cmds:
                if cmd_id in self._completed_cmds[robot_name]:
                    return True

            state = self._state_cache.get(robot_name)
            order_or_action_id = (
                self._cmd_order_map.get(robot_name, {}).get(cmd_id)
            )

        if state is None or order_or_action_id is None:
            return False

        # FATAL 에러가 있으면 완료 처리하지 않음 - 작업자가 에러를 해결할 때까지 대기
        # WARNING 레벨은 AGV 동작 가능하므로 완료 처리 허용
        if state.has_fatal_error:
            return False

        # Order 완료 확인: released(base) 노드가 없고 driving=False
        # Horizon 노드는 nodeStates에 남아있을 수 있으므로
        # released 노드만 확인한다.
        if order_or_action_id.startswith('order_'):
            if state.order_id == order_or_action_id:
                has_released = any(
                    ns.released for ns in state.node_states
                )
                if not has_released and not state.driving:
                    with self._lock:
                        self._completed_cmds.setdefault(
                            robot_name, set()
                        ).add(cmd_id)
                    return True
            # Order ID가 달라졌으면 이전 주문은 완료된 것
            elif state.order_id != order_or_action_id:
                if not state.order_id or state.order_id == '':
                    with self._lock:
                        self._completed_cmds.setdefault(
                            robot_name, set()
                        ).add(cmd_id)
                    return True
        else:
            # InstantAction 완료 확인
            # FAILED는 완료로 처리하지 않음 - 작업자가 에러 해결 후
            # 로봇이 재시도하여 FINISHED가 될 때까지 대기
            for action_state in state.action_states:
                if action_state.action_id == order_or_action_id:
                    if action_state.action_status == ActionStatus.FINISHED:
                        with self._lock:
                            self._completed_cmds.setdefault(
                                robot_name, set()
                            ).add(cmd_id)
                        return True

        return False

    def _on_state_message(
        self, robot_name: str, payload: bytes
    ) -> None:
        """State 토픽 콜백."""
        try:
            raw = payload.decode('utf-8')
            state = deserialize_state(raw)
            with self._lock:
                self._state_cache[robot_name] = state
        except Exception:
            logger.exception(
                'Failed to deserialize state: robot=%s', robot_name
            )

    def _on_connection_message(
        self, robot_name: str, payload: bytes
    ) -> None:
        """Handle connection topic callback."""
        try:
            from vda5050_fleet_adapter.infra.mqtt.message_serializer import (
                deserialize_connection,
            )
            connection = deserialize_connection(payload.decode('utf-8'))
            new_state = connection.connection_state
            with self._lock:
                prev_state = self._connection_cache.get(robot_name)
                self._connection_cache[robot_name] = new_state
            logger.info(
                'Connection update: robot=%s, state=%s',
                robot_name, new_state,
            )

            # ONLINE 전환 감지 시 downloadMap 전송
            if (
                new_state == ConnectionState.ONLINE
                and prev_state != ConnectionState.ONLINE
            ):
                self._send_download_map(robot_name)
        except Exception:
            logger.exception(
                'Failed to deserialize connection: robot=%s', robot_name
            )

    def _build_topic(self, robot_name: str, topic_name: str) -> str:
        """MQTT 토픽을 생성한다.

        Args:
            robot_name: 로봇 이름.
            topic_name: 토픽 이름 (order, state, instantActions 등).

        Returns:
            '{prefix}/{robot_name}/{topic_name}' 형태.
        """
        return f'{self._prefix}/{robot_name}/{topic_name}'

    def _make_header(self, robot_name: str, topic: str) -> Header:
        """VDA5050 메시지 헤더를 생성한다.

        Args:
            robot_name: 로봇 이름.
            topic: 토픽 이름 (header ID 카운터 키).

        Returns:
            Header 인스턴스.
        """
        key = f'{robot_name}/{topic}'
        with self._lock:
            hid = self._header_ids.get(key, 0)
            self._header_ids[key] = hid + 1

        return Header(
            version=_VDA5050_VERSION,
            manufacturer=self._manufacturer,
            serial_number=robot_name,
            header_id=hid,
            timestamp=datetime.now(UTC),
        )
