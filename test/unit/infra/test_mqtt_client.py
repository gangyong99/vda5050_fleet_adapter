"""MqttClient 유닛 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from vda5050_fleet_adapter.infra.mqtt.mqtt_client import MqttClient
from vda5050_fleet_adapter.usecase.ports.config_port import MqttConfig


@pytest.fixture
def config():
    """Create test MQTT configuration."""
    return MqttConfig(
        broker_host='localhost',
        broker_port=1883,
        keepalive_sec=60,
        reconnect_max_delay_sec=30,
    )


@pytest.fixture
def client(config):
    """Create test MQTT client with mocked paho client."""
    with patch(
        'vda5050_fleet_adapter.infra.mqtt.mqtt_client.mqtt.Client'
    ) as MockPaho:
        mock_paho = MagicMock()
        MockPaho.return_value = mock_paho
        mqtt_client = MqttClient(config, client_id='test')
        mqtt_client._paho = mock_paho
        yield mqtt_client


class TestSubscribeStoresQos:
    """subscribe() QoS 저장 테스트."""

    def test_subscribe_stores_qos(self, client):
        """subscribe가 callback과 QoS를 함께 저장한다."""
        cb = MagicMock()
        client.subscribe('test/topic', cb, qos=1)

        assert 'test/topic' in client._subscriptions
        stored_cb, stored_qos = client._subscriptions['test/topic']
        assert stored_cb is cb
        assert stored_qos == 1

    def test_subscribe_stores_default_qos_0(self, client):
        """기본 QoS 0이 저장된다."""
        cb = MagicMock()
        client.subscribe('test/topic', cb)

        _, stored_qos = client._subscriptions['test/topic']
        assert stored_qos == 0

    def test_unsubscribe_removes_entry(self, client):
        """unsubscribe가 저장된 항목을 제거한다."""
        cb = MagicMock()
        client.subscribe('test/topic', cb, qos=1)
        client.unsubscribe('test/topic')

        assert 'test/topic' not in client._subscriptions


class TestReconnectRestoresQos:
    """재연결 시 QoS 복원 테스트."""

    def test_reconnect_restores_qos(self, client):
        """재연결 시 저장된 QoS로 재구독한다."""
        cb1 = MagicMock()
        cb2 = MagicMock()
        client.subscribe('topic/a', cb1, qos=0)
        client.subscribe('topic/b', cb2, qos=1)

        # 연결 콜백 시뮬레이션
        client._on_connect(client._client, None, {}, 0)

        subscribe_calls = client._client.subscribe.call_args_list
        topics_qos = {
            call[0][0]: call[1]['qos']
            for call in subscribe_calls
        }
        assert topics_qos.get('topic/a') == 0
        assert topics_qos.get('topic/b') == 1
