FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，避免 Python 写 pyc 缓存
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装依赖（利用 Docker 缓存层，依赖不变时不重新安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据卷挂载点（SQLite 数据库文件持久化）
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 5000

# 设置默认环境变量（生产环境关闭 debug）
ENV FLASK_DEBUG=0
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000
ENV DATABASE=/app/data/daomangquan.db

# 启动命令
CMD ["python", "run.py"]
