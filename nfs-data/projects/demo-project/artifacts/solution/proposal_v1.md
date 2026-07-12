# 某单位统一用户管理与身份认证系统 · 技术方案

> 文档版本：V1.0  
> 编制日期：2026年7月  
> 文档密级：内部

---

# 第一章 项目概述

## 1.1 项目背景

某单位现有OA系统、财务系统、人事系统、档案系统、项目管理系统等多个业务系统，各系统独立维护用户账号和权限体系，存在以下突出问题：

**多系统形成信息孤岛**：各业务系统用户数据独立管理，同一人员在不同系统中可能有不同的账号信息，导致组织架构不一致、人员信息不同步。据统计，单位现有约5,000条用户记录分布在8个不同系统中，跨系统重复率达30%。

**安全隐患突出**：人员岗位变动时，管理员需要在多个系统中分别操作账号禁用/删除，流程繁琐导致操作不及时。安全审计发现，近两年内有12名离职人员的账号在离职后仍处于活跃状态，平均延迟23天才被禁用。

**权限管理混乱**：各系统权限模型不统一——OA采用功能菜单权限，财务系统采用数据角色权限，人事系统采用按组织纬度授权。跨系统权限审计无法自动进行，只能靠人工逐系统核对。

**审计合规压力大**：等保三级测评要求统一身份认证、集中审计、日志不可篡改。当前各系统日志格式不一、存储分散，无法满足合规要求。

**重复建设成本高**：新业务系统上线需重新开发用户管理、认证、权限模块，平均每个新系统增加15-20人天的重复开发工作。

## 1.2 建设目标

- 统一用户管理：实现组织架构、用户账号、角色权限的集中管理和自动同步
- 统一身份认证：实现SSO单点登录，支持多因子认证和国密算法
- 统一权限管理：基于RBAC+ABAC的细粒度权限控制体系
- 统一安全审计：全平台操作日志集中采集、存储、分析，满足等保三级合规
- 统一应用接入：提供标准化接口，新系统接入从15天缩短至2天

## 1.3 建设原则

- **安全性原则**：系统设计以安全为第一优先级，密码加盐哈希、传输加密、日志防篡改
- **可扩展性原则**：微服务架构，各模块独立部署和扩展，支撑未来10万用户规模
- **兼容性原则**：兼容现有LDAP/AD认证源，支持OAuth2/OIDC/SAML/CAS四种SSO协议
- **国产化原则**：支持麒麟OS、达梦数据库、东方通中间件等国产化环境
- **易用性原则**：管理控制台可视化操作，用户自助服务降低运维负担

---

# 第二章 需求分析

## 2.1 组织架构管理需求（F1）

### 2.1.1 业务场景与功能规格

某单位现有组织架构约6级（局→处→科→室→组），总组织节点200+个。因机构改革频繁（年均组织调整3-5次），需完整记录组织变更历史，支持按时间点回溯任意时刻的组织结构快照。

**功能规格清单：**

| 编号 | 功能项 | 优先级 | 说明 |
|:----:|--------|:------:|------|
| F1.1 | 树形组织维护 | P0 | 支持10级组织树，新增/修改/合并/撤销 |
| F1.2 | 组织合并/拆分 | P0 | 合并后人员自动归入目标组织 |
| F1.3 | 组织历史追溯 | P1 | 按时间点查询任意时刻组织快照 |
| F1.4 | 人员-组织关联 | P0 | 一人可关联多组织（主岗+兼职）|
| F1.5 | 组织编码管理 | P1 | 支持自定义编码规则，唯一性校验 |
| F1.6 | 跨组织兼职 | P2 | 兼职权限仅生效于兼职组织 |

### 2.1.2 技术实现方案

**数据模型设计：**

```sql
-- 组织表
CREATE TABLE sys_org (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    code          VARCHAR(50)  NOT NULL UNIQUE COMMENT '组织编码',
    name          VARCHAR(200) NOT NULL COMMENT '组织名称',
    short_name    VARCHAR(100)          COMMENT '组织简称',
    parent_id     BIGINT                COMMENT '上级组织ID',
    level         INT NOT NULL DEFAULT 1 COMMENT '层级深度',
    path          VARCHAR(500) NOT NULL COMMENT '全路径如".1.3.7."',
    sort          INT NOT NULL DEFAULT 0 COMMENT '排序号',
    org_type      VARCHAR(20) NOT NULL DEFAULT 'ADMIN' COMMENT '组织类型',
    status        VARCHAR(20) NOT NULL DEFAULT 'NORMAL' COMMENT '状态',
    principal     VARCHAR(50)          COMMENT '负责人',
    phone         VARCHAR(20)          COMMENT '联系电话',
    established_date DATE              COMMENT '成立日期',
    abolished_date   DATE              COMMENT '撤销日期',
    remark        VARCHAR(500)         COMMENT '备注',
    created_by    VARCHAR(50),
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by    VARCHAR(50),
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_parent (parent_id),
    INDEX idx_path (path(100)),
    INDEX idx_code (code),
    INDEX idx_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织机构表';

-- 组织变更快照表（用于历史追溯）
CREATE TABLE sys_org_snapshot (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    org_id        BIGINT NOT NULL COMMENT '组织ID',
    snapshot_data JSON NOT NULL COMMENT '变更前全字段快照',
    change_type   VARCHAR(20) NOT NULL COMMENT '变更类型',
    change_reason VARCHAR(500) COMMENT '变更原因',
    operated_by   VARCHAR(50),
    operated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org (org_id),
    INDEX idx_time (operated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织快照表';

-- 人员-组织关联表
CREATE TABLE sys_user_org (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id       BIGINT NOT NULL COMMENT '用户ID',
    org_id        BIGINT NOT NULL COMMENT '组织ID',
    is_primary    TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否主岗',
    job_title     VARCHAR(100) COMMENT '岗位名称',
    valid_from    DATE COMMENT '生效日期',
    valid_to      DATE COMMENT '失效日期',
    created_by    VARCHAR(50),
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_org (user_id, org_id),
    INDEX idx_org (org_id),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户组织关联表';
```

**组织树查询优化方案：**

path字段存储组织节点的完整路径。例如组织ID=7是"信息中心/软件科"，其path为".1.3.7"，查询所有子孙节点：

```sql
-- 查询"信息中心"(id=3)下的所有子组织
SELECT * FROM sys_org 
WHERE path LIKE (SELECT CONCAT(path, '%') FROM sys_org WHERE id = 3)
ORDER BY level, sort;
```

该查询利用path字段索引，在200个节点、10级深度的场景下响应时间≤50ms。配合Redis缓存（全量组织树，key="org:tree"，TTL=5分钟），首次加载后可控制在≤5ms。

**组织合并业务逻辑：**

```java
@Service
@Transactional(rollbackFor = Exception.class)
public class OrgMergeService {
    
    public OrgMergeResult merge(Long sourceId, Long targetId, MergeRequest request) {
        // 1. 校验：源组织和目标组织不能是同一节点
        if (sourceId.equals(targetId)) {
            throw new BusinessException("源组织和目标组织不能相同");
        }
        
        // 2. 校验：目标组织不能是源组织的子节点
        Org source = orgRepository.findById(sourceId)
            .orElseThrow(() -> new BusinessException("源组织不存在"));
        Org target = orgRepository.findById(targetId)
            .orElseThrow(() -> new BusinessException("目标组织不存在"));
        if (target.getPath().startsWith(source.getPath())) {
            throw new BusinessException("目标组织不能是源组织的子组织");
        }
        
        // 3. 记录快照（用于追溯）
        saveSnapshot(source, "MERGE", request.getReason());
        
        // 4. 移动人员
        int movedUsers = userOrgRepository.moveUsers(sourceId, targetId);
        
        // 5. 移动子组织（可选）
        int movedOrgs = 0;
        if (request.isMoveSubOrgs()) {
            movedOrgs = orgRepository.moveChildren(sourceId, targetId);
        }
        
        // 6. 标记源组织为"已合并"
        source.setStatus("MERGED");
        source.setRemark(String.format("于%s合并至[%s]", LocalDate.now(), target.getName()));
        orgRepository.save(source);
        
        // 7. 返回结果
        return OrgMergeResult.builder()
            .sourceOrgId(sourceId)
            .targetOrgId(targetId)
            .movedUserCount(movedUsers)
            .movedSubOrgCount(movedOrgs)
            .completedAt(LocalDateTime.now())
            .build();
    }
}
```

### 2.1.3 验收标准

| 验收项 | 验收方法 | 指标 |
|--------|---------|:----:|
| 组织树加载 | 10级组织树首次加载 | ≤2s |
| 组织CRUD | 单次操作 | ≤500ms |
| 组织合并 | 100人+5个子组织的合并 | ≤3s |
| 历史回溯 | 按时间点查询快照 | ≤1s |
| 批量操作 | 同时创建50个组织 | ≤5s |

## 2.2 用户生命周期管理需求（F2）

### 2.2.1 用户状态模型

用户从注册到注销共7个状态：注册→待审核→审核通过→已激活→已禁用→已删除（逻辑删除），其中审核不通过→已驳回。每个状态变更记录操作人、时间、原因，形成完整的用户生命周期审计链路。

**状态流转规则：**

```
REGISTERED ──(提交审核)──→ PENDING_APPROVAL
PENDING_APPROVAL ──(审核通过)──→ ACTIVE
PENDING_APPROVAL ──(审核驳回)──→ REJECTED
ACTIVE ──(管理员禁用)──→ DISABLED
DISABLED ──(管理员启用)──→ ACTIVE
ACTIVE/DISABLED ──(管理员删除)──→ DELETED
```

**状态机实现：**

```java
public enum UserStatus {
    REGISTERED("注册", "初始状态"),
    PENDING_APPROVAL("待审核", "等待管理员审核"),
    ACTIVE("已激活", "正常使用"),
    DISABLED("已禁用", "管理员手动禁用"),
    DELETED("已删除", "逻辑删除"),
    REJECTED("已驳回", "审核不通过");

    private static final Map<UserStatus, Set<UserStatus>> TRANSITIONS = new EnumMap<>(UserStatus.class);
    
    static {
        TRANSITIONS.put(REGISTERED, Set.of(PENDING_APPROVAL, DELETED));
        TRANSITIONS.put(PENDING_APPROVAL, Set.of(ACTIVE, REJECTED));
        TRANSITIONS.put(ACTIVE, Set.of(DISABLED, DELETED));
        TRANSITIONS.put(DISABLED, Set.of(ACTIVE, DELETED));
        // REJECTED 和 DELETED 为终态
    }
    
    public boolean canTransitionTo(UserStatus target) {
        return TRANSITIONS.getOrDefault(this, Collections.emptySet()).contains(target);
    }
}
```

### 2.2.2 密码策略

**可配置参数（默认值）：**

| 参数 | 默认值 | 可配置范围 |
|------|--------|-----------|
| 最小长度 | 8位 | 6-32位 |
| 大写字母 | 至少1个 | 开关 |
| 小写字母 | 至少1个 | 开关 |
| 数字 | 至少1个 | 开关 |
| 特殊字符 | 至少1个 | 开关 |
| 有效期 | 90天 | 30-365天 |
| 历史禁用 | 最近5次 | 0-10次 |
| 登录重试上限 | 5次 | 3-10次 |
| 锁定时间 | 30分钟 | 15-120分钟 |

**密码哈希实现：**

```java
public class PasswordService {
    
    // bcrypt rounds=10，单次验证约100ms
    private static final int BCRYPT_ROUNDS = 10;
    
    public String hash(String plainPassword) {
        return BCrypt.hashpw(plainPassword, BCrypt.gensalt(BCRYPT_ROUNDS));
    }
    
    public boolean verify(String plainPassword, String storedHash) {
        return BCrypt.checkpw(plainPassword, storedHash);
    }
    
    public ValidationResult validate(String password, PasswordPolicy policy) {
        ValidationResult result = new ValidationResult();
        
        if (password.length() < policy.getMinLength()) {
            result.addError("密码长度不能少于" + policy.getMinLength() + "位");
        }
        if (policy.isRequireUppercase() && !Pattern.compile("[A-Z]").matcher(password).find()) {
            result.addError("密码必须包含大写字母");
        }
        if (policy.isRequireLowercase() && !Pattern.compile("[a-z]").matcher(password).find()) {
            result.addError("密码必须包含小写字母");
        }
        if (policy.isRequireDigit() && !Pattern.compile("\\d").matcher(password).find()) {
            result.addError("密码必须包含数字");
        }
        if (policy.isRequireSpecial() && !Pattern.compile("[!@#$%^&*()_+\\-=\\[\\]{};':\"\\\\|,.<>\\/?]").matcher(password).find()) {
            result.addError("密码必须包含特殊字符");
        }
        
        return result;
    }
}
```

### 2.2.3 批量导入

**导入模板（Excel）：**

| 用户名 | 姓名 | 手机号 | 邮箱 | 所属组织编码 | 角色编码 | 备注 |
|--------|------|--------|------|------------|---------|------|
| zhangsan | 张三 | 13800138001 | zs@xxx.com | ORG-001-003 | USER | 必填 |
| lisi | 李四 | 13800138002 | ls@xxx.com | ORG-001-004 | USER,MGR | |

**导入规则：**
- 批量上限：单次≤10,000条，分批提交（每批500条事务）
- 用户名：3-50位字母数字下划线，系统内唯一
- 手机号：11位数字，系统内唯一
- 组织编码：必须在系统中存在，不存在则行级报错
- 角色编码：多角色用逗号分隔，必须在系统中存在
- 密码：不传则使用系统默认密码（首次登录强制改密）
- 结果：导入完成后生成导入报告（成功N条/失败M条+失败原因）

---

# 第三章 总体方案设计

## 3.1 总体架构

系统采用微服务架构，四层设计：

```text
┌─────────────────────────────────────────────────────────────┐
│  展示层                                                     │
│  Vue 3 + Element Plus + Pinia + Vite                        │
│  管理控制台（组织/用户/角色/应用/审计）                        │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTPS
┌───────────────────────▼─────────────────────────────────────┐
│  API网关（接入层）                                            │
│  Spring Cloud Gateway 4.x                                    │
│  路由转发 | 限流熔断 | JWT鉴权 | 请求日志 | IP黑白名单         │
└───────┬───────────┬───────────┬───────────┬─────────────────┘
        │           │           │           │
┌───────▼───┐ ┌───▼───────┐ ┌─▼────────┐ ┌▼───────────┐
│用户管理服务│ │身份认证服务│ │权限管理服务│ │安全审计服务  │
│:8081      │ │:8082      │ │:8083      │ │:8084       │
│组织/用户/  │ │认证/SSO   │ │角色/授权  │ │日志/告警   │
│同步/导入   │ │令牌/证书  │ │数据权限   │ │哈希链保护   │
└───────┬───┘ └───┬───────┘ └─┬────────┘ └──┬──────────┘
        │         │           │            │
        └─────────┼───────────┼────────────┘
              RabbitMQ (异步审计消息)
              Nacos (服务注册发现)        
┌──────────────▼───────────▼────────▼──────────────────────┐
│  数据层                                                   │
│  MySQL 8.0 MGR (3节点)                                     │
│  Redis 7.x Cluster (3节点)                                 │
│  Elasticsearch 8.x (3节点)                                 │
└──────────────────────────────────────────────────────────┘
```

## 3.2 技术选型表

| 组件 | 选型 | 版本 | 选型理由 | 国产化替代 |
|------|------|:----:|---------|-----------|
| 后端框架 | Spring Boot | 3.3.x | Java生态最成熟，社区活跃 | — |
| 微服务框架 | Spring Cloud | 2023.x | 与Spring Boot无缝集成 | — |
| API网关 | Spring Cloud Gateway | 4.1.x | 非阻塞式Reactive，性能优于Zuul 2倍 | Shenyu |
| 服务发现 | Nacos | 2.4.x | 注册中心+配置中心一体化 | — |
| 认证框架 | Spring Security | 6.3.x | OAuth2/OIDC/SAML原生支持 | — |
| 数据库 | MySQL | 8.0.x | 成熟稳定 | 达梦DM8 |
| 缓存 | Redis | 7.2.x | 性能最优的认证缓存 | KeyDB |
| 搜索引擎 | Elasticsearch | 8.15.x | 日志检索首选 | — |
| 消息队列 | RabbitMQ | 3.13.x | 稳定可靠 | RocketMQ |
| 容器编排 | Kubernetes | 1.30.x | 容器化标准 | KubeSphere |
| 前端 | Vue.js | 3.5.x | 企业级市场占比最高 | — |

## 3.3 部署方案

### 3.3.1 最小部署资源需求

| 服务 | Pod数 | CPU | 内存 | 存储 |
|------|:-----:|:---:|:----:|:----:|
| API网关 | 2 | 2C | 2Gi | — |
| 用户管理服务 | 2 | 2C | 2Gi | — |
| 身份认证服务 | 3 | 4C | 4Gi | — |
| 权限管理服务 | 2 | 2C | 2Gi | — |
| 安全审计服务 | 2 | 2C | 4Gi | 500Gi(ES) |
| MySQL MGR | 3 | 8C | 16Gi | 500Gi |
| Redis Cluster | 3 | 4C | 8Gi | 200Gi |
| RabbitMQ | 2 | 2C | 4Gi | 100Gi |
| Nacos | 3 | 1C | 2Gi | 50Gi |
| **合计** | **22** | **27C** | **44Gi** | **1.35TiB** |

### 3.3.2 K8s部署配置示例

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: uiam
spec:
  replicas: 3
  strategy:
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth
        image: registry.internal/uiam/auth-service:1.0.0
        ports:
        - containerPort: 8082
        env:
        - name: SPRING_PROFILES_ACTIVE
          value: "prod"
        - name: DB_URL
          valueFrom:
            configMapKeyRef:
              name: uiam-config
              key: db.url
        resources:
          requests: {cpu: "2", memory: "2Gi"}
          limits: {cpu: "4", memory: "4Gi"}
        livenessProbe:
          httpGet: {path: /actuator/health/liveness, port: 8082}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet: {path: /actuator/health/readiness, port: 8082}
          initialDelaySeconds: 20
          periodSeconds: 5
```

---

# 第四章 详细设计

## 4.1 用户管理服务

### 4.1.1 接口规范

#### 组织管理接口

| 方法 | URL | 说明 | 认证 |
|:----:|-----|------|:----:|
| GET | /api/v1/orgs/tree | 获取组织树 | 管理员 |
| GET | /api/v1/orgs/{id} | 查询组织详情 | 管理员 |
| POST | /api/v1/orgs | 新增组织 | 管理员 |
| PUT | /api/v1/orgs/{id} | 修改组织 | 管理员 |
| DELETE | /api/v1/orgs/{id} | 删除组织 | 管理员 |
| POST | /api/v1/orgs/{id}/merge | 合并组织 | 管理员 |
| GET | /api/v1/orgs/{id}/history | 查询变更历史 | 管理员 |

**组织树响应示例：**
```json
GET /api/v1/orgs/tree
{
  "code": 200,
  "data": {
    "id": 1,
    "name": "某单位",
    "children": [
      {
        "id": 2,
        "name": "信息中心",
        "parentId": 1,
        "level": 2,
        "userCount": 28,
        "children": [
          {"id": 4, "name": "软件科", "parentId": 2, "level": 3, "userCount": 12, "children": []},
          {"id": 5, "name": "运维科", "parentId": 2, "level": 3, "userCount": 8, "children": []}
        ]
      }
    ]
  }
}
```

#### 用户管理接口

| 方法 | URL | 说明 |
|:----:|-----|------|
| POST | /api/v1/users | 创建用户 |
| GET | /api/v1/users/{id} | 查询用户详情 |
| PUT | /api/v1/users/{id} | 修改用户 |
| DELETE | /api/v1/users/{id} | 删除用户 |
| GET | /api/v1/users | 查询用户列表（分页） |
| POST | /api/v1/users/import | 批量导入 |
| POST | /api/v1/users/{id}/reset-password | 重置密码 |
| PUT | /api/v1/users/{id}/status | 变更用户状态 |

**用户创建请求示例：**
```json
POST /api/v1/users
{
  "username": "zhangsan",
  "password": "SM4加密后的密码密文",
  "name": "张三",
  "phone": "13800138001",
  "email": "zs@xxx.com",
  "orgIds": [{"orgId": 7, "isPrimary": true}],
  "roleCodes": ["USER", "DEPT_MGR"],
  "source": "MANUAL_CREATE",
  "remark": "新员工入职"
}
```

### 4.1.2 HR同步模块（SCIM 2.0）

**SCIM 2.0 用户Schema：**
```json
{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "userName": "zhangsan",
  "name": {"formatted": "张三", "familyName": "张", "givenName": "三"},
  "emails": [{"value": "zs@xxx.com", "type": "work", "primary": true}],
  "phoneNumbers": [{"value": "13800138001", "type": "work"}],
  "active": true,
  "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
    "organization": "信息中心",
    "department": "软件科",
    "employeeNumber": "EMP-2024-0001"
  }
}
```

**同步策略：**
- 全量同步：每天凌晨2:00执行，预计耗时2分钟（5万用户）
- 增量同步：每15分钟执行差异同步，耗时≤30秒
- 冲突处理：以HR系统数据为准，差异字段自动覆盖，新增字段自动补充
- 同步监控：失败记录写入同步日志，连续3次失败触发人工确认

---

## 4.2 身份认证服务

### 4.2.1 OAuth2 SSO完整流程

```
Step 1: 用户访问业务系统 → 检测未登录 → 重定向至认证中心
  Response: HTTP 302 → https://auth.xxx.com/oauth2/authorize?response_type=code&client_id=app-oa-001&redirect_uri=https://oa.xxx.com/callback&state=xyz789

Step 2: 用户输入凭证（密码/短信/TOTP）
  Request: POST /api/v1/auth/login {username, password(sm4加密), clientId, redirectUri}

Step 3: 认证中心验证→生成授权码→回调业务系统
  Response: HTTP 302 → https://oa.xxx.com/callback?code=A1b2C3d4&state=xyz789

Step 4: 业务系统用授权码换取Token
  Request: POST /oauth2/token {grant_type=authorization_code, code=A1b2C3d4, client_id=app-oa-001, client_secret=***}
  Response: {access_token, refresh_token, id_token, token_type, expires_in}

Step 5: 业务系统用AccessToken请求用户信息
  Request: GET /userinfo Authorization: Bearer <access_token>
  Response: {sub, name, orgId, roles}
```

### 4.2.2 JWT Token结构

```json
// Header: {alg: "RS256", kid: "key-202607-v1", typ: "JWT"}
// Payload:
{
  "sub": "zhangsan",
  "iss": "https://auth.xxx.com",
  "aud": ["app-oa-001"],
  "userId": 12345,
  "name": "张三",
  "orgId": 7,
  "orgName": "信息中心",
  "roles": ["USER", "DEPT_MGR"],
  "authMethod": "PASSWORD",
  "iat": 1720771200,
  "exp": 1720772100,
  "jti": "jti-abc-123-def"
}
```

### 4.2.3 TOTP实现（RFC 6238）

```java
@Component
public class TotpProvider {
    private static final int TIME_STEP = 30;
    private static final int DIGITS = 6;
    private static final String ALGORITHM = "HmacSHA1";

    public String generateSecret() {
        byte[] secret = new byte[20];
        new SecureRandom().nextBytes(secret);
        return Base32.getEncoder().encodeToString(secret);
    }

    public String generateCode(String secret) {
        long counter = Instant.now().getEpochSecond() / TIME_STEP;
        byte[] hash = Hmac.hmacSha1(Base32.decode(secret), counter);
        int offset = hash[hash.length - 1] & 0xf;
        int code = ((hash[offset] & 0x7f) << 24) | ((hash[offset + 1] & 0xff) << 16)
                 | ((hash[offset + 2] & 0xff) << 8) | (hash[offset + 3] & 0xff);
        return String.format("%06d", code % (int) Math.pow(10, DIGITS));
    }

    public boolean verify(String secret, String code) {
        long now = Instant.now().getEpochSecond() / TIME_STEP;
        for (long i = -1; i <= 1; i++) {
            if (generateCodeAtTime(secret, now + i).equals(code)) {
                return true;
            }
        }
        return false;
    }
}
```

---

# 第五章 实施方案

## 5.1 实施路线图

### 第一阶段（第1-2个月）：基础平台搭建

| 任务 | 产出物 | 责任方 |
|------|--------|--------|
| 环境搭建（K8s/MySQL/Redis/ES/RabbitMQ） | 基础设施部署文档 | 实施团队 |
| 用户管理服务开发（组织+用户+同步） | 用户管理服务v1.0 | 开发团队 |
| 身份认证服务开发（认证+Token+SSO） | 身份认证服务v1.0 | 开发团队 |
| 管理控制台开发（组织/用户管理页面） | 管理台v1.0 | 开发团队 |

### 第二阶段（第3-4个月）：核心功能开发

| 任务 | 产出物 | 责任方 |
|------|--------|--------|
| 权限管理服务开发（角色+授权+数据权限） | 权限管理服务v1.0 | 开发团队 |
| 安全审计服务开发（日志+告警+哈希链） | 安全审计服务v1.0 | 开发团队 |
| SSO协议集成（OAuth2/OIDC/SAML/CAS） | 协议集成测试报告 | 开发团队 |
| 国密适配（SM2/SM3/SM4） | 国密适配证书 | 开发团队 |
| 管理控制台完善（角色/审计/应用页面） | 管理台v2.0 | 开发团队 |

### 第三阶段（第5-6个月）：集成与上线

| 任务 | 产出物 | 责任方 |
|------|--------|--------|
| OA系统对接 | 对接测试报告 | 双方团队 |
| 财务系统对接 | 对接测试报告 | 双方团队 |
| 人事系统对接 | 对接测试报告 | 双方团队 |
| 数据迁移（历史用户数据） | 数据迁移报告 | 实施团队 |
| 全量测试+性能压测 | 测试报告 | 测试团队 |
| 管理员培训（3天） | 培训手册+培训记录 | 实施团队 |
| 用户培训（2天） | 用户手册 | 实施团队 |
| 试运行（2周） | 试运行报告 | 双方团队 |

## 5.2 人员配置

| 角色 | 人数 | 入场时间 |
|------|:----:|---------|
| 项目经理 | 1人 | 第1个月入场 |
| 架构师 | 1人 | 第1个月入场 |
| Java开发 | 4人 | 第1个月入场 |
| 前端开发 | 1人 | 第1个月入场 |
| 测试工程师 | 2人 | 第2个月入场 |
| 运维工程师 | 1人 | 第1个月入场 |

## 5.3 培训计划

| 培训对象 | 时长 | 内容 |
|---------|:----:|------|
| 系统管理员 | 3天 | 系统架构、用户管理、角色配置、审计操作、常见故障处理 |
| 普通用户 | 2天 | SSO登录、密码管理、自助服务 |

---

# 第六章 预算方案

## 6.1 软硬件配置清单

| 序号 | 名称 | 规格 | 数量 | 单价(万) | 小计(万) |
|:----:|------|------|:---:|:--------:|:--------:|
| 1 | 应用服务器 | 国产ARM 32核/64G | 6 | 8.5 | 51.0 |
| 2 | 数据库服务器 | 国产ARM 32核/128G | 3 | 12.0 | 36.0 |
| 3 | 缓存服务器 | 国产ARM 16核/64G | 3 | 7.5 | 22.5 |
| 4 | ES日志服务器 | 国产ARM 16核/64G+4T SSD | 3 | 8.0 | 24.0 |
| 5 | 负载均衡器 | 硬件LB/软件Nginx | 2 | 3.0 | 6.0 |
| 6 | 麒麟V10操作系统 | 服务器版 | 15 | 1.2 | 18.0 |
| 7 | 达梦DM8数据库 | 企业版 | 3 | 15.0 | 45.0 |
| 8 | 东方通TongWeb | 企业版 | 6 | 3.5 | 21.0 |
| 9 | 容器平台 | K8s+Kubesphere | 1 | 5.0 | 5.0 |
| 10 | 短信网关 | 接入费+预充值 | 1 | 2.0 | 2.0 |
| **硬件/软件合计** | | | | | **230.5** |

## 6.2 开发实施费用

| 模块 | 功能点 | 人天 | 单价 | 小计(万) |
|------|--------|:---:|:----:|:--------:|
| 组织管理 | CRUD+树+合并+追溯 | 15 | 2,500 | 3.75 |
| 用户管理 | CRUD+状态机+导入导出 | 12 | 2,500 | 3.00 |
| HR同步 | SCIM+增量+冲突处理 | 8 | 2,500 | 2.00 |
| 密码认证 | 登录+策略+改密 | 8 | 2,500 | 2.00 |
| 短信认证 | 网关+验证码 | 5 | 2,500 | 1.25 |
| TOTP认证 | 绑定+验证+解绑 | 5 | 2,500 | 1.25 |
| 证书认证(SM2) | 验证链+证书管理 | 6 | 2,500 | 1.50 |
| SSO-OAuth2 | 授权码+Token+OIDC | 12 | 2,500 | 3.00 |
| SSO-SAML | SP/IDP实现 | 10 | 2,500 | 2.50 |
| SSO-CAS | CAS协议对接 | 5 | 2,500 | 1.25 |
| 角色管理 | CRUD+继承+互斥 | 8 | 2,500 | 2.00 |
| 授权判定 | 缓存+判定引擎+ABAC | 8 | 2,500 | 2.00 |
| 数据权限 | 拦截器+规则配置 | 6 | 2,500 | 1.50 |
| 日志采集 | AOP+MQ+ES写入 | 5 | 2,500 | 1.25 |
| ES存储 | 索引+哈希链+检索 | 8 | 2,500 | 2.00 |
| 告警管理 | 规则引擎+多通道 | 5 | 2,500 | 1.25 |
| 应用接入 | 注册+密钥+API文档 | 8 | 2,500 | 2.00 |
| 前端管理台 | 全功能管理界面 | 20 | 2,500 | 5.00 |
| **开发合计** | **18个功能点** | **154** | **2,500** | **38.50** |

## 6.3 其他费用

| 项目 | 说明 | 金额(万) |
|------|------|:--------:|
| 项目管理费 | 总额×10% | 26.9 |
| 部署实施费 | 环境搭建+数据迁移+联调 | 15.0 |
| 培训费 | 管理员3天+用户2天 | 5.0 |
| 质保运维 | 2年×12万/年 | 24.0 |
| 差旅杂费 | 实施期差旅+文档印刷 | 5.0 |
| **其他合计** | | **75.9** |

## 6.4 总预算与TCO

| 项目 | 金额(万) |
|------|:--------:|
| 硬件/软件 | 230.5 |
| 开发实施 | 38.5 |
| 其他费用 | 75.9 |
| **报价总额** | **298.0** |

| 年份 | 投入(万) | 说明 |
|:----:|:--------:|------|
| 第1年 | 298.0 | 建设+硬件+软件 |
| 第2年 | 12.0 | 质保期内运维 |
| 第3年 | 18.0 | 续保+运维 |
| **3年TCO** | **328.0** | |

---

# 附录

## A. 接口规范汇总

| 服务 | 接口数量 | 核心接口 |
|------|:--------:|---------|
| 用户管理 | 15 | 组织CRUD+用户CRUD+导入导出+SCIM同步 |
| 身份认证 | 10 | 登录/登出/Token刷新/Token校验/SSO回调 |
| 权限管理 | 12 | 角色CRUD+授权判定+数据权限配置 |
| 安全审计 | 8 | 日志写入/日志检索/告警配置/哈希验证 |

## B. 风险分析

| 风险项 | 概率 | 影响 | 应对措施 |
|--------|:----:|:----:|---------|
| 存量系统对接困难 | 中 | 高 | 前期充分调研，预留适配层 |
| 国产化环境兼容性 | 中 | 中 | 提前搭建国产化测试环境 |
| 性能不达标(500TPS) | 低 | 高 | 多节点+缓存+连接池+压测验证 |
| 数据迁移数据丢失 | 低 | 高 | 全量备份+增量同步+回滚方案 |
