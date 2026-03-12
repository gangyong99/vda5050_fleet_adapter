"""VDA5050 연결 상태 엔티티."""

from dataclasses import dataclass

from vda5050_fleet_adapter.domain.entities.header import Header
from vda5050_fleet_adapter.domain.enums import ConnectionState


@dataclass
class Connection:
    """MQTT 연결 상태 메시지.

    Args:
        header: 공통 메시지 헤더.
        connection_state: 연결 상태.
    """

    header: Header
    connection_state: ConnectionState
