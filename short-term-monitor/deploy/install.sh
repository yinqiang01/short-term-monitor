#!/bin/bash
# 短线选股监控系统 - Linux一键安装脚本
set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

INSTALL_DIR="/opt/short-term-monitor"
SERVICE_NAME="short-term-monitor"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  短线选股监控系统 - 一键安装${NC}"
echo -e "${BLUE}========================================${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行: sudo bash $0${NC}"; exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}[1/5] 安装系统依赖...${NC}"
if command -v apt-get &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv python3-dev gcc g++ libffi-dev git >/dev/null 2>&1
else
    yum install -y python3 python3-pip python3-devel gcc gcc-c++ libffi-devel git >/dev/null 2>&1
fi
echo -e "${GREEN}  完成${NC}"

echo -e "${YELLOW}[2/5] 创建用户和目录...${NC}"
id -u monitor &>/dev/null || useradd -r -s /bin/false monitor
mkdir -p "$INSTALL_DIR" "$INSTALL_DIR/logs" "$INSTALL_DIR/data"
echo -e "${GREEN}  完成${NC}"

echo -e "${YELLOW}[3/5] 复制项目文件...${NC}"
cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/"
cp "$PROJECT_DIR/.env.example" "$INSTALL_DIR/.env"
chown -R monitor:monitor "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"
chmod -R 775 "$INSTALL_DIR/logs" "$INSTALL_DIR/data"
echo -e "${GREEN}  完成${NC}"

echo -e "${YELLOW}[4/5] 安装Python依赖...${NC}"
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}  完成${NC}"

echo -e "${YELLOW}[5/5] 配置systemd服务...${NC}"
cp "$PROJECT_DIR/deploy/monitor.service" /etc/systemd/system/$SERVICE_NAME.service
sed -i "s|/usr/bin/python3|$INSTALL_DIR/venv/bin/python|g" /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
echo -e "${GREEN}  完成${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  安装成功！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}下一步：${NC}"
echo "1. 配置飞书机器人:"
echo -e "   ${GREEN}vi $INSTALL_DIR/.env${NC}"
echo "   填写 FEISHU_WEBHOOK_URL 和 FEISHU_SECRET"
echo ""
echo "2. 配置自选股（可选）:"
echo "   在 .env 中设置 WATCHLIST=600519,000001"
echo ""
echo "3. 启动服务:"
echo -e "   ${GREEN}sudo systemctl start $SERVICE_NAME${NC}"
echo ""
echo "4. 查看状态:"
echo -e "   ${GREEN}sudo systemctl status $SERVICE_NAME${NC}"
echo -e "   ${GREEN}sudo journalctl -u $SERVICE_NAME -f${NC}"
echo ""
echo "5. 访问Web面板:"
echo -e "   ${GREEN}http://服务器IP:8080${NC}"
echo ""
echo -e "${YELLOW}飞书机器人配置方法：${NC}"
echo "  1. 飞书群 -> 设置 -> 群机器人 -> 添加机器人 -> 自定义机器人"
echo "  2. 复制 Webhook 地址填入 .env"
echo "  3. 安全设置建议勾选'签名校验'，复制密钥填入 FEISHU_SECRET"
echo "  4. 重启服务生效"
echo ""
