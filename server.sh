#!/bin/bash

# 创建日志目录
mkdir -p log/

# 项目根目录
BASE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# 设置PYTHONPATH，解决模块导入问题
export PYTHONPATH="$BASE_DIR:$PYTHONPATH"

# 默认端口配置（可通过环境变量覆盖）
REDIS_PORT=${REDIS_PORT:-6379}
REJECT_PORT=${REJECT_PORT:-8007}
INTENT_PORT=${INTENT_PORT:-8008}
NLU_PORT=${NLU_PORT:-8009}
ENTRY_PORT=${ENTRY_PORT:-8080}

# 失败服务列表
FAILED_SERVICES=()

# 检查端口是否被占用
check_port() {
    local port=$1
    if ss -tlnp | grep -q ":$port "; then
        return 0  # 端口被占用
    elif nc -z localhost $port 2>/dev/null; then
        return 0  # 端口被占用
    else
        return 1  # 端口可用
    fi
}

# 检查服务是否启动成功（通过检查端口）
check_service_by_port() {
    local service_name=$1
    local port=$2
    local log_file=$3
    
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null; then
            echo "✅ $service_name 启动成功 (端口 $port)"
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    
    # 获取日志最后3行作为错误原因
    local error_msg=$(tail -n 3 "$log_file" 2>/dev/null | tr '\n' ';' || echo "未知错误")
    FAILED_SERVICES+=("$service_name: $error_msg")
    echo "❌ $service_name 启动失败: $error_msg"
    return 1
}

# 加载环境变量
echo "加载环境变量..."
if [ -f "$BASE_DIR/config/config.ini" ]; then
    source "$BASE_DIR/config/config.ini"
    echo "✅ 环境变量加载成功"
else
    echo "⚠️ 未找到 config/config.ini，使用系统环境变量"
fi

# 检查模型文件是否存在
echo "检查模型文件..."
MODEL_MISSING=()

REJECT_MODEL="$BASE_DIR/train/saved/reject/bert_tiny.ckpt"
INTENT_MODEL="$BASE_DIR/train/saved/intent/bert.ckpt"

if [ ! -f "$REJECT_MODEL" ]; then
    MODEL_MISSING+=("拒识模型: $REJECT_MODEL")
fi
if [ ! -f "$INTENT_MODEL" ]; then
    MODEL_MISSING+=("意图模型: $INTENT_MODEL")
fi

if [ ${#MODEL_MISSING[@]} -gt 0 ]; then
    echo ""
    echo "❌ 以下模型文件不存在："
    for missing in "${MODEL_MISSING[@]}"; do
        echo "  - $missing"
    done
    echo ""
    echo "请先运行训练命令生成模型："
    echo "  cd $BASE_DIR/train"
    echo "  python run.py --model bert --data intent"
    echo "  python run.py --model bert_tiny --data reject"
    exit 1
fi

# 检查端口占用情况
echo "检查端口占用情况..."
PORT_CONFLICTS=()

if check_port $REDIS_PORT; then
    PORT_CONFLICTS+=("Redis (端口 $REDIS_PORT)")
fi
if check_port $REJECT_PORT; then
    PORT_CONFLICTS+=("拒识服务 (端口 $REJECT_PORT)")
fi
if check_port $INTENT_PORT; then
    PORT_CONFLICTS+=("意图识别服务 (端口 $INTENT_PORT)")
fi
if check_port $NLU_PORT; then
    PORT_CONFLICTS+=("NLU服务 (端口 $NLU_PORT)")
fi
if check_port $ENTRY_PORT; then
    PORT_CONFLICTS+=("入口服务 (端口 $ENTRY_PORT)")
fi

# 如果有端口冲突，提示用户
if [ ${#PORT_CONFLICTS[@]} -gt 0 ]; then
    echo ""
    echo "⚠️ 以下端口已被占用："
    for conflict in "${PORT_CONFLICTS[@]}"; do
        echo "  - $conflict"
    done
    echo ""
    echo "请释放占用的端口，或通过环境变量指定其他端口："
    echo "  export REDIS_PORT=6380"
    echo "  export REJECT_PORT=8017"
    echo "  export INTENT_PORT=8018"
    echo "  export NLU_PORT=8019"
    echo "  export ENTRY_PORT=8090"
    echo ""
    echo "示例："
    echo "  REDIS_PORT=6380 REJECT_PORT=8017 bash server.sh"
    exit 1
fi

# 启动redis server（首次运行会自动下载编译，之后直接启动）
if [ ! -d "redis-6.0.8" ]; then
    echo "首次运行，开始下载并编译Redis..."
    wget http://download.redis.io/releases/redis-6.0.8.tar.gz
    tar -xzvf redis-6.0.8.tar.gz
    rm -rf redis-6.0.8.tar.gz
    cd redis-6.0.8
    make -j 10
    cd ..
    echo "Redis编译完成"
fi

echo "启动Redis数据库..."
nohup "$BASE_DIR/redis-6.0.8/src/redis-server" --port $REDIS_PORT > "$BASE_DIR/log/redis.log" 2>&1 &
check_service_by_port "Redis" $REDIS_PORT "$BASE_DIR/log/redis.log"

# 拒识服务
echo "启动拒识服务..."
cd "$BASE_DIR/train"
nohup python -c "import sys; sys.path.insert(0, '.'); exec(open('reject_infer.py').read())" > "$BASE_DIR/log/reject.log" 2>&1 &
check_service_by_port "拒识服务" $REJECT_PORT "$BASE_DIR/log/reject.log"

# 意图召回服务
echo "启动意图识别服务..."
nohup python -c "import sys; sys.path.insert(0, '.'); exec(open('intent_infer.py').read())" > "$BASE_DIR/log/intent.log" 2>&1 &
check_service_by_port "意图识别服务" $INTENT_PORT "$BASE_DIR/log/intent.log"

# 大模型nlu服务
echo "启动NLU服务..."
cd "$BASE_DIR/function_call"
nohup python -c "import sys; sys.path.insert(0, '.'); exec(open('chatnlu_infer.py').read())" > "$BASE_DIR/log/nlu.log" 2>&1 &
check_service_by_port "NLU服务" $NLU_PORT "$BASE_DIR/log/nlu.log"

# 入口服务
echo "启动入口服务..."
cd "$BASE_DIR"
nohup python -c "import sys; sys.path.insert(0, '.'); exec(open('start.py').read())" > "$BASE_DIR/log/start.log" 2>&1 &
check_service_by_port "入口服务" $ENTRY_PORT "$BASE_DIR/log/start.log"

# 汇总结果
echo ""
echo "=================== 启动结果汇总 ==================="
if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    echo "🎉 所有服务启动成功！"
    echo ""
    echo "服务端口列表："
    echo "  - Redis: $REDIS_PORT"
    echo "  - 拒识服务: $REJECT_PORT"
    echo "  - 意图识别: $INTENT_PORT"
    echo "  - NLU服务: $NLU_PORT"
    echo "  - 入口服务: $ENTRY_PORT"
else
    echo "❌ 以下服务启动失败："
    for failed in "${FAILED_SERVICES[@]}"; do
        echo "  - $failed"
    done
    echo ""
    echo "建议检查对应日志文件获取详细错误信息："
    echo "  - $BASE_DIR/log/redis.log"
    echo "  - $BASE_DIR/log/reject.log"
    echo "  - $BASE_DIR/log/intent.log"
    echo "  - $BASE_DIR/log/nlu.log"
    echo "  - $BASE_DIR/log/start.log"
fi