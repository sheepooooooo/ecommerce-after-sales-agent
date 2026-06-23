# Docker 验证待办

当前环境执行：

```powershell
docker --version
```

结果：PowerShell 未识别 `docker` 命令。因此本次未执行镜像构建、容器启动或 `/health` 验证。

## 待完成步骤

1. 安装 Docker Desktop。
2. 启动 Docker Desktop，并确认 Docker Engine 正常运行。
3. 运行：

```powershell
docker --version
```

4. 在项目根目录构建镜像：

```powershell
docker build -t ecommerce-after-sales-agent:local .
```

5. 启动容器，不传入真实 API Key：

```powershell
docker run --rm -p 8011:8011 ecommerce-after-sales-agent:local
```

6. 在另一个终端访问健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8011/health
```

7. 停止容器。

8. 记录真实结果，包括：

- Docker 版本。
- build 是否成功。
- 容器是否启动。
- `/health` HTTP 状态和返回体。
- 失败原因，如依赖安装失败、端口占用、启动超时。

## 当前简历写法

当前只能写：

```text
Dockerfile 已准备，Docker 本地构建与 /health 验证待补充。
```

不能写：

```text
已完成 Docker 部署验证。
```
