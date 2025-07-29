import numpy as np
import networkx as nx
from datetime import datetime, timedelta
import random
from typing import List, Dict, Tuple, Optional, Set, Any
import json

# 任务优先级枚举
class TaskPriority:
    CRITICAL = 3  # 紧急任务，如急救
    HIGH = 2      # 高优先级，如输液、样本采集
    MEDIUM = 1    # 中等优先级，如常规检查
    LOW = 0       # 低优先级，如环境消毒

# 机器人类型枚举
class RobotType:
    T_CELL = "T-Cell Bot"  # 快响应机器人
    B_CELL = "B-Cell Bot"  # 可容错机器人

# 任务类
class Task:
    def __init__(self, task_id: str, description: str, priority: TaskPriority, 
                 location: Tuple[float, float], estimated_duration: float,
                 dependencies: List[str] = None):
        self.task_id = task_id
        self.description = description
        self.priority = priority
        self.location = location
        self.estimated_duration = estimated_duration
        self.dependencies = dependencies if dependencies else []
        self.assigned_robot = None
        self.start_time = None
        self.end_time = None
        self.status = "pending"  # pending, assigned, in_progress, completed, failed
    
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "description": self.description,
            "priority": self.priority,
            "location": self.location,
            "estimated_duration": self.estimated_duration,
            "dependencies": self.dependencies,
            "assigned_robot": self.assigned_robot,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status
        }

# 机器人类
class Robot:
    def __init__(self, robot_id: str, robot_type: RobotType, 
                 position: Tuple[float, float], capabilities: List[str]):
        self.robot_id = robot_id
        self.robot_type = robot_type
        self.position = position
        self.capabilities = capabilities
        self.current_task = None
        self.battery_level = 100.0  # 百分比
        self.status = "idle"  # idle, busy, charging, error
        self.communication_quality = 1.0  # 1.0表示最佳
        self.last_comm_time = datetime.now()
        self.path = []  # 当前规划路径
    
    def update_position(self, new_position: Tuple[float, float]):
        self.position = new_position
    
    def update_battery(self, consumption: float):
        self.battery_level = max(0.0, self.battery_level - consumption)
    
    def to_dict(self):
        return {
            "robot_id": self.robot_id,
            "robot_type": self.robot_type,
            "position": self.position,
            "capabilities": self.capabilities,
            "current_task": self.current_task.task_id if self.current_task else None,
            "battery_level": self.battery_level,
            "status": self.status,
            "communication_quality": self.communication_quality
        }

# 环境类
class HospitalEnv:
    def __init__(self, rooms: Dict[str, Tuple[float, float]], 
                 obstacles: List[Tuple[float, float, float, float]],  # (x, y, width, height)
                 infection_zones: Dict[str, float],  # 区域ID: 感染风险等级
                 human_traffic: Dict[str, List[Tuple[datetime, Tuple[float, float]]]]):  # 人员流动预测
        self.rooms = rooms
        self.obstacles = obstacles
        self.infection_zones = infection_zones
        self.human_traffic = human_traffic
        self.traffic_density = {}  # 实时人流密度
        self.communication_status = {
            "bandwidth": 100.0,  # 百分比
            "packet_loss": 0.0   # 百分比
        }
    
    def update_communication_status(self, bandwidth: float, packet_loss: float):
        self.communication_status["bandwidth"] = max(0.0, min(100.0, bandwidth))
        self.communication_status["packet_loss"] = max(0.0, min(100.0, packet_loss))
    
    def update_human_traffic(self, time: datetime):
        # 更新指定时间的人流密度
        for zone, traffic in self.human_traffic.items():
            count = sum(1 for t, _ in traffic if abs((t - time).total_seconds()) < 60)
            self.traffic_density[zone] = count

# 大语言模型接口类（模拟）
class LLMInterface:
    def __init__(self):
        # 模拟LLM功能
        pass
    
    def parse_task_description(self, natural_language: str) -> Dict:
        # 解析自然语言任务描述
        # 这里是简化实现，实际中会使用真实的LLM
        if "消毒" in natural_language or "清洁" in natural_language:
            return {
                "task_type": "disinfection",
                "priority": TaskPriority.LOW if "常规" in natural_language else TaskPriority.MEDIUM,
                "location": "unknown",
                "duration": 5.0,
                "dependencies": []
            }
        elif "输液" in natural_language or "样本" in natural_language:
            return {
                "task_type": "patient_care",
                "priority": TaskPriority.HIGH,
                "location": "unknown",
                "duration": 3.0,
                "dependencies": []
            }
        elif "急救" in natural_language or "紧急" in natural_language:
            return {
                "task_type": "emergency",
                "priority": TaskPriority.CRITICAL,
                "location": "unknown",
                "duration": 2.0,
                "dependencies": []
            }
        else:
            return {
                "task_type": "general",
                "priority": TaskPriority.MEDIUM,
                "location": "unknown",
                "duration": 4.0,
                "dependencies": []
            }
    
    def generate_task_dag(self, tasks: List[Task]) -> nx.DiGraph:
        # 生成任务依赖图
        dag = nx.DiGraph()
        for task in tasks:
            dag.add_node(task.task_id, task=task)
            for dep in task.dependencies:
                dag.add_edge(dep, task.task_id)
        return dag
    
    def predict_robot_status(self, robot: Robot, neighbors: List[Robot], time: datetime) -> Dict:
        # 预测失联机器人状态
        # 简化实现：基于邻居机器人位置和时间推测
        last_seen = (time - robot.last_comm_time).total_seconds()
        speed = 0.5  # 假设速度为0.5单位/秒
        max_distance = last_seen * speed
        
        # 从邻居位置推测可能位置
        possible_positions = []
        for neighbor in neighbors:
            dx = robot.position[0] - neighbor.position[0]
            dy = robot.position[1] - neighbor.position[1]
            dist = (dx**2 + dy**2)**0.5
            
            if dist <= max_distance:
                possible_positions.append(neighbor.position)
        
        if possible_positions:
            predicted_pos = np.mean(possible_positions, axis=0)
        else:
            predicted_pos = robot.position  # 如果没有邻居信息，保持最后已知位置
        
        return {
            "position": tuple(predicted_pos),
            "status": "moving" if last_seen < 30 else "possibly_stuck",
            "estimated_battery": max(0, robot.battery_level - last_seen * 0.01)
        }
#_all_=["TaskPriority","RobotType","Task","Robot","HospitalEnv","LLMInterface"]