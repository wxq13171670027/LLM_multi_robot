from IANIvic import TaskPriority,RobotType,Task,Robot,HospitalEnv,LMInterface
def run_simulation():
    # 创建医院环境
    rooms = {
        "nurse_station": (10, 10),
        "room_1": (10, 30),
        "room_2": (30, 30),
        "room_3": (50, 30),
        "room_4": (70, 30),
        "room_5": (90, 30),
        "supply_room": (50, 10)
    }
    
    obstacles = [
        # 墙壁
        (0, 20, 100, 5),   # 走廊上墙壁
        (0, 35, 100, 5),   # 走廊下墙壁
        # 医疗设备
        (25, 25, 5, 5),
        (65, 25, 5, 5),
        (45, 15, 5, 5),
        (45, 40, 5, 5)
    ]
    
    # 感染风险等级：0-10，越高风险越大
    infection_zones = {
        "room_1": 8.0,
        "room_2": 5.0,
        "room_3": 6.0,
        "room_4": 3.0,
        "room_5": 2.0,
        "nurse_station": 1.0,
        "supply_room": 1.0
    }
    
    # 人员流动预测（简化）
    human_traffic = {
        "corridor": []  # 实际应用中会有预测数据
    }
    
    # 创建环境
    env = HospitalEnv(rooms, obstacles, infection_zones, human_traffic)
    # 设置初始通信状态
    env.update_communication_status(bandwidth=90.0, packet_loss=5.0)
    
    # 创建IANI框架
    iani_system = IANIFramework(env)
    
    # 添加机器人
    iani_system.add_robot(Robot(
        robot_id="T1",
        robot_type=RobotType.T_CELL,
        position=rooms["nurse_station"],
        capabilities=["输液", "样本采集", "急救"]
    ))
    
    iani_system.add_robot(Robot(
        robot_id="T2",
        robot_type=RobotType.T_CELL,
        position=rooms["nurse_station"],
        capabilities=["输液", "样本采集", "急救"]
    ))
    
    iani_system.add_robot(Robot(
        robot_id="B1",
        robot_type=RobotType.B_CELL,
        position=rooms["nurse_station"],
        capabilities=["消毒", "清洁", "物资运输"]
    ))
    
    iani_system.add_robot(Robot(
        robot_id="B2",
        robot_type=RobotType.B_CELL,
        position=rooms["nurse_station"],
        capabilities=["消毒", "清洁", "物资运输"]
    ))
    
    iani_system.add_robot(Robot(
        robot_id="B3",
        robot_type=RobotType.B_CELL,
        position=rooms["nurse_station"],
        capabilities=["消毒", "清洁", "物资运输"]
    ))
    
    # 打印初始状态
    print("=== 初始系统状态 ===")
    status = iani_system.get_system_status()
    print(f"时间: {status['current_time']}")
    print(f"机器人数量: {status['robot_count']}")
    print(f"任务数量: {status['task_count']}")
    print()
    
    # 医护人员发出第一个指令
    print("=== 医护人员指令 1 ===")
    command = "请给隔离病房3的患者进行输液"
    context = {"location": "room_3"}
    result = iani_system.process_human_command(command, context)
    print(f"指令: {command}")
    print(f"处理结果: {result}")
    print()
    
    # 运行系统一步
    print("=== 系统运行一步 ===")
    step_result = iani_system.step()
    print(f"时间: {step_result['timestamp']}")
    print(f"调度结果: {[r['task_id'] for r in step_result['scheduling_results'] if r['assigned']]}")
    print(f"T1状态: {next(r for r in step_result['robot_statuses'] if r['robot_id'] == 'T1')['status']}")
    print()
    
    # 医护人员发出第二个指令
    print("=== 医护人员指令 2 ===")
    command = "请对所有高风险区域进行消毒"
    context = {"location": "room_1, room_2, room_3"}
    result = iani_system.process_human_command(command, context)
    print(f"指令: {command}")
    print(f"处理结果: {result}")
    print()
    
    # 运行系统几步
    print("=== 系统运行几步 ===")
    for i in range(3):
        step_result = iani_system.step()
        print(f"第 {i+1} 步 - 时间: {step_result['timestamp']}")
        print(f"B1状态: {next(r for r in step_result['robot_statuses'] if r['robot_id'] == 'B1')['status']}")
        print(f"B2状态: {next(r for r in step_result['robot_statuses'] if r['robot_id'] == 'B2')['status']}")
    print()
    
    # 模拟通信质量下降
    print("=== 模拟通信质量下降 ===")
    env.update_communication_status(bandwidth=40.0, packet_loss=30.0)
    print(f"新通信状态: 带宽={env.communication_status['bandwidth']}%, 丢包率={env.communication_status['packet_loss']}%")
    print()
    
    # 医护人员发出紧急指令
    print("=== 医护人员紧急指令 ===")
    command = "隔离病房1需要紧急抢救，患者情况恶化"
    context = {"location": "room_1"}
    result = iani_system.process_human_command(command, context)
    print(f"指令: {command}")
    print(f"处理结果: {result}")
    print()
    
    # 运行系统几步
    print("=== 系统处理紧急情况 ===")
    for i in range(5):
        # 模拟医护人员位置
        human_positions = {
            "doctor_1": (10, 32),  # 医生在病房1附近
            "nurse_1": (10, 10)    # 护士在护士站
        }
        
        step_result = iani_system.step(human_positions)
        print(f"第 {i+1} 步 - 时间: {step_result['timestamp']}")
        print(f"T2状态: {next(r for r in step_result['robot_statuses'] if r['robot_id'] == 'T2')['status']}")
        print(f"通信策略调整: T类频率={iani_system.data_module.communication_strategy['t_bot_frequency']}Hz, B类频率={iani_system.data_module.communication_strategy['b_bot_frequency']}Hz")
    print()
    
    # 模拟B2机器人通信中断
    print("=== 模拟B2机器人通信中断 ===")
    b2 = next(r for r in iani_system.robots if r.robot_id == 'B2')
    b2.last_comm_time = datetime.now() - timedelta(seconds=40)  # 40秒前最后通信
    print()
    
    # 再运行几步
    print("=== 处理通信中断 ===")
    for i in range(2):
        step_result = iani_system.step()
        print(f"第 {i+1} 步 - 时间: {step_result['timestamp']}")
        print(f"B2状态缓存: {iani_system.data_module.bot_status_cache.get('B2', {}).get('data', '未知')}")
    print()
    
    # 最终状态
    print("=== 最终系统状态 ===")
    final_status = iani_system.get_system_status()
    print(f"时间: {final_status['current_time']}")
    print(f"已完成任务: {final_status['completed_tasks']}")
    print(f"待处理任务: {final_status['pending_tasks']}")
    print("各机器人状态:")
    for robot in final_status['robot_statuses']:
        print(f"  {robot['robot_id']}: {robot['status']}, 电池: {robot['battery_level']}%")

# 运行模拟
if __name__ == "__main__":
    run_simulation()