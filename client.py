# -*- coding: utf-8 -*-
# 功能：采集摄像头画面→识别草莓（画绿色框）→压缩传输到电脑（跨平台兼容版）

# 导入必要的库
import cv2          # OpenCV库：采集摄像头、识别草莓、压缩图片
import socket       # 网络库：和电脑建立连接、发送数据
import struct       # 数据打包库：给画面长度打包，方便电脑解析
import numpy as np  # 数值计算库：辅助草莓识别（转灰度图、匹配计算）
import time         # 时间库：加小延迟，避免发送数据太快导致卡顿

# -------------------------------------------
COMPUTER_IP = "192.168.1.7"  # 使用本地电脑IPv4地址（电脑cmd输ipconfig找）
PORT = 9999                  # 端口号：和电脑端保持一致就行
# -------------------------------------------------------------

# 1. 初始化USB摄像头（打开摄像头，设置基础参数）
cap = cv2.VideoCapture(0)    # 0：默认USB摄像头（插多个的话改1/2）
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)   # 画面宽度：320像素（小尺寸传输快不卡）
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # 画面高度：240像素
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)       # 关闭自动对焦（避免画面抖动）
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)      # 缓冲区大小：1帧（减少数据粘包）

# 2. 加载草莓模板图（用一张草莓图当识别样本）
# 路径说明：/home/pi/Desktop/strawberry.jpg → 树莓派桌面的strawberry.jpg文件
# 0：转为灰度图（黑白图识别更快并能减少计算量）
template = cv2.imread("/home/pi/Desktop/strawberry.jpg", 0)
if template is None:
    # 模板图没找到：只传输画面，不识别草莓
    print("草莓模板图没找到，仅传输摄像头画面（请把strawberry.jpg放桌面）")
    t_h, t_w = 0, 0  # 模板图宽高设为0，跳过识别
else:
    # 模板图加载成功：获取图的宽高（后续画框用）
    t_h, t_w = template.shape[:2]
    print("草莓模板图加载成功，开启识别功能")

# 3. 和电脑建立网络连接（主动连接电脑的端口）
# AF_INET：TCP/IP协议；SOCK_STREAM：TCP可靠传输，数据不丢包
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 关键设置：禁用TCP粘包（避免数据粘在一起，电脑解析出错）
client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
client.connect((COMPUTER_IP, PORT))  # 连接电脑的IP+端口
print(f"已成功连接电脑：{COMPUTER_IP}:{PORT}")

# 核心循环：持续采集→识别→传输（直到按Ctrl+C退出）
try:
    while True:
        # ---------------------- 步骤1：采集摄像头画面 ----------------------
        # ret：采集是否成功（True/False）；frame：采集到的彩色画面
        ret, frame = cap.read()
        if not ret:  # 采集失败（比如摄像头没插好）：等0.01秒再试
            time.sleep(0.01)
            continue

        # ---------------------- 步骤2：草莓识别（模板匹配） ----------------------
        if template is not None:  # 只有模板图加载成功才执行识别
            # 步骤2.1：彩色画面转灰度图（和模板图格式一致，才能匹配）
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 步骤2.2：模板匹配（找画面中和模板图相似的区域）
            # TM_CCOEFF_NORMED：归一化相关系数匹配（识别准确率高、速度快）
            result = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
            
            # 步骤2.3：筛选匹配结果（只保留匹配度≥70%的区域）
            # 0.7：匹配度阈值（值越小识别越宽松，可改0.6/0.8）
            match_mask = (result >= 0.7).astype(np.uint8)
            # 找到所有匹配区域的坐标
            locations = cv2.findNonZero(match_mask)

            # 步骤2.4：给识别到的草莓画绿色框
            if locations is not None:  # 找到匹配区域才画框
                for loc in locations:
                    x, y = loc[0][0], loc[0][1]  # 匹配区域的左上角坐标
                    # 画矩形框：(x,y)=左上角，(x+t_w,y+t_h)=右下角，绿色(0,255,0)，线宽2
                    cv2.rectangle(frame, (x, y), (x+t_w, y+t_h), (0,255,0), 2)
                    # 框上方写「草莓」文字：字体大小0.5，绿色，线宽1
                    cv2.putText(frame, "草莓", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)

        # ---------------------- 步骤3：压缩画面并传输到电脑 ----------------------
        # 步骤3.1：JPEG压缩（把画面变小，传输更快）
        # [cv2.IMWRITE_JPEG_QUALITY, 50]：压缩质量50（0-100，值越小文件越小、画质稍差）
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, 50]
        _, jpeg_frame = cv2.imencode('.jpg', frame, encode_param)  # 压缩为JPEG格式
        frame_data = jpeg_frame.tobytes()  # 转为字节数据（网络传输只能传字节）
        frame_size = len(frame_data)       # 获取字节数据的长度（告诉电脑要收多少）

        # 步骤3.2：发送数据到电脑（核心：跨平台格式!I，避免解析错误）
        try:
            # 第一步：发送4字节的「数据长度」（!I：网络字节序，Windows/Linux都兼容）
            client.sendall(struct.pack("!I", frame_size))
            # 第二步：发送压缩后的画面数据
            client.sendall(frame_data)
            time.sleep(0.05)  # 加0.05秒延迟（避免发送太快，电脑处理不过来）
        except:
            # 发送失败（比如电脑断开）：退出循环
            print("数据发送失败，电脑可能已断开，程序退出")
            break

# 手动退出逻辑（小白理解：按Ctrl+C会触发这个代码）
except KeyboardInterrupt:
    print("\n 你按了Ctrl+C，准备退出...")

# 程序结束后，清理资源（小白理解：不管正常退出还是报错，都要执行）
finally:
    cap.release()    # 关闭摄像头（避免下次用不了）
    client.close()   # 关闭网络连接
    print(" 程序已安全退出")