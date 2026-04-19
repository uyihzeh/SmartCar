import pygame
import sys
import time
import os
from pygame.locals import *

# 检查并安装必要的库
try:
    from adafruit_servokit import ServoKit
    import board
    import busio
except ImportError:
    print("⚠️ 检测到缺少必要的库，正在尝试安装...")
    os.system("pip3 install adafruit-circuitpython-servokit")
    os.system("pip3 install adafruit-blinka")
    from adafruit_servokit import ServoKit
    import board
    import busio

# -------------------------- 1. 机械臂配置（PCA9685舵机驱动） --------------------------
# 舵机通道分配 - 使用MG996R舵机（180°）
BASE_CH = 0         # 底座旋转舵机（最下面）
SHOULDER_CH = 1     # 肩部舵机（第二个舵机）
ELBOW_CH = 2        # 肘部舵机（第三个舵机）
WRIST_ROT_CH = 3    # 腕部旋转舵机（第四个舵机）
WRIST_TILT_CH = 4   # 腕部倾斜舵机（控制夹子方向）- 第五个舵机
CLAW_CH = 5         # 机械夹子舵机（70°=完全打开，145°=完全闭合）


# 舵机名称对应列表
SERVO_NAMES = [
    "底座", "肩部", "肘部", 
    "腕部旋转", "腕部倾斜", "夹子"
]


# 各舵机角度范围定义
ANGLE_LIMITS = {
    BASE_CH: (0, 180),      # 底座旋转范围（左右旋转）
    SHOULDER_CH: (20, 160),  # 肩部运动范围
    ELBOW_CH: (10, 170),     # 第三个舵机（肘部）
    WRIST_ROT_CH: (10, 160), # 第四个舵机（腕部旋转）
    WRIST_TILT_CH: (0, 180),# 腕部倾斜范围，修改上限为180°
    CLAW_CH: (70, 145)       # 夹子开合范围
}


# 各舵机基准位置（90°保持竖直）
HOME_POSITIONS = {
    BASE_CH: 90,             # 底座居中
    SHOULDER_CH: 140,         # 肩部竖直
    ELBOW_CH: 20,            # 肘部竖直
    WRIST_ROT_CH: 30,        # 腕部旋转居中
    WRIST_TILT_CH: 0,       # 腕部水平
    CLAW_CH: 70              # 夹子默认完全打开
}


# 程序退出时的复位位置（单独定义，用于特殊处理夹子）
SHUTDOWN_POSITIONS = {
    BASE_CH: 90,
    SHOULDER_CH: 90,
    ELBOW_CH: 90,
    WRIST_ROT_CH: 90,
    WRIST_TILT_CH: 90,
    CLAW_CH: 90              # 夹子在程序停止时复位到90°
}


# -------------------------- 2. 全局变量 --------------------------
# 当前舵机角度
current_angles = {
    BASE_CH: 90,
    SHOULDER_CH: 90,
    ELBOW_CH: 90,
    WRIST_ROT_CH: 90,
    WRIST_TILT_CH: 90,
    CLAW_CH: 70              # 初始化为70°
}

# 舵机活动状态跟踪（用于电源管理）
active_servos = set()  # 记录当前正在活动的舵机


# -------------------------- 3. 手柄配置与参数 --------------------------
# 控制参数
ROCKER_THRESHOLD = 0.2    # 摇杆灵敏度阈值（避免微小抖动）

# 手柄按键映射（根据实际检测结果修正）
CLAW_OPEN_BUTTON = 6       # 左上方按键：夹子打开
CLAW_CLOSE_BUTTON = 8      # 左下方按键：夹子闭合

# 按键映射修正 - 匹配实际检测结果
Y_BUTTON = 4               # Y键：第三个舵机（肘部）前倾
A_BUTTON = 0               # A键：第三个舵机（肘部）后仰
X_BUTTON = 3               # X键：第五个舵机（腕部倾斜）右转
B_BUTTON = 1               # B键：第五个舵机（腕部倾斜）左转
WRIST_FORWARD_BUTTON = 9   # 原夹子闭合键：第四个舵机（腕部旋转）前倾
WRIST_BACK_BUTTON = 7      # 原夹子打开键：第四个舵机（腕部旋转）后仰


# -------------------------- 4. 机械臂控制函数 --------------------------
def init_servos():
    """初始化舵机驱动板和机械臂舵机（使用I2C1）"""
    try:
        # I2C端口配置 - 使用I2C1（GPIO2=SDA, GPIO3=SCL）
        i2c = busio.I2C(board.SCL, board.SDA)
        
        # 等待I2C连接就绪
        while not i2c.try_lock():
            pass
        
        try:
            # 扫描I2C总线上的设备
            devices = i2c.scan()
            if not devices:
                print("⚠️ 未在I2C总线上发现任何设备")
            else:
                print(f"✅ 在I2C总线上发现设备: {[hex(d) for d in devices]}")
                if 0x40 not in devices:  # PCA9685默认地址
                    print(f"⚠️ 未发现舵机驱动板（预期地址: 0x40）")
        finally:
            i2c.unlock()
        
        kit = ServoKit(channels=16, i2c=i2c)
        print("✅ 使用adafruit_servokit初始化舵机成功")
        return kit
    
    except Exception as e:
        print(f"❌ 舵机初始化失败: {str(e)}")
        print("请检查以下事项：")
        print("1. 确保已正确启用I2C1: sudo raspi-config")
        print("2. 确保舵机驱动板正确连接到I2C1 (GPIO2=SDA, GPIO3=SCL)")
        print("3. 手动安装必要的库:")
        print("   pip3 install adafruit-circuitpython-servokit")
        print("   pip3 install adafruit-blinka")
        sys.exit(1)


def init_arm(kit):
    """初始化机械臂到竖直基准位置（90°）"""
    print("初始化机械臂到竖直基准位置...")
    # 初始化时依次移动每个舵机，避免同时启动过多舵机导致电源过载
    for ch in range(6):
        kit.servo[ch].set_pulse_width_range(500, 2500)  # MG996R舵机脉冲范围
        kit.servo[ch].angle = HOME_POSITIONS[ch]
        current_angles[ch] = HOME_POSITIONS[ch]
        time.sleep(0.5)  # 给每个舵机足够的移动时间
    print("机械臂初始化完成！")


def can_move_servo(servo_ch):
    """检查是否可以移动该舵机，确保同一时间最多5个舵机活动"""
    global active_servos
    
    # 如果该舵机已经在活动状态，允许继续移动
    if servo_ch in active_servos:
        return True
    
    # 如果活动舵机少于5个，允许添加新舵机
    if len(active_servos) < 5:
        active_servos.add(servo_ch)
        return True
    
    # 否则不允许移动
    return False


def move_servo(kit, servo_ch, target_angle, force_move=False):
    """
    控制单个舵机平滑运动到目标角度
    增加了电源保护：同一时刻最多控制5个舵机
    """
    # 检查是否可以移动该舵机
    if not can_move_servo(servo_ch):
        print(f"\n⚠️ 电源保护：暂时无法控制{SERVO_NAMES[servo_ch]}，请稍后再试")
        return False
    
    # 角度限制保护
    min_angle, max_angle = ANGLE_LIMITS[servo_ch]
    target_angle = max(min_angle, min(target_angle, max_angle))
    
    current_angle = current_angles[servo_ch]
    # 强制移动时忽略微小差异检查
    if not force_move and abs(target_angle - current_angle) < 0.2:
        # 如果舵机已静止，从活动列表中移除
        if servo_ch in active_servos:
            active_servos.remove(servo_ch)
        return False
    
    # 使用固定步长
    step = 0.5 if target_angle > current_angle else -0.5
    steps = abs(int((target_angle - current_angle) / step))
    step_interval = 0.02  # 固定步长间隔
    
    # 逐步移动
    joystick = pygame.joystick.Joystick(0)
    moved = False
    
    for _ in range(steps):
        current_angle += step
        if (step > 0 and current_angle >= target_angle) or (step < 0 and current_angle <= target_angle):
            current_angle = target_angle
        
        kit.servo[servo_ch].angle = current_angle
        current_angles[servo_ch] = current_angle
        moved = True
        time.sleep(step_interval)
        
        # 检查是否需要停止（摇杆回中）
        if servo_ch == BASE_CH:
            if abs(joystick.get_axis(2)) < 0.1:
                break
        elif servo_ch == SHOULDER_CH:
            if abs(joystick.get_axis(3)) < 0.1:
                break
    
    # 如果舵机已到达目标位置，从活动列表中移除
    if abs(current_angle - target_angle) < 0.5 and servo_ch in active_servos:
        active_servos.remove(servo_ch)
    
    return moved


def control_arm_movement(kit, joystick):
    """根据手柄输入控制机械臂运动"""
    global active_servos
    
    # 读取摇杆值
    right_stick_x = joystick.get_axis(2)  # 右摇杆X轴
    right_stick_y = joystick.get_axis(3)  # 右摇杆Y轴
    
    # 读取按键状态
    claw_open = joystick.get_button(CLAW_OPEN_BUTTON)
    claw_close = joystick.get_button(CLAW_CLOSE_BUTTON)
    y_press = joystick.get_button(Y_BUTTON)
    a_press = joystick.get_button(A_BUTTON)
    x_press = joystick.get_button(X_BUTTON)
    b_press = joystick.get_button(B_BUTTON)
    wrist_forward = joystick.get_button(WRIST_FORWARD_BUTTON)
    wrist_back = joystick.get_button(WRIST_BACK_BUTTON)
    
    # 1. 底座旋转（第一个舵机）- 右摇杆左右
    if abs(right_stick_x) > 0.1:
        target_angle = current_angles[BASE_CH] - (right_stick_x * 3.0)
        move_servo(kit, BASE_CH, target_angle)
    else:
        if BASE_CH in active_servos:
            active_servos.remove(BASE_CH)
    
    # 2. 肩部舵机（第二个舵机）- 右摇杆前后
    if abs(right_stick_y) > 0.1:
        # 右摇杆向上：肩部后仰（角度增大），右摇杆向下：肩部前倾（角度减小）
        target_angle = current_angles[SHOULDER_CH] + (right_stick_y * 3.0)
        move_servo(kit, SHOULDER_CH, target_angle)
    else:
        if SHOULDER_CH in active_servos:
            active_servos.remove(SHOULDER_CH)
    
    # 3. 肘部舵机（第三个舵机）- Y键和A键
    if y_press:  # Y键：肘部前倾（角度减小）
        target_angle = current_angles[ELBOW_CH] - 5  # 增加步长使动作更明显
        move_servo(kit, ELBOW_CH, target_angle, force_move=True)
        print(f"\n肘部前倾: {target_angle:.1f}°")
    elif a_press:  # A键：肘部后仰（角度增大）
        target_angle = current_angles[ELBOW_CH] + 5
        move_servo(kit, ELBOW_CH, target_angle, force_move=True)
        print(f"\n肘部后仰: {target_angle:.1f}°")
    else:
        if ELBOW_CH in active_servos:
            active_servos.remove(ELBOW_CH)
    
    # 4. 腕部旋转舵机（第四个舵机）- 原夹子控制键
    if wrist_forward:  # 原夹子闭合键：腕部前倾（角度减小）
        target_angle = current_angles[WRIST_ROT_CH] - 2
        move_servo(kit, WRIST_ROT_CH, target_angle, force_move=True)
        print(f"\n腕部前倾: {target_angle:.1f}°")
    elif wrist_back:  # 原夹子打开键：腕部后仰（角度增大）
        target_angle = current_angles[WRIST_ROT_CH] + 2
        move_servo(kit, WRIST_ROT_CH, target_angle, force_move=True)
        print(f"\n腕部后仰: {target_angle:.1f}°")
    else:
        if WRIST_ROT_CH in active_servos:
            active_servos.remove(WRIST_ROT_CH)
    
    # 5. 腕部倾斜舵机（第五个舵机）- X键和B键
    if x_press:  # X键：腕部右转（角度增大）
        # 增加调试信息，确认按键被正确检测
        print(f"\n检测到X键按下，控制第五个舵机（腕部倾斜）右转")
        # 增大步长使动作更明显
        target_angle = current_angles[WRIST_TILT_CH] + 3
        # 确保目标角度在允许范围内
        if target_angle > ANGLE_LIMITS[WRIST_TILT_CH][1]:
            target_angle = ANGLE_LIMITS[WRIST_TILT_CH][1]
            print(f"已达到腕部倾斜最大角度: {target_angle:.1f}°")
        move_servo(kit, WRIST_TILT_CH, target_angle, force_move=True)
        print(f"腕部右转: {target_angle:.1f}°")
    elif b_press:  # B键：腕部左转（角度减小）
        target_angle = current_angles[WRIST_TILT_CH] - 2
        move_servo(kit, WRIST_TILT_CH, target_angle, force_move=True)
        print(f"\n腕部左转: {target_angle:.1f}°")
    else:
        if WRIST_TILT_CH in active_servos:
            active_servos.remove(WRIST_TILT_CH)
    
    # 6. 夹子控制（第六个舵机）- 原速度控制键
    # 调整：步长从4增加到6，速度更快一些
    if claw_open:  # 原加速键：夹子打开
        target_claw = max(current_angles[CLAW_CH] - 6, 70)  # 打开到70°
        move_servo(kit, CLAW_CH, target_claw)
        print(f"\n夹子打开: {target_claw:.1f}°")
    elif claw_close:  # 原减速键：夹子闭合
        target_claw = min(current_angles[CLAW_CH] + 6, 145)
        move_servo(kit, CLAW_CH, target_claw)
        print(f"\n夹子闭合: {target_claw:.1f}°")
    else:
        if CLAW_CH in active_servos:
            active_servos.remove(CLAW_CH)
    
    # 打印当前状态
    print(f"\r底座: {current_angles[BASE_CH]:.1f}° | 肩部: {current_angles[SHOULDER_CH]:.1f}° | 肘部: {current_angles[ELBOW_CH]:.1f}° | 腕部旋转: {current_angles[WRIST_ROT_CH]:.1f}° | 腕部倾斜: {current_angles[WRIST_TILT_CH]:.1f}° | 夹子: {current_angles[CLAW_CH]:.1f}° | 活动舵机: {len(active_servos)}/5", end="", flush=True)


# -------------------------- 5. 手柄控制函数 --------------------------
def init_usb_joystick():
    """初始化USB手柄：无头模式"""
    os.environ["SDL_VIDEODRIVER"] = "dummy"  # 虚拟视频驱动
    
    pygame.init()
    pygame.joystick.init()

    joystick_count = pygame.joystick.get_count()
    if joystick_count == 0:
        print("❌ 未检测到任何USB手柄，请检查连接！")
        pygame.quit()
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    # 打印手柄信息
    print("=" * 60)
    print(f"✅ 成功检测到手柄：{joystick.get_name()}")
    print(f"   🎮 轴数量：{joystick.get_numaxes()}")
    print(f"   🔘 按键数量：{joystick.get_numbuttons()}")
    print("=" * 60)
    print("📢 控制说明（按 Ctrl+C 退出）")
    print("   右摇杆控制：")
    print("     - 左右：控制底座旋转（第一个舵机）")
    print("     - 上下：控制肩部（第二个舵机）后仰/前倾")
    print(f"   Y键（按钮{Y_BUTTON}）：肘部（第三个舵机）前倾")
    print(f"   A键（按钮{A_BUTTON}）：肘部（第三个舵机）后仰")
    print(f"   原夹子闭合键（{WRIST_FORWARD_BUTTON}）：腕部旋转（第四个舵机）前倾")
    print(f"   原夹子打开键（{WRIST_BACK_BUTTON}）：腕部旋转（第四个舵机）后仰")
    print(f"   X键（按钮{X_BUTTON}）：腕部倾斜（第五个舵机）右转")
    print(f"   B键（按钮{B_BUTTON}）：腕部倾斜（第五个舵机）左转")
    print(f"   左上方按键（{CLAW_OPEN_BUTTON}）：夹子打开")
    print(f"   左下方按键（{CLAW_CLOSE_BUTTON}）：夹子闭合")
    print("=" * 60)

    return joystick


def handle_joystick_input(kit, joystick):
    """处理手柄输入并控制机械臂"""
    # 处理pygame事件
    for event in pygame.event.get():
        if event.type == JOYDEVICEREMOVED:
            print("\n❌ 手柄已断开连接！")
            pygame.quit()
            sys.exit(1)
        if event.type == JOYBUTTONDOWN:
            print(f"\n按键 {event.button} 被按下")
    
    # -------------------------- 右摇杆和按键控制机械臂 --------------------------
    control_arm_movement(kit, joystick)


# -------------------------- 6. 主程序 --------------------------
def main():
    print("=" * 80)
    print("🎮 手柄控制机械臂系统（MG996R舵机版）")
    print("=" * 80)
    
    try:
        # 初始化硬件
        servo_kit = init_servos()
        init_arm(servo_kit)
        joystick = init_usb_joystick()
        
        # 主控制循环
        while True:
            # 处理手柄输入并控制设备
            handle_joystick_input(servo_kit, joystick)
            
            time.sleep(0.002)
    
    except KeyboardInterrupt:
        print("\n\n📤 程序退出中...")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {str(e)}")
    finally:
        # 程序结束时复位所有设备
        if 'servo_kit' in locals():
            # 机械臂复位到停止位置（使用SHUTDOWN_POSITIONS，夹子复位到90°）
            print("正在将机械臂复位到停止位置...")
            for ch in range(6):
                servo_kit.servo[ch].angle = SHUTDOWN_POSITIONS[ch]
                time.sleep(0.3)
            print("✅ 机械臂已复位到停止位置")
        
        # 清理手柄资源
        if 'joystick' in locals():
            joystick.quit()
        pygame.joystick.quit()
        pygame.quit()

if __name__ == "__main__":
    main()