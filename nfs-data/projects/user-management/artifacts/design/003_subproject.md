# 第四章 详细设计

## 4.1 用户管理服务

### 4.1.1 组织管理模块

**接口规范：**

| 接口 | 方法 | URL | 说明 |
|------|:----:|-----|------|
| 获取组织树 | GET | /api/v1/orgs/tree | 返回完整组织树 |
| 查询组织详情 | GET | /api/v1/orgs/{id} | 返回单个组织 |
| 新增组织 | POST | /api/v1/orgs | 创建组织节点 |
| 修改组织 | PUT | /api/v1/orgs/{id} | 修改组织属性 |
| 删除组织 | DELETE | /api/v1/orgs/{id} | 删除空节点 |
| 合并组织 | POST | /api/v1/orgs/{id}/merge | 组织合并操作 |
| 查询变更历史 | GET | /api/v1/orgs/{id}/history | 返回变更记录列表 |

**组织树接口响应示例：**
```json
GET /api/v1/orgs/tree
Response 200:
{
  "code": 200,
  "data": {
    "id": 1,
    "name": "某单位",
    "children": [
      {
        "id": 2,
        "name": "办公室",
        "parentId": 1,
        "level": 2,
        "userCount": 15,
        "children": []
      },
      {
        "id": 3,
        "name": "信息中心",
        "parentId": 1,
        "level": 2,
        "userCount": 28,
        "children": [
          {
            "id": 4,
            "name": "软件科",
            "parentId": 3,
            "level": 3,
            "userCount": 12,
            "children": []
          }
        ]
      }
    ]
  },
  "timestamp": 1720771200000
}
```

**组织合并接口请求示例：**
```json
POST /api/v1/orgs/5/merge
Request:
{
  "targetOrgId": 7,
  "mergeType": "ALL",          // ALL=全部合并, USER_ONLY=仅人员
  "keepSourceOrg": false,      // 合并后是否保留源组织
  "reason": "机构改革，撤销信息中心下属运维科并入软件科"
}
Response 200:
{
  "code": 200,
  "message": "合并成功",
  "data": {
    "sourceOrgId": 5,
    "targetOrgId": 7,
    "movedUserCount": 8,
    "movedSubOrgCount": 2,
    "completedAt": "2026-07-12T10:30:00"
  }
}
```

### 4.1.2 用户管理模块

**用户状态变更状态机实现：**
```java
public enum UserStatus {
    REGISTERED("注册", "初始状态，等待审核"),
    PENDING_APPROVAL("待审核", "已提交审核申请"),
    ACTIVE("已激活", "正常使用状态"),
    DISABLED("已禁用", "管理员手动禁用"),
    DELETED("已删除", "逻辑删除"),
    REJECTED("已驳回", "审核未通过");

    private final String displayName;
    private final String description;

    // 状态流转规则
    private static final Map<UserStatus, Set<UserStatus>> transitions = new HashMap<>();
    static {
        transitions.put(REGISTERED, Set.of(PENDING_APPROVAL, DELETED));
        transitions.put(PENDING_APPROVAL, Set.of(ACTIVE, REJECTED));
        transitions.put(ACTIVE, Set.of(DISABLED, DELETED));
        transitions.put(DISABLED, Set.of(ACTIVE, DELETED));
        // REJECTED和DELETED为终态
    }

    public boolean canTransitionTo(UserStatus target) {
        return transitions.getOrDefault(this, Collections.emptySet()).contains(target);
    }
}
```

**用户创建接口：**
```json
POST /api/v1/users
Request:
{
  "username": "zhangsan",
  "password": "SM4加密后的密码",
  "name": "张三",
  "phone": "13800138001",
  "email": "zs@xxx.com",
  "orgIds": [{"orgId": 7, "isPrimary": true}],
  "roleCodes": ["USER", "DEPT_MGR"],
  "source": "MANUAL_CREATE"
}
Response 201:
{
  "code": 201,
  "data": {
    "userId": 12345,
    "username": "zhangsan",
    "status": "ACTIVE",
    "createdAt": "2026-07-12T10:30:00"
  },
  "message": "用户创建成功"
}
```

### 4.1.3 HR同步模块

**SCIM 2.0 事件处理流程：**
```
HR系统推送SCIM事件
  → API网关接收 /scim/v2/**
  → 路由至用户管理服务
  → 解析SCIM JSON payload
  → 映射到内部用户模型
  → 校验必填字段
  → 检查是否存在（username/employeeNumber）
  → 存在→执行更新(对比差异字段)
  → 不存在→执行创建
  → 写入审计日志
  → 返回SCIM标准响应
```

## 4.2 身份认证服务

### 4.2.1 认证模块

**密码认证实现流程：**
```java
@Service
public class AuthenticationService {
    
    public AuthResult authenticate(AuthRequest request) {
        // 1. 校验验证码（防止暴力破解）
        checkCaptcha(request.getSessionId(), request.getCaptcha());
        
        // 2. 查询用户
        User user = userRepository.findByUsername(request.getUsername());
        if (user == null || user.getStatus() != UserStatus.ACTIVE) {
            loginAttemptService.recordFailure(request.getUsername(), request.getIp());
            throw new AuthenticationException("用户名或密码错误");
        }
        
        // 3. bcrypt验证密码
        if (!BCrypt.checkpw(request.getPassword(), user.getPasswordHash())) {
            loginAttemptService.recordFailure(request.getUsername(), request.getIp());
            // 检查是否需要锁定
            if (loginAttemptService.shouldLock(user.getId())) {
                user.setStatus(UserStatus.DISABLED);
                userRepository.save(user);
                throw new AuthenticationException("密码错误次数过多，账号已锁定");
            }
            throw new AuthenticationException("用户名或密码错误");
        }
        
        // 4. 生成Token
        loginAttemptService.reset(user.getId());
        TokenPair tokens = tokenService.generateTokenPair(user);
        
        // 5. 异步发送审计日志
        auditService.sendAsync(new AuditEvent(
            user.getId(), request.getIp(),
            AuditAction.LOGIN, null, true
        ));
        
        return AuthResult.success(tokens);
    }
}
```

### 4.2.2 令牌管理

**JWT生成（RS256签名）：**
```java
@Component
public class JwtTokenProvider {
    
    private final RSAPrivateKey privateKey;
    private final RSAPublicKey publicKey;
    
    public String generateAccessToken(User user) {
        Instant now = Instant.now();
        return Jwts.builder()
            .issuer("https://auth.xxx.com")
            .subject(user.getUsername())
            .claim("userId", user.getId())
            .claim("name", user.getName())
            .claim("orgId", user.getPrimaryOrgId())
            .claim("roles", user.getRoleCodes())
            .claim("authMethod", "PASSWORD")
            .issuedAt(Date.from(now))
            .expiration(Date.from(now.plus(15, ChronoUnit.MINUTES)))
            .id(UUID.randomUUID().toString())
            .signWith(privateKey, SignatureAlgorithm.RS256)
            .compact();
    }
}
```

### 4.2.3 多因子认证

**TOTP 实现（RFC 6238）：**
```java
public class TotpProvider {
    private static final int TIME_STEP = 30;        // 30秒有效期
    private static final int DIGITS = 6;             // 6位数字
    private static final String ALGORITHM = "HmacSHA1";

    public String generateSecret() {
        byte[] bytes = new byte[20];
        new SecureRandom().nextBytes(bytes);
        return Base32.encode(bytes);
    }

    public boolean verify(String secret, String code) {
        long timeWindow = Instant.now().getEpochSecond() / TIME_STEP;
        // 允许前后各1个窗口（共3个窗口，90秒）
        for (long offset = -1; offset <= 1; offset++) {
            long hash = generateHash(Base32.decode(secret), timeWindow + offset);
            if (String.format("%06d", hash % 1_000_000).equals(code)) {
                return true;
            }
        }
        return false;
    }
}
```

## 4.3 权限管理服务

### 4.3.1 授权判定实现

```java
@Component
public class AuthorizationDecisionManager {
    
    @Cacheable(value = "permissions", key = "#userId + ':' + #resourceId")
    public boolean checkPermission(Long userId, String resourceId, String action) {
        // 1. 获取用户所有角色
        List<Role> roles = roleRepository.findByUserId(userId);
        
        // 2. 合并所有角色的权限
        Set<String> permissions = new HashSet<>();
        for (Role role : roles) {
            permissions.addAll(getPermissionsWithInheritance(role));
        }
        
        // 3. 判定
        String required = resourceId + ":" + action;
        return permissions.contains(required) || permissions.contains(resourceId + ":*");
    }
    
    private Set<String> getPermissionsWithInheritance(Role role) {
        Set<String> result = new HashSet<>();
        Role current = role;
        while (current != null) {
            result.addAll(permissionRepository.findByRoleId(current.getId())
                .stream()
                .map(p -> p.getResourceId() + ":" + p.getAction())
                .collect(Collectors.toSet()));
            current = current.getParentRole();
        }
        return result;
    }
}
```

## 4.4 安全审计服务

### 4.4.1 日志格式定义

```json
{
  "logId": "audit-20260712-000001",
  "timestamp": "2026-07-12T10:30:15.123Z",
  "userId": 12345,
  "username": "zhangsan",
  "userIp": "192.168.1.100",
  "sessionId": "sess-abc-123",
  "actionType": "LOGIN",
  "actionDetail": "用户名密码认证",
  "resourceType": "AUTH_SERVICE",
  "resourceId": null,
  "result": "SUCCESS",
  "failReason": null,
  "duration": 156,
  "userAgent": "Mozilla/5.0...",
  "prevHash": "a1b2c3d4e5f6...",
  "hash": "f6e5d4c3b2a1..."
}
```

### 4.4.2 哈希链保护实现

```java
@Component
public class AuditLogProtector {
    
    public String computeHash(AuditLog log, String prevHash) {
        String content = String.format("%s|%s|%s|%s|%s|%s",
            log.getTimestamp().toString(),
            log.getUserId(),
            log.getActionType(),
            log.getResourceId(),
            log.getResult(),
            prevHash
        );
        return DigestUtils.sha3_256Hex(content);   // SM3哈希
    }
    
    public boolean verifyChain(List<AuditLog> logs) {
        String prevHash = "";
        for (AuditLog log : logs) {
            String expected = computeHash(log, prevHash);
            if (!expected.equals(log.getHash())) {
                return false;  // 日志被篡改
            }
            prevHash = expected;
        }
        return true;
    }
}
```

### 4.4.3 ES索引映射

```json
PUT /audit-logs-2026-07
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "refresh_interval": "5s"
  },
  "mappings": {
    "properties": {
      "timestamp":     { "type": "date" },
      "userId":        { "type": "long" },
      "username":      { "type": "keyword" },
      "userIp":        { "type": "ip" },
      "actionType":    { "type": "keyword" },
      "resourceType":  { "type": "keyword" },
      "resourceId":    { "type": "keyword" },
      "result":        { "type": "keyword" },
      "failReason":    { "type": "text" },
      "duration":      { "type": "integer" },
      "detail":        { "type": "text", "analyzer": "ik_max_word" },
      "hash":          { "type": "keyword" },
      "prevHash":      { "type": "keyword" }
    }
  }
}
```
