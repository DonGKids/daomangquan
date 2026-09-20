# 导茫犬 · 大学生扫"茫"信息服务平台

> 让每一个迷茫的大学生找到方向

专为大学生打造的垂直信息服务平台，通过迷茫检测 + 个性化推荐 + 分类信息库 + 互助论坛，帮助大学生解决信息碎片化问题。

## 核心功能

| 功能 | 说明 |
|------|------|
| 迷茫检测 | 输入当前困惑，系统提取关键词 + 匹配分类 + 生成个性化推荐 |
| 分类信息库 | 生活常识 / 升学就业 / 法律知识 / 创业资讯 四大板块，支持分类筛选和关键词搜索 |
| 互助论坛 | 发帖、评论、点赞、删除、分页，完整的用户交互 |
| 个人中心 | 用户信息、检测历史、发帖历史、反馈提交 |
| 个性化推荐 | 基于迷茫检测结果，在首页展示"为你推荐"内容 |

## 技术栈

- **后端**：Python + Flask 3.1.3
- **数据库**：SQLite（首次启动自动建表，零配置）
- **前端**：HTML5 + CSS3 + 原生 JavaScript + Jinja2 模板
- **安全**：Werkzeug 密码哈希、参数化查询防 SQL 注入、会话管理
- **部署**：Docker + Docker Compose，一键容器化部署

## 快速开始

提供两种运行方式：本地运行 或 Docker 部署。

### 方式一：本地运行

#### 环境要求

- Python 3.10+
- pip

#### 安装与运行

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/daomangquan.git
cd daomangquan

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 运行
python run.py
```

浏览器打开 http://127.0.0.1:5000 即可访问。

数据库 `daomangquan.db` 会在首次启动时自动创建，无需手动操作。

### 方式二：Docker 部署

#### 环境要求

- Docker
- Docker Compose

#### 一键启动

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/daomangquan.git
cd daomangquan

# 2. 设置密钥（生产环境必须修改）
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# 3. 构建并启动
docker-compose up -d --build
```

浏览器打开 http://127.0.0.1:5000 即可访问。

- 数据库文件持久化到宿主机 `./data/daomangquan.db`，容器重启数据不丢失
- 查看日志：`docker-compose logs -f`
- 停止服务：`docker-compose down`

### 环境变量（可选）

复制 `.env.example` 为 `.env` 并修改：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| SECRET_KEY | dev-only... | 会话加密密钥，生产环境必须修改 |
| FLASK_DEBUG | 1 | 调试模式，生产环境设为 0 |
| FLASK_HOST | 127.0.0.1 | 监听地址 |
| FLASK_PORT | 5000 | 监听端口 |
| DATABASE | daomangquan.db | 数据库文件路径 |

## 项目结构

```
daomangquan/
├── app/
│   ├── __init__.py          # 应用工厂 create_app()
│   ├── models.py            # 数据库模型与初始化（6 张表）
│   ├── routes.py            # 路由与业务逻辑
│   ├── static/
│   │   └── js/main.js       # 前端公共 JS
│   └── templates/           # Jinja2 模板（10 个页面）
│       ├── base.html        # 基础模板（导航栏 + api 封装）
│       ├── index.html       # 首页
│       ├── login.html       # 登录
│       ├── register.html    # 注册
│       ├── maze.html        # 迷茫检测
│       ├── info.html        # 信息库
│       ├── forum.html       # 论坛列表
│       ├── post_detail.html # 帖子详情
│       └── profile.html     # 个人中心
├── config.py                # 配置类
├── run.py                   # 启动入口
├── Dockerfile               # Docker 镜像构建
├── docker-compose.yml       # Docker Compose 编排
├── .dockerignore            # Docker 构建排除
├── requirements.txt         # 依赖清单
├── .env.example             # 环境变量示例
└── .gitignore
```

## 数据库表结构

| 表名 | 说明 |
|------|------|
| users | 用户（用户名、密码哈希、学号、学院、专业） |
| maze_detect | 迷茫检测记录（内容、关键词、分类，JSON 存储） |
| categories | 信息分类（4 个默认分类） |
| infos | 信息库内容（标题、内容、分类关联） |
| posts | 论坛帖子 |
| comments | 帖子评论 |
| post_likes | 帖子点赞（UNIQUE 约束防重复） |
| feedback | 用户反馈 |

## License

MIT License - 详见 [LICENSE](LICENSE)
