# 图例汇总（mermaid→drawio→PNG）

> 收集自：需求分析 / 总体方案 / 分项方案 / 公共部分 / 原型设计

## 一、需求全景图

**来源**: 需求分析智能体 (001_requirement.md)
**编号**: 图1-1
**类型**: graph TD 流程图
**用途**: 方案书第二章·需求分析 开头综述

```mermaid
graph TD
    subgraph "用户需求全景"
        F1[F1 组织架构管理]
        F2[F2 用户生命周期管理]
        F3[F3 身份认证]
        F4[F4 权限管理]
        F5[F5 审计日志]
        F6[F6 应用接入]
    end
    F1 --> T1[技术实现: parent_id+level+path]
    F2 --> T2[技术实现: 状态机+SCIM+bcrypt]
    F3 --> T3[技术实现: OAuth2/OIDC/SAML/CAS]
    F4 --> T4[技术实现: RBAC+ABAC+MyBatis拦截器]
    F5 --> T5[技术实现: AOP+MQ+ES+哈希链]
    F6 --> T6[技术实现: REST API+密钥管理]
    T1 --> VER[验收: CRUD≤1s]
    T2 --> VER
    T3 --> VER
    T4 --> VER
    T5 --> VER
    T6 --> VER
```

## 二、用户状态机图

**来源**: 需求分析智能体 (001_requirement.md)
**编号**: 图1-2
**类型**: graph LR 状态流转图
**用途**: 方案书2.2节·用户生命周期

```mermaid
graph LR
    REG[注册] --> PEND[待审核]
    PEND --> ACT[已激活]
    ACT --> DIS[已禁用]
    DIS --> ACT
    ACT --> DEL[已删除]
    PEND --> REJ[已驳回]
```

## 三、系统总体架构图

**来源**: 总体方案智能体 (002_architecture.md)
**编号**: 图2-1
**类型**: graph TB 分层架构图
**用途**: 方案书3.1节·总体架构

```mermaid
graph TB
    subgraph "客户端层"
        BRO[浏览器/业务系统]
    end
    subgraph "接入层"
        NX[Nginx负载均衡]
        GW[Spring Cloud Gateway]
    end
    subgraph "服务层"
        US[用户管理服务]
        AS[身份认证服务]
        PS[权限管理服务]
        AUS[安全审计服务]
    end
    subgraph "数据层"
        MYSQL[(MySQL/达梦)]
        REDIS[(Redis集群)]
        ES[(ES集群)]
    end
    subgraph "基础设施"
        MQ[RabbitMQ]
        NACOS[Nacos]
        K8S[Kubernetes]
    end
    BRO --> NX --> GW
    GW --> US & AS & PS & AUS
    US --> MYSQL & REDIS
    AS --> REDIS & MYSQL
    PS --> MYSQL & REDIS
    AUS --> ES & MQ
    US & AS & PS & AUS --> NACOS
    US & AS & PS & AUS -..-> K8S
```

## 四、服务模块关系图

**来源**: 分项方案智能体 (003_subproject.md)
**编号**: 图3-1
**类型**: graph TB 模块关系图
**用途**: 方案书4.1-4.4节·各服务内部结构

```mermaid
graph TB
    subgraph "用户管理服务"
        OM[组织管理模块] --> UM[用户管理模块]
        UM --> SYNC[HR同步模块]
    end
    subgraph "身份认证服务"
        AM[认证模块] --> SSO[SSO模块]
        SSO --> TM[令牌管理模块]
    end
    subgraph "权限管理服务"
        RM[角色管理] --> PM[授权判定]
        PM --> DP[数据权限]
    end
    subgraph "安全审计服务"
        LC[日志采集] --> LS[日志存储]
        LS --> ALERT[告警模块]
    end
    AM --> LC
    PM --> LC
```

## 五、SSO认证时序图

**来源**: 公共部分智能体 (004_common.md)
**编号**: 图4-1
**类型**: sequenceDiagram 时序图
**用途**: 方案书3.2节·认证流程说明

```mermaid
sequenceDiagram
    participant U as 用户
    participant GW as API网关
    participant AS as 认证服务
    participant APP as 业务系统
    participant AUDIT as 审计服务
    
    U->>GW: 1.登录请求(密码加密)
    GW->>AS: 2.路由到认证服务
    AS->>AS: 3.验证密码(bcrypt比对)
    AS->>AS: 4.生成JWT+RefreshToken
    AS->>AUDIT: 5.审计日志(MQ)
    AS-->>GW: 6.返回Token
    GW-->>U: 7.登录成功
    U->>GW: 8.请求业务API(Token)
    GW->>GW: 9.验证JWT签名
    GW->>APP: 10.转发请求(含用户信息)
    APP-->>GW: 11.业务响应
    GW-->>U: 12.返回结果
```

## 六、标准化输出对照表

| 编号 | 图名 | 类型 | 插入位置 | mermaid源 | drawio | PNG |
|:---:|------|:---:|---------|:--------:|:------:|:---:|
| 1-1 | 需求全景图 | graph TD | 第二章开头 | ✅ | - | - |
| 1-2 | 用户状态机 | graph LR | §2.2 | ✅ | - | - |
| 2-1 | 系统架构图 | graph TB | §3.1 | ✅ | - | - |
| 3-1 | 服务模块关系 | graph TB | §4.1-4.4 | ✅ | - | - |
| 4-1 | 认证时序图 | sequence | §3.2 | ✅ | - | - |

> **说明**: mermaid代码可直接进方案书。后续可通过 mermaid-cli (mmdc) 将 mermaid 转为 SVG/PNG，或通过 drawio 重新绘制为标准化格式。
