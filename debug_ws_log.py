import websocket
import json
import threading
import time
import os

# ================= 配置区域 =================
# 1. 填入你的 WebSocket 地址
WS_URL = "ws://127.0.0.1:25885" 

# 2. 本地日志文件名
LOG_FILE = "ws_received_data.txt"
# ===========================================

def save_to_file(raw_data):
    """
    将原始数据追加写入到本地文件
    """
    try:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        # 分隔符，方便阅读
        separator = "-" * 50
        
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"【时间】: {current_time}\n")
            f.write(f"【内容】: {raw_data}\n")
            f.write(f"{separator}\n")
    except Exception as e:
        print(f"!! 写入文件失败: {e}")

def on_message(ws, message):
    """
    当收到服务器发来的消息时触发
    """
    # ----------------------------------------
    # 1. 控制台输出 (屏幕显示)
    # ----------------------------------------
    print("\n" + "=" * 50)
    print("【收到新数据】")
    
    # 尝试解析 JSON 以便在屏幕上漂亮地打印
    try:
        data = json.loads(message)
        # ensure_ascii=False 保证中文正常显示
        pretty_json = json.dumps(data, indent=4, ensure_ascii=False)
        print(pretty_json)
    except:
        # 如果不是JSON，直接打印原始字符串
        print(message)
    
    print("=" * 50)

    # ----------------------------------------
    # 2. 写入本地文件
    # ----------------------------------------
    save_to_file(message)
    print(f">> 数据已保存至 {LOG_FILE}")

def on_error(ws, error):
    print(f"【错误】: {error}")

def on_close(ws, close_status_code, close_msg):
    print("【连接已关闭】")
    print(f"状态码: {close_status_code}, 信息: {close_msg}")

def on_open(ws):
    print("【连接成功】")
    print(f"正在监听: {WS_URL}")
    print(f"数据将同时保存到: {os.path.abspath(LOG_FILE)}")

if __name__ == "__main__":
    websocket.enableTrace(False)
    
    if "你的端口" in WS_URL:
        print("❌ 错误：请先修改脚本中的 WS_URL 变量！")
    else:
        # 如果文件存在，先在开始时加个标记，区分不同次的运行
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n\n====== 新的运行会话开始 ======\n\n")

        ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        try:
            ws.run_forever(ping_interval=60)
        except KeyboardInterrupt:
            print("\n用户手动停止")