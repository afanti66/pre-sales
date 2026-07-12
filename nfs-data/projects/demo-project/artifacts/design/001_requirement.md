# 第二章 需求分析

## 2.1 组织架构管理需求（F1）

### 2.1.1 业务场景
某单位现有组织架构约6级（局→处→科→室→组），总组织节点约200+个。因机构改革频繁（年均组织调整3-5次），需要系统能够完整记录组织变更历史，支持按时间点回溯任意时刻的组织结构快照。

### 2.1.2 功能规格

**2.1.2.1 组织树维护**
- 支持树形结构展示，最大层级深度不低于10级
- 单节点下子节点数量无硬性限制（设计目标≥500个）
- 组织节点属性：编码、名称、简称、上级组织、排序号、组织类型（行政/事业/企业/临时）、状态（正常/撤销/合并中）、成立日期、撤销日期、备注
- 操作类型：新增子节点、修改属性、删除空节点、移动（变更父节点）
- 组织合并：选择两个同级组织合并，合并后原组织标记为"已合并"，人员自动归入目标组织
- 组织拆分：选择一个组织拆分为多个，人员按规则分配到子组织

**2.1.2.2 组织查询**
- 按编码精确查询、按名称模糊查询、按类型筛选
- 查询根节点到目标节点的完整路径（如：某单位→信息中心→软件科→开发组）
- 查询某个组织的所有子孙节点
- 查询某个组织的直接子节点（分页，每页50条）
- 查询某个组织的历史变更记录

**2.1.2.3 组织与人员关联**
- 一人可关联多个组织（主岗1个+兼职N个），兼职数上限可配置
- 关联有效期：支持设置临时调动的起止时间，到期自动解除
- 关联变更记录：记录每次关联变更的操作人、时间、原因

### 2.1.3 技术方案

**数据模型（MySQL DDL）：**
```sql
CREATE TABLE sys_org (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) NOT NULL UNIQUE COMMENT '组织编码',
    name VARCHAR(200) NOT NULL COMMENT '组织名称',
    short_name VARCHAR(100) COMMENT '组织简称',
    parent_id BIGINT DEFAULT NULL COMMENT '上级组织ID',
    level INT NOT NULL DEFAULT 1 COMMENT '层级深度',
    path VARCHAR(500) NOT NULL COMMENT '路径（如 .1.3.7.）',
    sort INT NOT NULL DEFAULT 0 COMMENT '排序号',
    org_type VARCHAR(20) NOT NULL DEFAULT 'ADMIN' COMMENT '组织类型',
    status VARCHAR(20) NOT NULL DEFAULT 'NORMAL' COMMENT '状态',
    established_date DATE COMMENT '成立日期',
    abolished_date DATE COMMENT '撤销日期',
    remark VARCHAR(500) COMMENT '备注',
    created_by VARCHAR(50), created_at DATETIME,
    updated_by VARCHAR(50), updated_at DATETIME,
    INDEX idx_parent (parent_id),
    INDEX idx_path (path),
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织表';
```

**组织树查询实现：**
使用path字段存储全路径，查询所有子组织时：
```sql
-- 查询组织ID=7的所有子孙节点
SELECT * FROM sys_org WHERE path LIKE CONCAT(
    (SELECT path FROM sys_org WHERE id = 7), '%%')
ORDER BY level, sort;
```

**组织变更历史追溯：**
```sql
CREATE TABLE sys_org_snapshot (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    org_id BIGINT NOT NULL COMMENT '组织ID',
    snapshot_data JSON NOT NULL COMMENT '变更前快照(全字段JSON)',
    change_type VARCHAR(20) NOT NULL COMMENT '变更类型',
    change_reason VARCHAR(500) COMMENT '变更原因',
    operated_by VARCHAR(50), operated_at DATETIME,
    INDEX idx_org (org_id),
    INDEX idx_time (operated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织快照表';
```

### 2.1.4 验收标准
- 组织树加载：10级组织树首次加载≤2s，缓存后≤500ms
- 组织CRUD：单次操作≤500ms
- 组织查询：按路径查询子组织≤200ms
- 历史回溯：按时间点查询快照≤1s

## 2.2 用户生命周期管理需求（F2）

### 2.2.1 用户状态模型
用户状态机严格定义为以下6种状态，状态流转规则：

```
[注册] ──(提交审核)──→ [待审核] ──(审核通过/驳回)──→ [已激活/已驳回]
                                              └──(激活后)──→ [正常使用]
[正常使用] ──(管理员禁用)──→ [已禁用]
[已禁用] ──(管理员启用)──→ [正常使用]
[正常使用/已禁用] ──(管理员删除)──→ [已删除](逻辑删除)
```

### 2.2.2 密码策略规范

**密码复杂度规则（可配置）：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| 最小长度 | 8位 | 支持6-32位配置 |
| 大写字母 | 至少1个 | 开/关 |
| 小写字母 | 至少1个 | 开/关 |
| 数字 | 至少1个 | 开/关 |
| 特殊字符 | 至少1个 | 支持!@#$%^&*等 |
| 有效期 | 90天 | 到期前7天开始提醒 |
| 历史禁止 | 5次 | 不能使用最近N次密码 |
| 登录重试 | 5次 | 连续失败5次锁定30分钟 |

**密码强度校验实现（Java）：**
```java
@Component
public class PasswordPolicyValidator {
    private final PasswordPolicy policy;
    
    public ValidationResult validate(String plainPassword) {
        ValidationResult result = new ValidationResult();
        if (plainPassword.length() < policy.getMinLength()) {
            result.addError("密码长度不能少于" + policy.getMinLength() + "位");
        }
        if (policy.isRequireUppercase() && !Pattern.compile("[A-Z]").matcher(plainPassword).find()) {
            result.addError("密码必须包含大写字母");
        }
        // ... 其他校验
        return result;
    }
}
```

**密码哈希实现：**
```java
// bcrypt rounds=10，每次改密重新计算
String passwordHash = BCrypt.hashpw(plainPassword, BCrypt.gensalt(10));
// 验证
boolean matches = BCrypt.checkpw(inputPassword, storedHash);
```

### 2.2.3 批量导入规范

**导入模板格式（Excel）：**
| 用户名 | 姓名 | 手机号 | 邮箱 | 所属组织编码 | 角色编码 | 备注 |
|--------|------|--------|------|------------|---------|------|
| zhangsan | 张三 | 13800138001 | zs@xxx.com | ORG-001-003 | USER | 必填 |
| lisi | 李四 | 13800138002 | ls@xxx.com | ORG-001-004 | USER,MANAGER | |

**导入校验规则：**
1. 用户名：3-50位字母数字下划线，不重复
2. 手机号：11位数字，不重复
3. 组织编码：必须在系统中存在，否则自动创建（可选）
4. 角色编码：必须在系统中存在，多角色用逗号分隔
5. 校验通过后批量写入（每批500条事务提交）
6. 校验失败生成错误日志文件，定位失败行号和原因

## 2.3 身份认证需求（F3）

### 2.3.1 认证方式对比

| 认证方式 | 安全等级 | 用户体验 | 部署成本 | 适用场景 |
|---------|:-------:|:--------:|:--------:|---------|
| 用户名+密码 | ★★★ | ★★★★★ | 低 | 日常登录 |
| 短信验证码 | ★★★★ | ★★★★ | 中 | 密码重置、二次验证 |
| TOTP动态令牌 | ★★★★★ | ★★★ | 低 | 高安全场景 |
| 数字证书(SM2) | ★★★★★ | ★★ | 高 | 等保三级合规 |
| 生物特征(预留) | ★★★★★ | ★★★★★ | 高 | 移动端（二期） |

### 2.3.2 OAuth2授权码模式流程（核心SSO协议）

```
Step 1: 用户访问客户端应用，未登录
Step 2: 客户端构造授权请求，重定向到认证中心
  GET /oauth2/authorize?
    response_type=code
    &client_id=app-oa-001
    &redirect_uri=https://oa.xxx.com/callback
    &state=xyz123
    &scope=openid profile

Step 3: 用户输入凭证，认证中心验证身份
Step 4: 验证通过，生成授权码，重定向回客户端
  HTTP 302
  Location: https://oa.xxx.com/callback?
    code=A1b2C3d4E5f6
    &state=xyz123

Step 5: 客户端用授权码换取AccessToken
  POST /oauth2/token
  Content-Type: application/x-www-form-urlencoded
  grant_type=authorization_code
  &code=A1b2C3d4E5f6
  &redirect_uri=https://oa.xxx.com/callback
  &client_id=app-oa-001
  &client_secret=secret123

Step 6: 认证中心返回Token
  {
    "access_token": "eyJhbGciOiJSUzI1NiJ9...",
    "token_type": "Bearer",
    "expires_in": 900,
    "refresh_token": "dGhpcyBpcyBhIHJlZnJl...",
    "id_token": "eyJraWQiOiJyc2..."
  }
```

### 2.3.3 JWT Token结构

```json
// Header
{
  "alg": "RS256",
  "kid": "key-202607-v1",
  "typ": "JWT"
}

// Payload
{
  "sub": "zhangsan",
  "userId": 12345,
  "name": "张三",
  "orgId": 7,
  "orgName": "信息中心",
  "roles": ["USER", "DEPT_MGR"],
  "authMethod": "PASSWORD",
  "iss": "https://auth.xxx.com",
  "aud": ["app-oa-001", "app-fin-002"],
  "iat": 1720771200,
  "exp": 1720772100,
  "jti": "unique-token-id-001"
}
```

## 2.4 性能需求对应分析

| 指标 | 要求值 | 设计目标 | 实现保障措施 |
|------|--------|---------|------------|
| 用户规模 | 50,000 | 100,000 | 分库分表设计，按组织ID哈希分片 |
| 并发认证 | 500 TPS | 1,500 TPS | 认证服务3节点集群+Redis缓存+连接池优化 |
| SSO响应 | ≤2s(95%) | ≤1s(95%) | 缓存命中时≤200ms，未命中时≤800ms |
| 可用性 | 99.9% | 99.95% | 多节点部署+Nacos健康检查+自动重启 |
| 日志写入 | 1,000条/s | 3,000条/s | ES集群3节点+Bulk批量写入+MQ削峰 |
| 组织同步 | ≤5min | ≤2min | 增量同步机制+并行处理 |
