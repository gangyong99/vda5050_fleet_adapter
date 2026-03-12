# VDA5050 통신 프로토콜 정의서

> VDA5050 v2.0 기반 AGV-Master Control 통신 프로토콜 정리
>
> 원본 스펙: [VDA5050/VDA5050_EN.md](https://github.com/VDA5050/VDA5050/blob/main/VDA5050_EN.md)

---

## 1. 프로토콜 개요

| 항목 | 내용 |
|------|------|
| 프로토콜 | MQTT 3.1.1 이상 |
| 페이로드 | JSON (UTF-8) |
| 인코딩 | UTF-8 |
| ID 허용 문자 | `A-Z`, `a-z`, `0-9`, `_`, `-`, `.`, `:` (`/`, `$` 금지) |

### 1.1 통신 방향

```
┌──────────────┐         MQTT Broker         ┌──────────────┐
│              │  ── order ──────────────→    │              │
│    Master    │  ── instantActions ─────→    │     AGV      │
│   Control    │                              │              │
│   (RMF)     │  ←────────────── state ──    │              │
│              │  ←──────── visualization ── │              │
│              │  ←─────────── connection ── │              │
│              │  ←──────────── factsheet ── │              │
└──────────────┘                              └──────────────┘
```

---

## 2. MQTT 토픽 구조

### 2.1 토픽 네이밍 규칙

```
{interfaceName}/{majorVersion}/{manufacturer}/{serialNumber}/{topic}
```

**예시:**
```
uagv/v2/RobotCompany/AGV-001/order
uagv/v2/RobotCompany/AGV-001/instantActions
uagv/v2/RobotCompany/AGV-001/state
uagv/v2/RobotCompany/AGV-001/visualization
uagv/v2/RobotCompany/AGV-001/connection
uagv/v2/RobotCompany/AGV-001/factsheet
```

### 2.2 토픽별 상세

| Topic | 방향 | 설명 | QoS | Retained |
|-------|------|------|-----|----------|
| `order` | Master → AGV | 주행 명령 (그래프 기반) | 0 | No |
| `instantActions` | Master → AGV | 즉시 실행 액션 | 0 | No |
| `state` | AGV → Master | 차량 상태 보고 | 0 | No |
| `visualization` | AGV → Systems | 고빈도 위치 데이터 | 0 | No |
| `connection` | AGV/Broker → Master | 연결 상태 (Last Will) | 1 | Yes |
| `factsheet` | AGV → Master | 차량 사양/능력 정보 | 0 | No |

---

## 3. 공통 헤더 (Header)

모든 메시지는 다음 헤더 필드를 포함한다:

```json
{
  "headerId": 1234,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "2.0.0",
  "manufacturer": "RobotCompany",
  "serialNumber": "AGV-001"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `headerId` | uint32 | O | 토픽별 증가 카운터 |
| `timestamp` | string (ISO 8601) | O | UTC 시간 `YYYY-MM-DDTHH:mm:ss.ffZ` |
| `version` | string | O | 프로토콜 버전 `Major.Minor.Patch` |
| `manufacturer` | string | O | AGV 제조사명 |
| `serialNumber` | string | O | AGV 고유 식별자 |

---

## 4. Order 메시지 (Master → AGV)

주행 명령을 방향 그래프(Node + Edge)로 전달한다.

### 4.1 Order 구조

```json
{
  "headerId": 1,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "2.0.0",
  "manufacturer": "RobotCompany",
  "serialNumber": "AGV-001",
  "orderId": "order-001",
  "orderUpdateId": 0,
  "zoneSetId": "zone-set-1",
  "nodes": [],
  "edges": []
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `orderId` | string | O | 주문 고유 ID |
| `orderUpdateId` | uint32 | O | 주문 업데이트 번호 (증가) |
| `zoneSetId` | string | X | 사용할 구역 세트 ID |
| `nodes` | Node[] | O | 노드 배열 |
| `edges` | Edge[] | O | 엣지 배열 |

### 4.2 Base와 Horizon

```
├─── Base (released=true) ──┤──── Horizon (released=false) ────┤
  Node0 → Edge0 → Node1 → Edge1 → Node2 → Edge2 → Node3
  [AGV 즉시 주행]                   [경로 예약, 교통 제어용]
```

- **Base**: `released=true` — AGV가 즉시 주행해야 하는 구간
- **Horizon**: `released=false` — 교통 제어를 위한 미래 경로 (변경 가능)

### 4.3 Node 구조

```json
{
  "nodeId": "node-001",
  "sequenceId": 0,
  "released": true,
  "nodePosition": {
    "x": 10.5,
    "y": 20.3,
    "theta": 1.57,
    "allowedDeviationXY": 0.5,
    "allowedDeviationTheta": 0.1,
    "mapId": "map-floor1"
  },
  "actions": []
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `nodeId` | string | O | 노드 고유 ID |
| `sequenceId` | uint32 | O | 그래프 내 순서 (짝수: 0, 2, 4...) |
| `released` | bool | O | Base 여부 |
| `nodePosition` | object | X | 위치 정보 (첫 주문 시 필수) |
| `nodePosition.x` | float | O | X 좌표 (m) |
| `nodePosition.y` | float | O | Y 좌표 (m) |
| `nodePosition.theta` | float | X | 방향 (rad), -PI ~ PI |
| `nodePosition.allowedDeviationXY` | float | X | 허용 위치 오차 (m) |
| `nodePosition.allowedDeviationTheta` | float | X | 허용 방향 오차 (rad) |
| `nodePosition.mapId` | string | O | 맵 ID |
| `actions` | Action[] | O | 노드 도착 시 실행할 액션 |

### 4.4 Edge 구조

```json
{
  "edgeId": "edge-001",
  "sequenceId": 1,
  "released": true,
  "startNodeId": "node-001",
  "endNodeId": "node-002",
  "maxSpeed": 2.0,
  "orientation": 0.0,
  "rotationAllowed": true,
  "trajectory": null,
  "corridor": {
    "leftWidth": 1.0,
    "rightWidth": 1.0,
    "corridorRefPoint": "KINEMATICCENTER"
  },
  "actions": []
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `edgeId` | string | O | 엣지 고유 ID |
| `sequenceId` | uint32 | O | 그래프 내 순서 (홀수: 1, 3, 5...) |
| `released` | bool | O | Base 여부 |
| `startNodeId` | string | O | 시작 노드 ID |
| `endNodeId` | string | O | 종료 노드 ID |
| `maxSpeed` | float | X | 최대 속도 (m/s) |
| `orientation` | float | X | 주행 방향 (rad) |
| `rotationAllowed` | bool | X | 회전 허용 여부 |
| `trajectory` | object | X | NURBS 경로 정의 |
| `corridor` | object | X | 장애물 회피 경계 |
| `actions` | Action[] | O | 엣지 주행 중 실행할 액션 |

### 4.5 Order 업데이트 규칙

1. 동일 `orderId`에 대해 `orderUpdateId`를 증가시켜 전송
2. **Stitching Node**: 이전 Base의 마지막 노드 = 새 Base의 첫 노드
3. Horizon 영역은 자유롭게 변경 가능
4. Base 영역 변경 시 반드시 이전 Base의 마지막 노드에서 연결

### 4.6 Order 검증 순서

```
1. JSON 포맷 유효성 검증
2. 신규 주문 vs 기존 주문 업데이트 판별
3. 차량 상태가 주문 수락 가능한지 확인
4. 시작 위치 도달 가능 여부 확인
5. orderUpdateId 시퀀스 검증
6. 연결 유효성 (stitching) 확인
```

---

## 5. Instant Actions 메시지 (Master → AGV)

주문 흐름 외부에서 즉시 실행하는 액션 명령이다.

```json
{
  "headerId": 5,
  "timestamp": "2024-01-15T10:31:00.000Z",
  "version": "2.0.0",
  "manufacturer": "RobotCompany",
  "serialNumber": "AGV-001",
  "actions": [
    {
      "actionType": "startPause",
      "actionId": "action-uuid-001",
      "blockingType": "HARD",
      "actionParameters": []
    }
  ]
}
```

---

## 6. Action 시스템

### 6.1 Action 구조

```json
{
  "actionType": "pick",
  "actionId": "action-uuid-002",
  "blockingType": "HARD",
  "actionDescription": "Pick up pallet",
  "actionParameters": [
    {
      "key": "stationType",
      "value": "floor"
    },
    {
      "key": "loadType",
      "value": "EPAL"
    }
  ]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `actionType` | string | O | 액션 종류 식별자 |
| `actionId` | string | O | 고유 ID (UUID 권장) |
| `blockingType` | string | O | 블로킹 유형 |
| `actionDescription` | string | X | 액션 설명 |
| `actionParameters` | object[] | X | 액션별 파라미터 |

### 6.2 Blocking Type

| 타입 | 설명 |
|------|------|
| `NONE` | 주행과 병렬 실행 가능 |
| `SOFT` | 다른 액션과 병렬 가능, 주행은 차단 |
| `HARD` | 이 액션만 단독 실행 (주행 + 다른 액션 모두 차단) |

### 6.3 Action 상태 전이

```
                    ┌──────────────┐
                    │   WAITING    │  (노드/엣지 도달 대기)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ INITIALIZING │  (액션 초기화 중)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
               ┌───→│   RUNNING    │←──┐
               │    └──┬───────┬───┘   │
               │       │       │       │
        ┌──────┴──┐    │    ┌──▼───────┴─┐
        │  PAUSED │←───┘    │   FAILED    │
        └─────────┘         └─────────────┘
               │
        ┌──────▼──────┐
        │  FINISHED   │
        └─────────────┘
```

### 6.4 사전 정의 액션 (Predefined Actions)

#### 이동 제어

| 액션 | 설명 | blockingType |
|------|------|-------------|
| `startPause` | 일시 정지 | HARD |
| `stopPause` | 일시 정지 해제 | HARD |
| `cancelOrder` | 현재 주문 취소 | HARD |

#### 충전

| 액션 | 설명 | blockingType |
|------|------|-------------|
| `startCharging` | 충전 시작 | HARD |
| `stopCharging` | 충전 중지 | HARD |

#### 화물 처리

| 액션 | 설명 | blockingType |
|------|------|-------------|
| `pick` | 화물 적재 | HARD |
| `drop` | 화물 하역 | HARD |

#### 위치/맵

| 액션 | 설명 | blockingType |
|------|------|-------------|
| `initPosition` | 위치 초기화 (로컬라이제이션 오버라이드) | HARD |
| `finePositioning` | 정밀 위치 정렬 | HARD |
| `downloadMap` | 맵 다운로드 | NONE |
| `enableMap` | 맵 활성화 | NONE |
| `deleteMap` | 맵 삭제 | NONE |

#### 기타

| 액션 | 설명 | blockingType |
|------|------|-------------|
| `waitForTrigger` | 외부 트리거 대기 | HARD |
| `factsheetRequest` | Factsheet 요청 | NONE |

---

## 7. State 메시지 (AGV → Master)

AGV의 전체 상태를 보고한다. 상태 변경 시 또는 최대 30초 간격으로 발행한다.

### 7.1 발행 트리거 이벤트

- 주문 수신/업데이트
- 화물 상태 변경
- 에러/경고 발생 또는 해제
- 노드 통과
- 운영 모드 변경
- 주행 상태 변경
- 맵 업데이트

### 7.2 State 전체 구조

```json
{
  "headerId": 100,
  "timestamp": "2024-01-15T10:30:05.000Z",
  "version": "2.0.0",
  "manufacturer": "RobotCompany",
  "serialNumber": "AGV-001",

  "orderId": "order-001",
  "orderUpdateId": 0,
  "lastNodeId": "node-001",
  "lastNodeSequenceId": 0,

  "driving": true,
  "newBaseRequest": false,
  "distanceSinceLastNode": 2.5,

  "operatingMode": "AUTOMATIC",
  "paused": false,

  "nodeStates": [],
  "edgeStates": [],
  "actionStates": [],

  "agvPosition": {
    "x": 12.3,
    "y": 21.0,
    "theta": 1.57,
    "mapId": "map-floor1",
    "positionInitialized": true,
    "localizationScore": 0.95
  },

  "velocity": {
    "vx": 1.0,
    "vy": 0.0,
    "omega": 0.0
  },

  "loads": [],
  "batteryState": {
    "batteryCharge": 85.0,
    "batteryVoltage": 48.2,
    "charging": false,
    "reach": 5000
  },

  "errors": [],
  "information": [],
  "safetyState": {
    "eStop": "NONE",
    "fieldViolation": false
  },

  "maps": []
}
```

### 7.3 주요 필드 상세

#### 주문 진행 상태

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `orderId` | string | O | 현재 실행 중인 주문 ID (없으면 빈 문자열) |
| `orderUpdateId` | uint32 | O | 현재 주문 업데이트 번호 |
| `lastNodeId` | string | O | 마지막 통과/현재 위치 노드 ID |
| `lastNodeSequenceId` | uint32 | O | 마지막 노드의 시퀀스 ID |
| `driving` | bool | O | 주행 중 여부 |
| `newBaseRequest` | bool | O | 새 Base 요청 (Base 끝에 근접 시 true) |
| `distanceSinceLastNode` | float | X | 마지막 노드 이후 이동 거리 (m) |

#### 위치 및 속도

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `agvPosition.x` | float | O | X 좌표 (m) |
| `agvPosition.y` | float | O | Y 좌표 (m) |
| `agvPosition.theta` | float | O | 방향 (rad) |
| `agvPosition.mapId` | string | O | 현재 맵 ID |
| `agvPosition.positionInitialized` | bool | O | 로컬라이제이션 초기화 여부 |
| `agvPosition.localizationScore` | float | X | 로컬라이제이션 품질 (0.0~1.0) |
| `velocity.vx` | float | X | X 방향 속도 (m/s) |
| `velocity.vy` | float | X | Y 방향 속도 (m/s) |
| `velocity.omega` | float | X | 각속도 (rad/s) |

#### 운영 모드

| 모드 | 설명 |
|------|------|
| `AUTOMATIC` | Master 완전 제어 (정상 운영) |
| `SEMIAUTOMATIC` | Master 제어 + 운전자 속도 오버라이드 |
| `MANUAL` | HMI 수동 제어 |
| `SERVICE` | 유지보수 모드 |
| `TEACHIN` | 맵핑/설정 모드 |

#### nodeStates / edgeStates

남은 노드/엣지의 상태를 배열로 보고한다. 노드 통과 시 해당 노드는 배열에서 제거된다.

```json
{
  "nodeStates": [
    {
      "nodeId": "node-002",
      "sequenceId": 2,
      "released": true,
      "nodeDescription": "Station A"
    }
  ],
  "edgeStates": [
    {
      "edgeId": "edge-001",
      "sequenceId": 1,
      "released": true,
      "edgeDescription": "Path to Station A"
    }
  ]
}
```

#### actionStates

```json
{
  "actionStates": [
    {
      "actionId": "action-uuid-002",
      "actionType": "pick",
      "actionDescription": "Pick up pallet",
      "actionStatus": "RUNNING",
      "resultDescription": ""
    }
  ]
}
```

| actionStatus | 설명 |
|-------------|------|
| `WAITING` | 실행 대기 (노드/엣지 미도달) |
| `INITIALIZING` | 초기화 중 |
| `RUNNING` | 실행 중 |
| `PAUSED` | 일시 정지 |
| `FINISHED` | 완료 |
| `FAILED` | 실패 |

#### 배터리 상태

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `batteryState.batteryCharge` | float | O | 충전율 (%) |
| `batteryState.batteryVoltage` | float | X | 전압 (V) |
| `batteryState.batteryHealth` | float | X | 배터리 건강도 (%) |
| `batteryState.charging` | bool | O | 충전 중 여부 |
| `batteryState.reach` | uint32 | X | 예상 주행 가능 거리 (m) |

#### 화물 상태

```json
{
  "loads": [
    {
      "loadId": "load-001",
      "loadType": "EPAL",
      "loadPosition": "front",
      "boundingBoxReference": { "x": 0.0, "y": 0.0, "z": 0.5, "theta": 0.0 },
      "loadDimensions": { "length": 1.2, "width": 0.8, "height": 1.0 },
      "weight": 500.0
    }
  ]
}
```

#### 에러 및 정보

```json
{
  "errors": [
    {
      "errorType": "orderError",
      "errorLevel": "WARNING",
      "errorDescription": "Order validation failed: invalid nodeId",
      "errorHint": "Check nodeId format",
      "errorReferences": [
        { "referenceKey": "nodeId", "referenceValue": "node-999" }
      ]
    }
  ],
  "information": [
    {
      "infoType": "general",
      "infoLevel": "INFO",
      "infoDescription": "AGV reached charging station"
    }
  ]
}
```

| errorLevel | 설명 |
|-----------|------|
| `WARNING` | AGV 동작 가능, 주의 필요 |
| `FATAL` | AGV 동작 불가, 즉각 조치 필요 |

#### 안전 상태

```json
{
  "safetyState": {
    "eStop": "NONE",
    "fieldViolation": false
  }
}
```

| eStop 값 | 설명 |
|----------|------|
| `AUTOACK` | 자동 복구 비상 정지 |
| `MANUAL` | 수동 복구 비상 정지 |
| `REMOTE` | 원격 비상 정지 |
| `NONE` | 비상 정지 아님 |

#### 맵 상태

```json
{
  "maps": [
    { "mapId": "map-floor1", "mapVersion": "1.0", "mapStatus": "ENABLED" },
    { "mapId": "map-floor2", "mapVersion": "2.1", "mapStatus": "DISABLED" }
  ]
}
```

| mapStatus | 설명 |
|----------|------|
| `ENABLED` | 활성화 (mapId당 하나만 가능) |
| `DISABLED` | 비활성화 |

---

## 8. Visualization 메시지 (AGV → Systems)

State와 동일한 구조이나, 고빈도로 위치 데이터만 전송한다. 시각화/모니터링 시스템용이며 Master Control 로직에는 사용하지 않는다.

---

## 9. Connection 메시지 (연결 관리)

### 9.1 구조

```json
{
  "headerId": 1,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "2.0.0",
  "manufacturer": "RobotCompany",
  "serialNumber": "AGV-001",
  "connectionState": "ONLINE"
}
```

### 9.2 연결 상태

| 상태 | 발신자 | 설명 |
|------|--------|------|
| `ONLINE` | AGV | MQTT 연결 직후 AGV가 발행 |
| `OFFLINE` | AGV | 정상 종료 시 disconnect 전 발행 |
| `CONNECTIONBROKEN` | Broker | 비정상 연결 끊김 시 Last Will로 발행 |

### 9.3 Last Will 설정

AGV는 MQTT 연결 시 Last Will 메시지를 설정한다:
- **Topic**: `uagv/v2/{manufacturer}/{serialNumber}/connection`
- **Payload**: `connectionState: "CONNECTIONBROKEN"`
- **QoS**: 1
- **Retained**: true

### 9.4 연결 흐름

```
AGV 시작
  │
  ├─ MQTT Connect (Last Will 설정: CONNECTIONBROKEN)
  │
  ├─ connection 토픽에 "ONLINE" 발행 (retained, QoS 1)
  │
  ├─ ... 정상 운영 ...
  │
  ├─ [정상 종료] → "OFFLINE" 발행 → MQTT Disconnect
  │
  └─ [비정상 종료] → Broker가 Last Will "CONNECTIONBROKEN" 발행
```

### 9.5 하트비트

Master Control은 약 15초 간격의 하트비트로 연결 상태를 감시한다.

---

## 10. Factsheet 메시지 (AGV → Master)

`factsheetRequest` InstantAction 수신 시 AGV 사양 정보를 전송한다.

### 10.1 주요 섹션

| 섹션 | 설명 |
|------|------|
| `typeSpecification` | AGV 클래스, 타입, 능력 |
| `physicalParameters` | 크기, 최대 속도, 최대 적재 중량 |
| `loadHandlingDevices` | 리프트 범위, 지원 화물 유형 |
| `supportedActions` | 지원하는 액션 목록 |
| `optionalParameters` | 지원하는 옵션 필드 (trajectory, corridor 등) |
| `stationType` / `loadType` | 지원 스테이션/화물 유형 |
| `maxMessageLength` | 최대 메시지 길이 (메모리 제한) |
| `localizationParameters` | 로컬라이제이션 방식 상세 |
| `protocolCompatibility` | 지원 프로토콜 버전 |

---

## 11. 노드 통과 메커니즘

### 11.1 통과 조건

AGV의 제어 지점(control point)이 다음 조건을 만족할 때 노드를 통과한 것으로 간주한다:
- 위치 오차 ≤ `allowedDeviationXY`
- 방향 오차 ≤ `allowedDeviationTheta`

### 11.2 통과 시 처리 순서

```
1. nodeStates에서 해당 노드 제거
2. lastNodeId, lastNodeSequenceId 업데이트
3. 노드 액션 트리거 (WAITING → INITIALIZING → RUNNING)
4. 이전 엣지 완료 (edgeStates에서 제거)
5. 다음 엣지 진입 (있는 경우) → 엣지 액션 트리거
```

### 11.3 Corridor (복도) 기능

엣지의 선택적 속성으로, 장애물 회피를 위한 주행 경계를 정의한다:

```json
{
  "corridor": {
    "leftWidth": 1.0,
    "rightWidth": 1.0,
    "corridorRefPoint": "KINEMATICCENTER"
  }
}
```

| corridorRefPoint | 설명 |
|-----------------|------|
| `KINEMATICCENTER` | 기구학적 중심 기준 |
| `CONTOUR` | 차량 외곽 기준 |

---

## 12. 주문 취소 (cancelOrder)

### 12.1 취소 흐름

```
Master: cancelOrder InstantAction 전송
  │
  ├─ AGV 즉시 정지 가능 → 현재 위치에서 정지
  │
  ├─ 노드 기반 AGV → 다음 노드에서 정지
  │
  ├─ 실행 중 액션 → 중단 시도
  │   ├─ 중단 가능 → 즉시 중단, FAILED 처리
  │   └─ 중단 불가 → 완료까지 대기 후 취소
  │
  ├─ 대기 중 액션 → FAILED 처리
  │
  └─ cancelOrder actionStatus: RUNNING → FINISHED
     (모든 취소 처리 완료 시)
```

### 12.2 취소 후 새 주문

취소 후 새 주문의 시작 노드:
1. 현재 위치에 임시 노드 생성 (큰 deviation 범위)
2. 이전 주문의 마지막 통과 노드에서 시작

---

## 13. 맵 관리

### 13.1 맵 생명주기

```
downloadMap → (맵 다운로드) → DISABLED 상태로 추가
                                    │
enableMap → ENABLED (동일 mapId의 다른 버전은 DISABLED)
                                    │
deleteMap → 맵 제거 (state에서 삭제)
```

### 13.2 규칙

- `mapId` + `mapVersion` 조합으로 식별
- 동일 `mapId`에 대해 하나의 버전만 `ENABLED` 가능
- 주문 실행 전 필요한 맵이 사전 로드되어 있어야 함

---

## 14. 통신 모범 사례

### 14.1 QoS 전략

| 상황 | QoS | 이유 |
|------|-----|------|
| order, instantActions | 0 | 고빈도, 최신 데이터가 중요 |
| state, visualization | 0 | 고빈도, 최신 데이터가 중요 |
| connection | 1 | 연결 상태는 확실히 전달되어야 함 |
| factsheet | 0 | 요청-응답 패턴 |

> **참고**: 본 프로젝트에서는 안정성을 위해 order/instantActions에 QoS 2, state에 QoS 1을 사용한다. (`CODING_RULES.md` 참조)

### 14.2 타임아웃 처리

- Master Control이 액션 타임아웃 관리 (예: `waitForTrigger`)
- AGV는 자체적으로 타임아웃 로직을 실행하지 않음

### 14.3 Optional 필드 규칙

- Optional 필드는 해당하지 않으면 생략 가능
- 전송된 Optional 필드는 수신측이 반드시 처리하거나 에러로 거부
- Master는 AGV Factsheet에서 지원하는 Optional 파라미터만 전송

### 14.4 에러 참조 (Error References)

```json
{
  "errorReferences": [
    { "referenceKey": "nodeId", "referenceValue": "node-003" },
    { "referenceKey": "actionId", "referenceValue": "action-uuid-005" }
  ]
}
```



에러의 근본 원인을 추적하기 위해 관련 엔티티의 ID를 참조한다.
