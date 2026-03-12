"""RobotAPI 포트 인터페이스.

RMF fleet adapter가 AGV와 통신하기 위한 추상 인터페이스.
rmf_demos_fleet_adapter의 RobotClientAPI 패턴을 따른다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum


class RobotAPIResult(IntEnum):
    """RobotAPI 호출 결과."""

    SUCCESS = 0
    RETRY = 1
    IMPOSSIBLE = 2


@dataclass(frozen=True)
class CommissionState:
    """RMF Commission 상태.

    VDA5050 상태 기반으로 계산된 RMF commission 설정.

    Args:
        accept_dispatched_tasks: dispatch 태스크 수락 여부.
        accept_direct_tasks: direct 태스크 수락 여부.
        perform_idle_behavior: idle 행동 수행 여부.
    """

    accept_dispatched_tasks: bool = True
    accept_direct_tasks: bool = True
    perform_idle_behavior: bool = True


@dataclass
class RobotUpdateData:
    """주기적 상태 업데이트 데이터.

    Args:
        robot_name: 로봇 이름.
        map_name: 현재 맵 이름.
        position: [x, y, theta] 좌표.
        battery_soc: 배터리 충전율 (0.0-1.0).
        last_completed_cmd_id: 마지막 완료된 명령 ID.
    """

    robot_name: str
    map_name: str
    position: list[float]
    battery_soc: float
    last_completed_cmd_id: int = 0


class RobotAPI(ABC):
    """AGV 통신 인터페이스.

    RMF fleet adapter가 AGV에 명령을 보내고 상태를 조회하는 포트.
    """

    @abstractmethod
    def navigate(
        self,
        robot_name: str,
        cmd_id: int,
        nodes: list,
        edges: list,
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

    @abstractmethod
    def stop(self, robot_name: str, cmd_id: int) -> RobotAPIResult:
        """Cancel order instant action을 전송한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 명령 ID.

        Returns:
            명령 결과.
        """

    @abstractmethod
    def pause(self, robot_name: str, cmd_id: int) -> RobotAPIResult:
        """Start-pause instant action을 전송한다.

        Negotiation 발생 시 로봇을 일시정지시키기 위해 사용한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 명령 ID.

        Returns:
            명령 결과.
        """

    @abstractmethod
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
            activity: 액션 종류 (e.g. 'charge', 'teleop').
            action_params: 액션 파라미터.

        Returns:
            명령 결과.
        """

    @abstractmethod
    def get_data(self, robot_name: str) -> RobotUpdateData | None:
        """로봇의 현재 상태 데이터를 반환한다.

        Args:
            robot_name: 로봇 이름.

        Returns:
            상태 데이터 또는 아직 수신 전이면 None.
        """

    @abstractmethod
    def get_commission_state(
        self, robot_name: str
    ) -> CommissionState | None:
        """VDA5050 상태 기반 commission 상태를 반환한다.

        Args:
            robot_name: 로봇 이름.

        Returns:
            commission 상태 또는 상태 미수신 시 None.
        """

    @abstractmethod
    def is_robot_connected(self, robot_name: str) -> bool:
        """로봇의 연결 상태가 ONLINE인지 확인한다.

        연결 상태를 수신한 적이 없으면 True(연결 가정)를 반환한다.

        Args:
            robot_name: 로봇 이름.

        Returns:
            ONLINE이거나 상태 미수신이면 True, 그 외 False.
        """

    @abstractmethod
    def is_command_completed(
        self, robot_name: str, cmd_id: int
    ) -> bool:
        """명령 완료 여부를 확인한다.

        Args:
            robot_name: 로봇 이름.
            cmd_id: 확인할 명령 ID.

        Returns:
            완료 여부.
        """
