# Docker 验证待办

本文件只记录 Docker 本地验证的待办事项。当前项目发布说明不得声称容器化部署已经通过验证，除非后续确实完成以下步骤并记录真实结果。

## 当前状态

当前最终发布版只执行了本地 Python 脚本、pytest、API 检查、稳定性测试和离线评测。未在本阶段执行 Docker 镜像构建、容器启动或容器内 `/health` 验证。

因此简历、README 和项目说明中只能写：

```text
项目保留 Docker 后续验证待办；当前已完成本地脚本、测试和离线评测验证。
```

不能写：

```text
容器化部署已通过完整验证。
```

## 后续人工验证步骤

1. 安装并启动 Docker Desktop。
2. 确认 Docker Engine 正常运行：

```powershell
docker --version
```

3. 在项目根目录构建镜像：

```powershell
docker build -t ecommerce-after-sales-agent:local .
```

4. 启动容器，不传入真实 API Key：

```powershell
docker run --rm -p 8011:8011 ecommerce-after-sales-agent:local
```

5. 在另一个终端访问健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8011/health
```

6. 记录真实结果，包括 Docker 版本、build 是否成功、容器是否启动、`/health` 状态和失败原因。
