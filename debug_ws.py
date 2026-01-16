import websocket
import json
import threading
import time

# ================= 配置区域 =================
# 在这里填入你的 WebSocket 地址
WS_URL = "ws://127.0.0.1:25885" 
# ===========================================

def on_message(ws, message):
    """
    当收到服务器发来的消息时触发
    """
    print("-" * 50)
    print("【收到数据】 (Raw):")
    # 1. 打印原始数据（以防不是 JSON）
    print(message) 
    
    print("\n【尝试解析 JSON】:")
    try:
        # 2. 尝试解析为 JSON 并漂亮地打印出来
        data = json.loads(message)
        print(json.dumps(data, indent=4, ensure_ascii=False))
        
        # 3. 可以在这里预演一下提取逻辑，例如：
        # if 'lrc' in data:
        #     print(f"提取歌词: {data['lrc']}")
        
    except json.JSONDecodeError:
        print(">> 数据不是标准的 JSON 格式，无法解析结构。")
    except Exception as e:
        print(f">> 解析出错: {e}")
    print("-" * 50)

def on_error(ws, error):
    """
    当连接发生错误时触发
    """
    print(f"【错误】: {error}")

def on_close(ws, close_status_code, close_msg):
    """
    当连接关闭时触发
    """
    print("【连接已关闭】")
    print(f"状态码: {close_status_code}, 信息: {close_msg}")

def on_open(ws):
    """
    当连接建立成功时触发
    """
    print("【连接成功】")
    print(f"正在监听: {WS_URL} ...")
    # 如果服务端需要你发送验证消息才能开始推送，可以在这里写：
    # ws.send(json.dumps({"action": "subscribe"}))

if __name__ == "__main__":
    # 开启调试模式可以看到握手细节，不需要可以设为 False
    websocket.enableTrace(False) 
    
    if "你的端口" in WS_URL:
        print("❌ 错误：请先修改脚本中的 WS_URL 变量为你实际的 WebSocket 地址！")
    else:
        # 创建 WebSocketApp 实例
        ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        # 长连接运行
        # ping_interval=60: 每60秒发送一次心跳，防止断连
        try:
            ws.run_forever(ping_interval=60)
        except KeyboardInterrupt:
            print("\n用户手动停止")