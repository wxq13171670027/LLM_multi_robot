import time
from datetime import datetime

# 假设已导入前文定义的所有类（Robot, BedsideRobot等）

def main():
    # 1. 初始化IANI控制器
    iani_controller = IANI_Controller()
    
    # 2. 添加环境障碍物（坐标参考定量化场景）
    obstacles = [(10,9), (15,9), (12,7), (18,7)]
    for x, y in obstacles:
        iani_controller.add_obstacle(x, y)
    print(f"已添加障碍物：{obstacles}")

    # 3. 创建并注册机器人（3组9个）
    # 床头护理机器人（A1-A3）
    bedside_bots = [
        BedsideRobot("A1", 10, 5),
        BedsideRobot("A2", 15, 5),
        BedsideRobot("A3", 20, 5)
    ]
    # 物流机器人（B1-B3）
    logistics_bots = [
        LogisticsRobot("B1", 5, 10),
        LogisticsRobot("B2", 10, 10),
        LogisticsRobot("B3", 15, 10)
    ]
    # 消毒机器人（C1-C3）
    disinfect_bots = [
        DisinfectRobot("C1", 10, 8, (5, 12)),
        DisinfectRobot("C2", 15, 8, (12, 18)),
        DisinfectRobot("C3", 20, 8, (18, 25))
    ]
    
    # 注册到控制器
    for bot in bedside_bots:
        iani_controller.register_robot('bedside', bot)
    for bot in logistics_bots:
        iani_controller.register_robot('logistics', bot)
    for bot in disinfect_bots:
        iani_controller.register_robot('disinfect', bot)
    
    print(f"已注册机器人：床头{A1-A3}，物流{B1-B3}，消毒{C1-C3}")

    # 4. 模拟任务场景（基于定量化场景数据）
    print("\n====== 开始执行任务 ======")
    
    # 场景1：A1执行咽喉试纸采样并请求补给
    print("\n【场景1】A1执行咽喉试纸采样")
    a1 = bedside_bots[0]
    a1.receive_task({
        'type': 'self_operate',
        'content': {'operation': 'throat_swab'},
        'priority': 'P1',
        'target_pos': (10, 5),
        'sender': a1
    })
    time.sleep(2)  # 模拟任务执行时间

    # 场景2：A3突发止血带短缺（P0优先级）
    print("\n【场景2】A3突发止血带短缺")
    a3 = bedside_bots[2]
    a3.supplies['tourniquet'] = 0  # 手动清空库存
    a3.request_supply('tourniquet', 5)  # 发送紧急请求
    time.sleep(3)  # 模拟任务执行时间

    # 场景3：A2完成5次作业后请求样本传送
    print("\n【场景3】A2请求样本传送")
    a2 = bedside_bots[1]
    # 手动累加作业次数至5次
    a2.work_count = 4
    a2.receive_task({
        'type': 'self_operate',
        'content': {'operation': 'blood_draw'},
        'priority': 'P1',
        'target_pos': (15, 5),
        'sender': a2
    })
    time.sleep(3)  # 模拟任务执行时间

    # 5. 输出任务执行结果
    print("\n====== 任务执行结果 ======")
    for bot in logistics_bots + disinfect_bots:
        print(f"\n{bot.robot_id}任务历史：")
        for task in bot.task_history:
            start = task['start_time'].strftime("%H:%M:%S")
            end = task['end_time'].strftime("%H:%M:%S") if 'end_time' in task else "未完成"
            print(f"- 任务类型：{task['task']['type']}，状态：{task['status']}，时间：{start}->{end}")

if __name__ == "__main__":
    main()