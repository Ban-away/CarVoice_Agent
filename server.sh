#!/bin/bash

# 创建日志目录
mkdir -p log/

# 项目根目录
BASE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# 失败服务列表
FAILED_SERVICES=()

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
    
    # 获取日志最后一行作为错误原因
    local error_msg=$(tail -n 3 "$log_file" 2>/dev/null | tr '\n' ';' || echo "未知错误")
    FAILED_SERVICES+=("$service_name: $error_msg")
    echo "❌ $service_name 启动失败: $error_msg"
    return 1
}

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
nohup "$BASE_DIR/redis-6.0.8/src/redis-server" > "$BASE_DIR/log/redis.log" 2>&1 &
check_service_by_port "Redis" 6379 "$BASE_DIR/log/redis.log"

# 拒识服务（端口 8007）
echo "启动拒识服务..."
cd "$BASE_DIR/train"
nohup python reject_infer.py > "$BASE_DIR/log/reject.log" 2>&1 &
check_service_by_port "拒识服务" 8007 "$BASE_DIR/log/reject.log"

# 意图召回服务（端口 8008）
echo "启动意图识别服务..."
nohup python intent_infer.py > "$BASE_DIR/log/intent.log" 2>&1 &
check_service_by_port "意图识别服务" 8008 "$BASE_DIR/log/intent.log"

# 大模型nlu服务（端口 8009）
echo "启动NLU服务..."
cd "$BASE_DIR/function_call"
nohup python chatnlu_infer.py > "$BASE_DIR/log/nlu.log" 2>&1 &
check_service_by_port "NLU服务" 8009 "$BASE_DIR/log/nlu.log"

# 入口服务（端口 8080）
echo "启动入口服务..."
cd "$BASE_DIR"
nohup python start.py > "$BASE_DIR/log/start.log" 2>&1 &
check_service_by_port "入口服务" 8080 "$BASE_DIR/log/start.log"

# 汇总结果
echo ""
echo "=================== 启动结果汇总 ==================="
if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    echo "🎉 所有服务启动成功！"
    echo ""
    echo "服务端口列表："
    echo "  - Redis: 6379"
    echo "  - 拒识服务: 8007"
    echo "  - 意图识别: 8008"
    echo "  - NLU服务: 8009"
    echo "  - 入口服务: 8080"
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