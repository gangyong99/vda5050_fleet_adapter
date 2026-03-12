"""paho-mqtt 래퍼 클라이언트.

MQTT 연결 관리, 자동 재연결, Last Will 설정 등
paho-mqtt의 저수준 API를 캡슐화한다.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import threading

import paho.mqtt.client as mqtt

from vda5050_fleet_adapter.usecase.ports.config_port import MqttConfig

logger = logging.getLogger(__name__)


class MqttClient:
    """paho-mqtt 래퍼.

    Args:
        config: MQTT 브로커 접속 설정.
        client_id: MQTT 클라이언트 ID.
    """

    def __init__(self, config: MqttConfig, client_id: str = '') -> None:
        """Initialize."""
        self._config = config
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        self._lock = threading.Lock()
        self._connected = False

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._client.reconnect_delay_set(
            min_delay=1,
            max_delay=config.reconnect_max_delay_sec,
        )

        self._subscriptions: dict[
            str, tuple[Callable[[str, bytes], None], int]
        ] = {}

    @property
    def is_connected(self) -> bool:
        """MQTT 브로커 연결 여부."""
        return self._connected

    def set_last_will(
        self, topic: str, payload: str, qos: int = 1, retain: bool = True
    ) -> None:
        """Last Will 메시지를 설정한다.

        connect() 호출 전에 설정해야 한다.

        Args:
            topic: Last Will 토픽.
            payload: Last Will 페이로드.
            qos: QoS 레벨.
            retain: Retained 플래그.
        """
        self._client.will_set(topic, payload, qos=qos, retain=retain)

    def connect(self) -> None:
        """MQTT 브로커에 연결한다."""
        logger.info(
            'MQTT connecting to %s:%d',
            self._config.broker_host,
            self._config.broker_port,
        )
        self._client.connect(
            host=self._config.broker_host,
            port=self._config.broker_port,
            keepalive=self._config.keepalive_sec,
        )
        self._client.loop_start()

    def disconnect(self) -> None:
        """MQTT 브로커 연결을 종료한다."""
        logger.info('MQTT disconnecting')
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    def publish(
        self, topic: str, payload: str, qos: int = 0, retain: bool = False
    ) -> None:
        """메시지를 발행한다.

        Args:
            topic: MQTT 토픽.
            payload: JSON 페이로드 문자열.
            qos: QoS 레벨.
            retain: Retained 플래그.
        """
        with self._lock:
            result = self._client.publish(
                topic, payload.encode('utf-8'), qos=qos, retain=retain
            )
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(
                    'MQTT publish failed: topic=%s, rc=%d', topic, result.rc
                )

    def subscribe(
        self, topic: str, callback: Callable[[str, bytes], None], qos: int = 0
    ) -> None:
        """토픽을 구독한다.

        Args:
            topic: 구독할 MQTT 토픽.
            callback: 메시지 수신 콜백 (topic, payload).
            qos: QoS 레벨.
        """
        with self._lock:
            self._subscriptions[topic] = (callback, qos)
            if self._connected:
                self._client.subscribe(topic, qos=qos)
                logger.debug('MQTT subscribed: %s (qos=%d)', topic, qos)

    def unsubscribe(self, topic: str) -> None:
        """토픽 구독을 해제한다.

        Args:
            topic: 해제할 MQTT 토픽.
        """
        with self._lock:
            self._subscriptions.pop(topic, None)
            if self._connected:
                self._client.unsubscribe(topic)

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: dict,
        rc: int,
    ) -> None:
        """연결 성공 콜백."""
        if rc == 0:
            self._connected = True
            logger.info('MQTT connected to broker')
            # 재연결 시 기존 구독 복원 (저장된 QoS 사용)
            with self._lock:
                for topic, (_cb, qos) in self._subscriptions.items():
                    self._client.subscribe(topic, qos=qos)
                    logger.debug(
                        'MQTT re-subscribed: %s (qos=%d)', topic, qos
                    )
        else:
            logger.error('MQTT connection failed: rc=%d', rc)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        rc: int,
    ) -> None:
        """연결 해제 콜백."""
        self._connected = False
        if rc != 0:
            logger.warning(
                'MQTT unexpected disconnect: rc=%d, auto-reconnecting',
                rc,
            )

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: object,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """메시지 수신 콜백."""
        with self._lock:
            entry = self._subscriptions.get(msg.topic)
            callback = entry[0] if entry is not None else None

        if callback is not None:
            try:
                callback(msg.topic, msg.payload)
            except Exception:
                logger.exception(
                    'Error in MQTT message handler: topic=%s', msg.topic
                )
        else:
            logger.debug('No handler for topic: %s', msg.topic)
