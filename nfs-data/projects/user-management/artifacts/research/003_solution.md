# 方案知识（按需求/总体/分项/技术域摘录）

## 一、需求维度
### 可复用方案片段
- Keycloak开源方案的用户联合（User Federation）支持LDAP/AD自动同步
- Authing支持SCIM协议与HR系统（北森/用友）实时同步
- 某央企项目实现15万用户、200个应用的统一认证，采用分级分域授权策略
- 某省政务平台采用"统一认证+分域授权"混合模型，满足跨部门数据隔离需求

### 典型配置参考
- SSO会话超时：空闲超时30分钟，绝对超时12小时
- 密码策略：8位以上+大小写+数字+特殊字符，90天更换
- 锁定策略：连续5次失败锁定30分钟

## 二、总体维度
### 可复用架构方案
```
客户端 → Nginx/API Gateway → 认证服务 → Redis Session
                            → 授权服务 → MySQL/达梦
                            → 用户服务 → MySQL/达梦
                            → 审计服务 → Elasticsearch
```
- Gateway层：Spring Cloud Gateway统一路由，限流熔断
- 认证服务：无状态设计，JWT Token承载认证信息
- 各服务间通过gRPC/REST通信，异步消息用RabbitMQ

### 国产化部署
- 麒麟V10 + 东方通TongWeb + 达梦DM8
- Redis替代方案：KeyDB/Tendis（适配国产ARM架构）

## 三、分项维度
### 用户中心参考实现
- 用户数据模型：用户表(user)+组织表(org)+用户-组织关联表
- 组织树：parent_id + level + path 经典实现
- 批量导入：EasyExcel逐行解析+验证+批量写入

### 认证中心参考实现
- Spring Security + OAuth2 Client/Resource Server
- JWT生成：nimbus-jose-jwt 或 jjwt 库
- TOTP实现：Google Authenticator兼容（RFC 6238）
- 验证码：集成阿里云/腾讯云短信SDK

### 权限中心参考实现
- Spring Security Method Security + @PreAuthorize
- 动态数据权限：MyBatis拦截器注入当前用户组织ID
- 角色缓存：Redis Hash存储角色-权限映射，TTL=5分钟

### 审计中心参考实现
- Logback + Kafka + Logstash + Elasticsearch
- 每条审计日志包含：[时间][用户ID][IP][操作类型][资源ID][结果][详情JSON]
- 索引按月分片，保留6个月

## 四、技术域维度
### 密码安全方案
- 注册/改密：前端SM4加密传输 → 后端SM3+bcrypt双重哈希存储
- 登录验证：前端SM4密文→后端解密→查询用户→bcrypt比对
- Token：RS256签名的JWT，公钥/私钥对管理

### 容器化部署参考
```yaml
# K8s Deployment 参考
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  replicas: 3
  selector: ...
  template:
    spec:
      containers:
      - name: auth
        image: registry.internal/auth-service:1.0
        resources:
          requests: {cpu: 500m, memory: 512Mi}
          limits: {cpu: 2, memory: 2Gi}
```

### 关键性能基线
- 单节点认证服务：500 TPS（2C4G配置）
- Redis缓存认证Token：100万Token占用约500MB内存
- ES日志写入：单节点约2000条/秒
