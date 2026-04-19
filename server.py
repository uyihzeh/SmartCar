# -*- coding: utf-8 -*-
# 功能：接收树莓派传输的摄像头画面，显示草莓识别结果（跨平台兼容版）

# 导入必要的库
import cv2          # OpenCV库：用于显示画面、解码图片
import socket       # 网络库：用于和树莓派建立网络连接、接收数据
import struct       # 数据打包库：用于解析树莓派发送的数据长度
import numpy as np  # 数值计算库：用于将字节数据转为OpenCV能识别的格式
import os           # 系统库：用于设置OpenCV显示参数，避免窗口无响应

# ---------------------- 基础配置----------------------
PORT = 8192                          # 端口号：和树莓派保持一致即可
MAX_FRAME_SIZE = 1024 * 1024         # 最大帧尺寸：1MB（过滤异常数据，避免报错）
WINDOW_NAME = "Strawberry Recognition"       # 窗口标题（英文更稳定）
# ---------------------------------------------------------------------------

# 关键设置：避免Windows系统下OpenCV窗口无响应/乱码问题
os.environ["QT_QPA_PLATFORM"] = "windows"  # 强制使用Windows兼容的显示后端
cv2.ocl.setUseOpenCL(False)               # 禁用OpenCL，避免显示冲突

# 1. 创建网络服务器（相当于电脑开一个接收数据的端口）
# AF_INET：使用TCP/IP协议；SOCK_STREAM：使用TCP可靠传输（不会丢包）
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("", PORT))  # 绑定到本机所有IP的端口（""表示本机任意IP）
server.listen(1)         # 监听连接：只允许1个树莓派连接（避免冲突）
print(" 电脑端已启动，等待树莓派连接...")

# 2. 接受树莓派的连接（和树莓派建立专属数据通道）
# client：和树莓派通信的专属通道；addr：树莓派的IP和端口
client, addr = server.accept()
client.settimeout(5)  # 超时设置：5秒没收到数据就跳过，避免卡死
print(f" 已连接树莓派：{addr}（IP+端口）")

# 3. 提前创建显示窗口（先开一个空窗口，避免画面显示不出来）
# WINDOW_NORMAL：窗口可缩放；resizeWindow：设置窗口初始大小（640x480，看得清）
cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WINDOW_NAME, 640, 480)

# 4. 初始化变量（存放接收数据的「缓冲区」）
data = b""                              # 空字节串：存放待处理的原始数据
payload_size = struct.calcsize("!I")    # 数据长度的打包格式：!I（网络字节序4字节）
                                        # 小白理解：树莓派先传4字节「数据长度」，再传实际画面

# 核心循环：持续接收并显示画面（直到按q退出）
try:
    while True:
        # ---------------------- 步骤1：接收数据长度（固定4字节） ----------------------
        # 循环接收，直到凑够4字节（数据长度）
        while len(data) < payload_size:
            # 只接收缺少的字节数（避免多收导致粘包）
            # 4096：每次最多收4KB数据，小白理解：一次收太多会卡，分批收更稳
            packet = client.recv(payload_size - len(data))
            if not packet:  # 如果没收到数据，说明树莓派断开连接
                print(" 树莓派已断开连接")
                break
            data += packet  # 把收到的字节拼到缓冲区
        if not data:  # 缓冲区为空，退出循环
            break

        # ---------------------- 步骤2：解析数据长度并校验 ----------------------
        packed_size = data[:payload_size]  # 取前4字节（这是「画面数据的长度」）
        data = data[payload_size:]         # 缓冲区剩下的部分：待处理的画面数据
        frame_size = struct.unpack("!I", packed_size)[0]  # 解包：把4字节转成数字（画面长度）

        # 过滤异常数据（比如超大数值，是解包错误，直接跳过）
        if frame_size <= 0 or frame_size > MAX_FRAME_SIZE:
            print(f" 跳过异常帧尺寸：{frame_size}（不是正常画面数据）")
            data = b""  # 清空缓冲区，重新接收
            continue

        # ---------------------- 步骤3：接收实际画面数据 ----------------------
        frame_data = b""  # 存放完整的画面数据
        # 循环接收，直到凑够「frame_size」字节（画面数据的总长度）
        while len(frame_data) < frame_size:
            # 只收「缺少的字节数」，避免粘包
            packet = client.recv(frame_size - len(frame_data))
            if not packet:
                break
            frame_data += packet
        # 如果没收到完整的画面数据，清空缓冲区重新来
        if len(frame_data) != frame_size:
            data = b""
            continue

        # ---------------------- 步骤4：解码并显示画面 ----------------------
        try:
            # 把字节数据转成OpenCV能显示的图像格式
            # np.frombuffer：字节转数组；cv2.imdecode：JPEG解码为图像
            frame = cv2.imdecode(np.frombuffer(frame_data, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:  # 解码成功才显示
                cv2.imshow(WINDOW_NAME, frame)
        except:
            # 解码失败不报错，直接跳过（避免程序崩溃）
            continue

        # ---------------------- 步骤5：窗口刷新+退出逻辑 ----------------------
        # waitKey(1)是窗口刷新的关键，没有这行窗口会卡死
        # 检测是否按了「q键」，按q就退出循环
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print(" 你按了q键，准备退出...")
            break

# 程序结束后，清理资源（不管正常退出还是报错，都要执行）
finally:
    client.close()          # 关闭和树莓派的连接
    server.close()          # 关闭服务器端口
    cv2.destroyAllWindows() # 关闭显示窗口
    print("程序已安全退出 ")
    input("按回车键关闭窗口...")  # 避免窗口一闪而过