# 导入I2C通信库，用于和电机驱动板对话
import smbus
# 导入时间库，用于控制动作持续的时间
import time
# 导入结构体库，用于解析编码器的脉冲数据
import struct

# ================= 配置区域开始 =================

# 设置树莓派的I2C总线号，树莓派5通常用的是1号总线
I2C_BUS = 1                  

# 设置电机驱动板的I2C地址，这个地址是板子出厂默认的0x34
MOTOR_ADDR = 0x34            

# 设置演示时的电机速度 (范围建议 10-40，房间里建议慢一点，安全)
DEMO_SPEED = 15  

# 设置动作持续时间 (单位：秒，专为小空间定制)
TIME_STRAIGHT = 2.0           # 前进/后退持续时间 (2秒)
TIME_TURN = 1.0                # 原地转弯持续时间 (1秒，大概转90度左右)

# ================= 配置区域结束 =================

# ================= 驱动板寄存器地址定义 (不用改，看板子手册就行) =================

# 读取电池电压的寄存器地址
ADC_BAT_ADDR = 0x00
# 设置电机类型的寄存器地址
MOTOR_TYPE_ADDR = 0x14
# 设置编码器极性的寄存器地址 (如果电机失控，改这个)
MOTOR_ENCODER_POLARITY_ADDR = 0x15
# 固定转速控制的寄存器地址 (我们用这个来让电机转)
MOTOR_FIXED_SPEED_ADDR = 0x33
# 读取编码器总脉冲数的寄存器地址
MOTOR_ENCODER_TOTAL_ADDR = 0x3C

# ================= 电机类型定义 =================

# 定义N20编码电机的类型值 (如果你是TT电机，改成1)
MOTOR_TYPE_N20 = 2
# 把我们用的电机类型赋值给变量
MotorType = MOTOR_TYPE_N20
# 设置编码器极性，默认0，如果发现电机乱转就改成1
MotorEncoderPolarity = 0

# ================= 初始化I2C总线 =================

# 创建一个I2C总线对象，后面我们就用这个bus来和驱动板通信
bus = smbus.SMBus(I2C_BUS)

# ================= 核心功能函数定义 =================

def Motor_Init():
    """
    电机初始化函数
    作用：告诉驱动板我们用的是什么电机，必须在最开始运行一次
    """
    # 在终端打印提示信息
    print("正在初始化电机驱动板...")
    # 通过I2C向驱动板的电机类型寄存器写入我们的电机类型
    bus.write_byte_data(MOTOR_ADDR, MOTOR_TYPE_ADDR, MotorType)
    # 延时0.5秒，等待驱动板处理完这个设置
    time.sleep(0.5)
    # 通过I2C向驱动板的编码器极性寄存器写入数值
    bus.write_byte_data(MOTOR_ADDR, MOTOR_ENCODER_POLARITY_ADDR, MotorEncoderPolarity)
    # 再延时0.5秒
    time.sleep(0.5)
    # 打印初始化完成的提示
    print("电机初始化完成！准备开始演示...")

def stop_car():
    """
    停车函数
    作用：让所有电机立即停止转动
    """
    # 向速度控制寄存器写入4个0，代表4个电机速度都为0
    bus.write_i2c_block_data(MOTOR_ADDR, MOTOR_FIXED_SPEED_ADDR, [0, 0, 0, 0])
    # 延时0.2秒，确保电机完全停下来了再执行下一个动作
    time.sleep(0.2)

def move_forward():
    """
    前进函数
    作用：控制小车向前走
    """
    # 在终端打印当前在做什么动作
    print(f"-> 正在前进 {TIME_STRAIGHT} 秒...")
    # 定义4个电机的速度，全部为正数代表正转
    # 列表顺序：[电机1速度, 电机2速度, 电机3速度, 电机4速度]
    # 如果你发现是在后退，把这里的正数全部改成负数
    speeds = [DEMO_SPEED, DEMO_SPEED, DEMO_SPEED, DEMO_SPEED]
    # 通过I2C把速度列表发送给驱动板
    bus.write_i2c_block_data(MOTOR_ADDR, MOTOR_FIXED_SPEED_ADDR, speeds)
    # 延时指定的时间，让电机保持转动
    time.sleep(TIME_STRAIGHT)
    # 时间到了，调用停车函数让电机停下
    stop_car()

def move_backward():
    """
    后退函数
    作用：控制小车向后走
    """
    print(f"-> 正在后退 {TIME_STRAIGHT} 秒...")
    # 定义4个电机的速度，全部为负数代表反转
    speeds = [-DEMO_SPEED, -DEMO_SPEED, -DEMO_SPEED, -DEMO_SPEED]
    # 发送速度指令
    bus.write_i2c_block_data(MOTOR_ADDR, MOTOR_FIXED_SPEED_ADDR, speeds)
    # 保持转动
    time.sleep(TIME_STRAIGHT)
    # 停车
    stop_car()

def turn_left():
    """
    原地左转函数
    作用：控制小车原地向左转 (左轮倒转，右轮正转)
    """
    print(f"-> 正在原地左转 {TIME_TURN} 秒...")
    # 假设 M1, M2 是左边两个电机，M3, M4 是右边两个电机
    # 左边速度设为负，右边速度设为正，实现原地打转
    speeds = [-DEMO_SPEED, -DEMO_SPEED, DEMO_SPEED, DEMO_SPEED]
    # 发送速度指令
    bus.write_i2c_block_data(MOTOR_ADDR, MOTOR_FIXED_SPEED_ADDR, speeds)
    # 保持转动
    time.sleep(TIME_TURN)
    # 停车
    stop_car()

def turn_right():
    """
    原地右转函数
    作用：控制小车原地向右转 (右轮倒转，左轮正转)
    """
    print(f"-> 正在原地右转 {TIME_TURN} 秒...")
    # 右边速度设为负，左边速度设为正
    speeds = [DEMO_SPEED, DEMO_SPEED, -DEMO_SPEED, -DEMO_SPEED]
    # 发送速度指令
    bus.write_i2c_block_data(MOTOR_ADDR, MOTOR_FIXED_SPEED_ADDR, speeds)
    # 保持转动
    time.sleep(TIME_TURN)
    # 停车
    stop_car()

# ================= 主程序入口 =================

def main():
    """
    主函数
    程序从这里开始按顺序执行
    """
    try:
        # 第一步：先运行电机初始化
        Motor_Init()
        # 打印一个分隔符，让终端输出好看一点
        print("\n========== 小空间演示开始 ==========")
        # 稍微等1秒，让你准备好手机拍视频
        time.sleep(1)

        # 第二步：按顺序执行动作 (你可以随意增减这里的顺序)
        
        # 动作1：前进
        print("\n[第 1 步]")
        move_forward()
        
        # 动作2：后退
        print("\n[第 2 步]")
        move_backward()

        # 动作3：左转
        print("\n[第 3 步]")
        turn_left()
        
        # 动作4：前进
        print("\n[第 4 步]")
        move_forward()

        # 动作5：右转 (转两次，相当于掉头)
        print("\n[第 5 步]")
        turn_right()
        turn_right()
        
        # 动作6：前进
        print("\n[第 6 步]")
        move_forward()
        
        # 动作7：右转回正
        print("\n[第 7 步]")
        turn_right()
        
        # 动作8：后退
        print("\n[第 8 步]")
        move_backward()

        # 所有动作执行完毕
        print("\n========== 演示结束！小车已自动停止 ==========")

    except KeyboardInterrupt:
        # 如果你在运行过程中按了 Ctrl+C，会执行这里
        print("\n检测到你手动停止了程序！")
        # 确保电机停下
        stop_car()
    except Exception as e:
        # 如果程序出错了，会执行这里
        print(f"\n程序出错了，错误信息：{e}")
        # 确保电机停下
        stop_car()

# 这行代码的作用是：只有当你直接运行这个文件时，才会执行main()函数
if __name__ == "__main__":
    main()