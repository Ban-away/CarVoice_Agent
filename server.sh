#!/bin/bash

# 创建日志目录（不存在时自动新建）
mkdir -p log/

# 失败服务列表
FAILED_SERVICES=()

# 检查服务是否启动成功的函数
check_service() {
    local service_name=$1
    local log_file=$2
    local pid=$!
    
    sleep 3
    
    # 检查进程是否存在
    if ! kill -0 $pid 2>/dev/null; then
        # 获取日志最后一行作为错误原因
        local error_msg=$(tail -n 1 "$log_file" 2>/dev/null || echo "未知错误")
        FAILED_SERVICES+=("$service_name: $error_msg")
        echo "❌ $service_name 启动失败: $error_msg"
    else
        echo "✅ $service_name 启动成功"
    fi
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
nohup ./redis-6.0.8/src/redis-server > log/redis.log 2>&1 &
check_service "Redis" "log/redis.log"

# 拒识服务
echo "启动拒识服务..."
cd train
nohup python reject_infer.py > ../log/reject.log 2>&1 &
check_service "拒识服务" "../log/reject.log"

# 意图召回服务
echo "启动意图识别服务..."
nohup python intent_infer.py > ../log/intent.log 2>&1 &
check_service "意图识别服务" "../log/intent.log"

# 大模型nlu服务
echo "启动NLU服务..."
cd ../function_call
nohup python chatnlu_infer.py > ../log/nlu.log 2>&1 &
check_service "NLU服务" "../log/nlu.log"

# 入口服务 
echo "启动入口服务..."
cd ../
nohup python start.py > ./log/start.log 2>&1 &
check_service "入口服务" "./log/start.log"

# 汇总结果
echo ""
echo "=================== 启动结果汇总 ==================="
if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    echo "🎉 所有服务启动成功！"
else
    echo "❌ 以下服务启动失败："
    for failed in "${FAILED_SERVICES[@]}"; do
        echo "  - $failed"
    done
    echo ""
    echo "建议检查对应日志文件获取详细错误信息："
    echo "  - log/redis.log"
    echo "  - log/reject.log"
    echo "  - log/intent.log"
    echo "  - log/nlu.log"
    echo "  - log/start.log"
fi