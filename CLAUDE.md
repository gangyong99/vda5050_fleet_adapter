# CLAUDE.md - VDA5050 Fleet Adapter Project Rules

## Project Overview
VDA5050 Fleet Adapter: ROS 2 (Jazzy) + Open-RMF fleet adapter bridging VDA5050 AGVs via MQTT.

## Reference Implementation
- Fleet adapter 구현 시 [rmf_demos_fleet_adapter](https://github.com/open-rmf/rmf_demos/tree/main/rmf_demos_fleet_adapter)를 참조할 것
- Fleet adapter 구현 시 [vda5050_fleet_adapter](https://github.com/mrceki/vda5050_fleet_adapter/tree/main/vda5050_fleet_adapter)를 참조할 것 

## Tech Stack
- Python 3.12+ / ROS 2 Jazzy Jalisco (Ubuntu 24.04)
- `rmf_fleet_adapter_python`, `rclpy`, MQTT (paho-mqtt)
- Build: `ament_python` / `colcon`

## Architecture: Clean Architecture
```
vda5050_fleet_adapter/
  domain/         # Entities, Value Objects, Domain Events (no external deps)
  usecase/        # Application logic, Port interfaces (ABC)
  infra/          # Adapters: MQTT client, ROS 2 nodes, config loaders
  presentation/   # Entry points, CLI, ROS 2 launch integration
```
- Dependencies flow inward only: infra -> usecase -> domain
- Domain layer MUST NOT import rclpy, paho-mqtt, or any framework
- Use Port/Adapter (ABC interfaces in usecase/, implementations in infra/)

## Coding Rules

### Style
- PEP 8 strict, enforced by flake8
- Line length: 99 characters max
- Docstrings: Google style, PEP 257 compliant
- Type hints required on all public functions/methods
- snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE for constants

### Naming Conventions
- ROS 2 nodes: `vda5050_` prefix (e.g., `vda5050_fleet_adapter_node`)
- MQTT topics: follow VDA5050 spec (`/interfaceName/version/manufacturer/serialNumber/topic`)
- Config keys: snake_case in YAML

### Error Handling
- Never use bare `except:`; always catch specific exceptions
- ROS 2 logging (`self.get_logger()`) for node-level logging
- Python `logging` module for non-ROS components
- Log levels: DEBUG for protocol details, INFO for state changes, WARN for recoverable errors, ERROR for failures

### Testing
- pytest for unit tests, launch_testing for integration
- Unit tests MUST NOT depend on ROS 2 runtime or MQTT broker
- Mock external dependencies at Port boundaries
- Test file naming: `test_<module_name>.py`

### VDA5050 Specific
- All VDA5050 message models defined as dataclasses in domain/
- Strict validation of VDA5050 JSON schemas on send/receive
- AGV state machine transitions must be explicit and logged

## Build & Test Commands
```bash
# Build
cd ~/rmf_ws && colcon build --packages-select vda5050_fleet_adapter

# Test
colcon test --packages-select vda5050_fleet_adapter
colcon test-result --verbose

# Lint
cd ~/rmf_ws/src/vda5050_fleet_adapter && python -m flake8
python -m pytest test/
```

## Workflow
- 작업이 완료되면 자동으로 git commit을 수행할 것 (사용자가 별도로 요청하지 않아도)

## Key Constraints
- Do NOT add ROS 2 message type definitions here; use existing rmf_fleet_msgs
- MQTT QoS: use QoS 1 for state/visualization, QoS 2 for orders/instant actions
- All config values must be loadable from YAML parameters, no hardcoded values
- Thread safety: use `threading.Lock` for shared state between MQTT callbacks and ROS 2 callbacks

## VDA5050 Order 생성 규칙

### Order 단위
- rmf의 한개의 Task가 하나의 order 단위가 되어야한다. 예를 들어 rmf에 go_to_place명령이 들어올경우 로봇으로 전달 되는 orderID는 하나여야 한다.
- 예외사항 : rmf core의 기능을 통해 로봇이 다른 로봇 및 특정상황에서 기존 경로가 변경이 일어날경우 기존 order를 cancel 시키고 다른 orderid로 새로 내린다.

### 3-Tier 경로 생성 구조 (구현 완료)
order 경로는 3개의 Tier로 구성된다 (경로 조립 관점):
- **Tier 1 (Horizon - RMF 경로)**: 현재 위치 → RMF가 제공한 경로 끝까지. `released=False`.
- **Tier 2 (Horizon - 최종목적지 확장)**: RMF 경로 끝 → 최종 목적지까지. `released=False`. 최종목적지가 이미 경로에 포함되어 있으면 생략.
- **Tier 3 (Base)**: 현재 위치 → goal_node(destination)까지. `released=True`로 설정되어 즉시 실행.

최종 VDA5050 order에서는 Base(Tier 3)가 앞, Horizon(Tier 1, 2)이 뒤에 배치된다.
order는 무조건 최종목적지까지 node가 다 있어야한다. Tier 2로 추가된 경로는 다음 destination 도착 후 재계산되므로 부정확해도 괜찮다.

### 경로 데이터 소스 (구현 완료)
- `destination.waypoint_names` 속성을 사용하여 RMF가 계산한 경로를 받는다 (planned_path topic 대신).
- EasyFullControl C++에서 navigate() 콜백 시 전체 waypoint 시퀀스를 제공한다.
- waypoint_names가 없거나 유효하지 않으면 `compute_path()`로 fallback.
- **최종 목적지**: `destination.final_name` 속성으로 파악. cart_delivery처럼 phase가 2개 이상인 경우, 각 phase의 목적지가 최종 목적지가 된다.

### 경로 보간 (Sparse Path Interpolation, 구현 완료)
- RMF의 waypoint_names가 sparse할 수 있음 (예: `[1, 3, 5]` → 중간 노드 누락).
- `_interpolate_path()` 메서드가 인접하지 않은 waypoint 쌍 사이에 `compute_path()`로 중간 노드를 채운다.
- nav_graph에 직접 edge가 있으면 그대로 사용, 없으면 최단 경로로 보간.

### 브리지 경로 (Bridge Path, 구현 완료)
- 로봇의 현재 위치(start_node)가 RMF 경로의 시작점과 다를 경우:
  - start_node가 rmf_path 안에 있으면 → 해당 인덱스부터 사용
  - start_node가 rmf_path 밖이면 → `compute_path()`로 start_node → rmf_path[0] 브리지 경로 생성 후 연결

### Order Update 규칙 (구현 완료)
- 같은 Task 내에서 새로운 Destination이 내려오면 → `order_update_id++`, 같은 `order_id` 유지
- 새로운 Task이면 → 새로운 `order_id` 생성, `order_update_id = 0`
- Order update 시 stitching: 이전 order의 마지막 Base node의 sequenceId(`_last_stitch_seq_id`)를 다음 order의 시작점으로 사용하여 AGV가 끊김 없이 전환

### SequenceId 규칙 (구현 완료)
- Node: 짝수 sequenceId (0, 2, 4, 6, ...)
- Edge: 홀수 sequenceId (1, 3, 5, 7, ...)
- Order update 시 `seq_start = _last_stitch_seq_id`로 연속성 유지
- Base/Horizon 분리: Node는 `i <= base_end_index`이면 released, Edge는 `i < base_end_index`이면 released

### Order 예시
- 최종목적지 = 5, 로봇 출발지 1, 중간 경유지 2,3,4
- rmf core에서 받은 경로가 [1,2,3,4]이고 첫번째 destination이 3이면: 1(base)-2(base)-3(base)-4(horizon, rmf경로)-5(horizon, 최종목적지까지 추가)
- 3번 까지 도착 후 rmf core에서 받은 경로가 [3,4,5]이고 두번째 destination이 4이면: 3(base)-4(base)-5(horizon, rmf경로)
- 4번 까지 도착 후 rmf core에서 받은 경로가 [4,5]이고 세번째 destination이 5이면: 4(base)-5(base)

## Negotiation 처리 규칙 (구현 완료)
rmf에서 negotiation이 발생하면 아래 순서를 따른다:
1. RMF가 `stop()` 호출 → `startPause` instantAction을 로봇에 전송, `_is_paused_for_negotiation = True`
2. RMF가 새로운 경로로 `navigate()` 호출 → `cancelOrder` instantAction 전송
3. 1초 대기 후 새로운 `orderID`로 order 생성하여 로봇을 움직인다.
4. `_is_paused_for_negotiation` 플래그로 negotiation 상태를 추적하여 cancel → new order 시퀀스를 보장한다.

## 도착 감지 (Arrival Detection, 구현 완료)
- **navigate 명령**: 거리 기반 도착 감지 (`arrival_threshold`, 기본 0.5m). VDA5050 state의 position과 목적지 좌표 간 유클리드 거리가 threshold 이하이면 도착으로 판단.
- **execute_action 명령**: VDA5050 state의 action_states에서 action_id의 상태가 FINISHED/FAILED인지 확인.
- navigate 완료는 RMF의 책임이므로, VDA5050의 Base node 진행 상태가 아닌 거리 기반으로 빠르게 피드백.

### Theta 기반 도착 판정 (구현 완료)
- Base 도착 노드 이후에 Horizon이 있고, 진입/진출 heading 간 회전각이 `turn_angle_threshold`(기본 15°) 이상이면 theta 조건을 추가.
- `build_vda5050_nodes_edges()`에서 Base 노드의 `NodePosition.theta`를 진출 heading + edge orientation으로 설정.
- `update()`에서 거리 조건 통과 후 `_navigate_target_theta`가 설정되어 있으면 로봇의 현재 heading과 비교, `allowed_deviation_theta`(기본 15°) 이내여야 도착으로 판정.
- theta 미설정(직진 구간, base가 첫/마지막 노드) 시 기존 거리 기반 도착 동작 유지.
- 설정: `config.yaml`의 `rmf_fleet.turn_angle_threshold` (degree), `rmf_fleet.allowed_deviation_theta` (degree).

## Execute Action as NodeAction (구현 완료)
- cart_delivery 등에서 execute_action(pickup/dropoff)이 호출될 때, 활성 order가 있으면 instantAction 대신 **order update의 nodeAction**으로 전송.
- 현재 위치의 가장 가까운 노드에 `BlockingType.HARD` action을 붙여 order update로 전송.
- 현재 노드만 Base(released), 최종 목적지까지의 나머지 경로는 Horizon으로 구성.
- `track_action_id`를 사용하여 action 완료를 추적 (order_id가 아닌 action_id로 모니터링).

## pickDrop Base/Horizon 분리 (구현 완료)
nav_graph에서 `pickDrop: true` 속성이 있는 destination 노드의 경우:

### 동작 원리
- **navigate()**: pickDrop destination을 horizon(unreleased)으로 유지, 직전 노드까지만 base. 도착 판정도 직전 노드 좌표 기준.
- **execute_action()**: `_pick_drop_destination`이 설정된 경우 `_build_pick_drop_order_update()` 사용:
  - 경로: current_node → pickDrop destination (compute_path 사용)
  - 모든 노드 base (released). Action을 마지막 노드(pickDrop dest)에 부착.
  - 전송 후 order 라이프사이클 즉시 리셋 (`_active_order_id = None` 등).
- **로봇이 이미 dest에 있는 경우**: path가 [dest] 1개이면 order 미생성, 즉시 `execution.finished()`.

### Order Lifecycle
- Phase 1 (navigate to pickup) + Phase 2 (pick action) = **order_A**
- Phase 3 (navigate to dropoff) + Phase 4 (drop action) = **order_B** (별도 orderID)
- Phase 2/4에서 `_build_pick_drop_order_update()` 실행 시 order 리셋 → Phase 3이 새 orderID 생성.

### Order 예시
```
Phase 1 (navigate): wp1(base,seq=0) → wp2(horizon,seq=2)   [order_A, updateId=0]
Phase 2 (pick):     wp1(base,seq=0) → wp2(base,seq=2,pick) [order_A, updateId=1]
  → order 리셋
Phase 3 (navigate): wp2(base,seq=0) → wp3(horizon,seq=2)   [order_B, updateId=0]
Phase 4 (drop):     wp2(base,seq=0) → wp3(base,seq=2,drop) [order_B, updateId=1]
  → order 리셋
```

### 엣지케이스
- **go_to_place 리셋**: pickDrop pending 상태에서 task 종료 → `_reset_order_state()`에서 cancelOrder 전송.
- **nav_graph 설정**: pickup/dropoff 스테이션에 `pickDrop: true` 속성 필수.

## pickDrop Station Node Removal (구현 완료)
pickDrop 속성이 destination의 **직전 노드**(staging node)에 있고, destination 자체는 실제 카트/드롭 위치(station node)인 시나리오. Charging 패턴과 동일하게 station node를 VDA5050 order에서 제거.

### 동작 원리
- **navigate()**: path[-2]가 pickDrop이면 path[-1](station node)을 제거, staging node까지만 경로 생성.
  - `_pick_drop_station_node`에 제거된 station node 저장.
  - `_pick_drop_destination`을 staging node로 설정 → 기존 pickDrop 로직 자동 적용.
  - `target`과 `_final_destination`을 staging node로 갱신 → Tier 2 확장 방지.
- **execute_action()**: `stationName`은 RMF Task 파라미터에서 직접 제공 (auto-fill 없음). `drop` action은 항상 `stationName` 포함.
- **_build_pick_drop_order_update()**: 리셋 시 `_pick_drop_station_node = None`.

### Station Node Removal 조건
- `_pick_drop_destination is None` (dest 자체에 pickDrop이 있는 기존 시나리오와 충돌 방지)
- `len(path) >= 2`
- `path[-2]`의 nav_graph 속성에 `pickDrop: True`

### Order 예시 (Station Node Removal)
```
경로: wp1-wp2-wp3(pickDrop)-wp4(station)-wp3-wp2-wp5(pickDrop)-wp6(station)

Phase 1 (navigate to pick):
  RMF: navigate(dest=wp4)
  → station node wp4 제거, path=[wp1,wp2,wp3]
  VDA5050: wp1(base)→wp2(base)→wp3(horizon)  [order_A, updateId=0]
  → wp2 도착 → execution.finished()

Phase 2 (pick action):
  RMF: execute_action('pick', {})
  VDA5050: wp2(base)→wp3(base,pick)  [order_A, updateId=1]
  → order 리셋

Phase 3 (navigate to drop):
  RMF: navigate(dest=wp6)
  → station node wp6 제거, path=[...,wp5]
  VDA5050: wp3(base)→...→wp5(horizon)  [order_B, updateId=0]
  → pre-staging 도착 → execution.finished()

Phase 4 (drop action):
  RMF: execute_action('drop', {})
  → stationName은 RMF Task params에서 제공
  VDA5050: ...→wp5(base,drop+stationName=wp6)  [order_B, updateId=1]
  → order 리셋
```

## Robot Connection 관리 (구현 완료)
- VDA5050 connection topic을 구독하여 로봇별 연결 상태(`ConnectionState`)를 캐싱.
- `is_robot_connected()`: navigate 등 명령 전송 전 pre-flight check. 미연결 시 `RETRY` 반환.
- Fleet adapter 시작 시 로봇이 연결되지 않은 상태면 RMF에 `add_robot`하지 않음.

## downloadMap instantAction (구현 완료)
- 로봇이 ONLINE으로 연결(또는 재연결)될 때 `downloadMap` instantAction을 자동 전송.
- `config.yaml`의 `download_map` 섹션에서 설정. 섹션이 없으면 비활성화.
- actionParameters: `mapId`, `mapDownloadUrl`, `mapVersion`.
- `is_download_map_ready()`로 action 완료(FINISHED/FAILED)를 확인, 미완료 시 navigate가 RETRY.

## Commission 자동 업데이트 (구현 완료)
- VDA5050 state 기반으로 RMF commission을 자동 갱신:
  - `OFFLINE`/`CONNECTIONBROKEN`, FATAL error, Emergency stop, Manual/Service/TeachIn mode → 전체 decommission (dispatched=false, direct=false, idle=false)
  - `SEMIAUTOMATIC` → 부분 commission (dispatched=false, direct=true, idle=true)
  - `AUTOMATIC` + 정상 → 전체 commission (dispatched=true, direct=true, idle=true)

## Order Validation 규칙 (domain/entities/order.py)
- order_id 비어있으면 안됨
- nodes 비어있으면 안됨
- Node의 sequenceId는 짝수, Edge의 sequenceId는 홀수
- Edge의 start_node_id/end_node_id가 nodes 목록에 존재해야 함
- Base → Horizon 순서만 허용 (Horizon 이후 Base node 불가)