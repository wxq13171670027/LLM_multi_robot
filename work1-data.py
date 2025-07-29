from IANIvic import TaskPriority,RobotType,Task,Robot,HospitalEnv,LMInterface
class DataTransmissionModule:
    def __init__(self, llm: LLMInterface):
        self.llm = llm
        self.t_bot_channel = []  # T类机器人通信通道
        self.b_bot_channel = []  # B类机器人通信通道
        self.bot_status_cache = {}  # 缓存机器人状态
        self.communication_strategy = {
            "t_bot_frequency": 10.0,  # Hz
            "b_bot_frequency": 2.0    # Hz
        }
    
    def adjust_communication_strategy(self, env: HospitalEnv):
        # 根据通信状态调整策略
        bandwidth = env.communication_status["bandwidth"]
        packet_loss = env.communication_status["packet_loss"]
        
        # 带宽不足或丢包率高时，降低B类通道频率
        if bandwidth < 50 or packet_loss > 20:
            self.communication_strategy["b_bot_frequency"] = max(0.5, self.communication_strategy["b_bot_frequency"] * 0.5)
        else:
            # 恢复正常频率
            self.communication_strategy["b_bot_frequency"] = min(2.0, self.communication_strategy["b_bot_frequency"] * 1.1)
    
    def t_bot_transmit(self, robot: Robot, task_status: Dict, timestamp: datetime) -> Dict:
        # T类机器人通信：简化语义生成
        # 使用Influence-Based Prompt Compression机制
        compressed_data = {
            "robot_id": robot.robot_id,
            "timestamp": timestamp,
            "position": robot.position,
            "battery": round(robot.battery_level, 1),
            "task_id": task_status.get("task_id"),
            "task_progress": task_status.get("progress", 0),
            "errors": task_status.get("errors", []),
            "priority": task_status.get("priority", TaskPriority.HIGH)
        }
        
        # 加入到T类通道
        self.t_bot_channel.append(compressed_data)
        self.bot_status_cache[robot.robot_id] = {
            "data": compressed_data,
            "timestamp": timestamp
        }
        
        return compressed_data
    
    def b_bot_transmit(self, robot: Robot, status_summary: Dict, timestamp: datetime) -> Dict:
        # B类机器人通信：EMOS式摘要模板
        summary_data = {
            "robot_id": robot.robot_id,
            "timestamp": timestamp,
            "position": robot.position,
            "battery": round(robot.battery_level, 1),
            "status": robot.status,
            "completed_tasks": status_summary.get("completed_tasks", []),
            "pending_tasks": status_summary.get("pending_tasks", []),
            "environment_sensors": status_summary.get("sensors", {})
        }
        
        # 加入到B类通道
        self.b_bot_channel.append(summary_data)
        self.bot_status_cache[robot.robot_id] = {
            "data": summary_data,
            "timestamp": timestamp
        }
        
        return summary_data
    
    def check_robot_connection(self, robot: Robot, current_time: datetime) -> bool:
        # 检查机器人连接状态
        time_since_last_comm = (current_time - robot.last_comm_time).total_seconds()
        
        # 根据机器人类型定义超时阈值
        if robot.robot_type == RobotType.T_CELL:
            timeout = 5.0  # T类机器人超时时间更短
        else:
            timeout = 15.0  # B类机器人超时时间较长
            
        return time_since_last_comm < timeout
    
    def handle_disconnected_robot(self, robot: Robot, all_robots: List[Robot], current_time: datetime) -> Dict:
        # 处理失联机器人：预测性语义补偿
        # 找到邻近机器人
        neighbors = []
        for r in all_robots:
            if r.robot_id != robot.robot_id and self.check_robot_connection(r, current_time):
                dx = robot.position[0] - r.position[0]
                dy = robot.position[1] - r.position[1]
                distance = (dx**2 + dy**2)**0.5
                if distance < 10.0:  # 距离小于10单位视为邻近
                    neighbors.append(r)
        
        # 使用LLM预测状态
        predicted_status = self.llm.predict_robot_status(robot, neighbors, current_time)
        
        # 生成替代语义包
        replacement_data = {
            "robot_id": robot.robot_id,
            "timestamp": current_time,
            "predicted": True,
            "predicted_position": predicted_status["position"],
            "predicted_status": predicted_status["status"],
            "predicted_battery": predicted_status["estimated_battery"],
            "last_known_position": robot.position,
            "last_communication": robot.last_comm_time
        }
        
        # 更新缓存
        self.bot_status_cache[robot.robot_id] = {
            "data": replacement_data,
            "timestamp": current_time,
            "predicted": True
        }
        
        return replacement_data
    
    def get_robot_status(self, robot_id: str, current_time: datetime) -> Optional[Dict]:
        # 获取机器人状态，处理可能的失联情况
        if robot_id in self.bot_status_cache:
            status = self.bot_status_cache[robot_id]
            # 检查数据是否过期
            if (current_time - status["timestamp"]).total_seconds() < 30:
                return status["data"]
        return None