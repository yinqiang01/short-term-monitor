"""
短线选股监控系统 - 主程序入口
用法:
    python -m src.main              # 启动监控+Web
    python -m src.main --web-only   # 仅启动Web面板
    python -m src.main --monitor-only # 仅启动监控（无Web）
    python -m src.main --test       # 测试模式
"""
import argparse
import sys
import threading
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import get_config
from src.logger import get_logger
from src.scheduler import MonitorScheduler
from src.web import run_web

logger = get_logger("Main")


def main():
    parser = argparse.ArgumentParser(description="短线选股监控系统")
    parser.add_argument("--web-only", action="store_true", help="仅启动Web面板")
    parser.add_argument("--monitor-only", action="store_true", help="仅启动监控")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    args = parser.parse_args()

    config = get_config(args.config).config
    logger.info("=" * 60)
    logger.info("短线选股监控系统 v1.0.0 启动")
    logger.info("=" * 60)

    if args.web_only:
        # 仅Web模式
        logger.info("模式：仅Web面板")
        run_web(config)
        return

    if args.monitor_only:
        # 仅监控模式
        logger.info("模式：仅监控（无Web）")
        scheduler = MonitorScheduler(config)
        scheduler.start()
        return

    # 默认：监控 + Web 同时运行
    logger.info("模式：监控 + Web面板")

    # 在独立线程运行监控
    scheduler = MonitorScheduler(config)
    monitor_thread = threading.Thread(target=scheduler.start, daemon=True)
    monitor_thread.start()

    # 主线程运行Web
    try:
        run_web(config)
    except KeyboardInterrupt:
        logger.info("用户中断，程序退出")
        scheduler.stop()


if __name__ == "__main__":
    main()
