import math
from collections import defaultdict
from datetime import datetime

class AgentVerseScheduler:
    """基于AgentVerse的动态专家招募调度器，整合所有核心模块"""
    def __init__(self, controller):
        self.controller = controller  # 关联IANI控制器
        self.robot_expertise = {  # 机器人能力矩阵
            'bedside': defaultdict(dict),
            'logistics': defaultdict(dict),
            'disinfect': defaultdict(dict)
        }
        self.task_performance = defaultdict(list)  # 任务历史表现
        self.init_robot_expertise()  # 初始化能力矩阵

    def init_robot_expertise(self):
        """初始化机器人能力矩阵（多维评分：0-10）"""
        # 物流机器人初始化
        for bot in self.controller.robots['logistics']:
            self.robot_expertise['logistics'][bot.robot_id] = {
                'supply_cotton_swab': 6.0,
                'supply_tourniquet': 5.5,
                'supply_sample': 7.0,
                'env_adaptability': 6.5,  # 环境适应力
                'time_sensitivity': 7.5   # 时间敏感任务匹配度
            }
        # 消毒机器人初始化
        for bot in self.controller.robots['disinfect']:
            self.robot_expertise['disinfect'][bot.robot_id] = {
                'disinfect_operation': 7.0,
                'disinfect_robot': 6.8,
                'env_adaptability': 7.2,
                'coverage_stability': 8.0  # 消毒覆盖率稳定性
            }

    def extract_task_features(self, task):
        """任务特征提取与量化（整合时间敏感度和环境复杂度）"""
        priority_weights = {'P0':1.0, 'P1':0.7, 'P2':0.3}
        obstacle_density = self.calculate_obstacle_density(task['target_pos'])
        
        return {
            'priority': task['priority'],
            'priority_weight': priority_weights[task['priority']],
            'location': task['target_pos'],
            'task_subtype': task['content'].get('item', task['content'].get('area')),
            'time_sensitive': task['type'] == 'supply' and 'sample' in task['content'].get('item', ''),
            'obstacle_density': obstacle_density
        }

    def calculate_obstacle_density(self, target_pos, radius=2.0):
        """计算目标位置周围障碍物密度（半径2米内）"""
        tx, ty = target_pos
        obstacles_in_range = 0
        for (x, y) in self.controller.map_obstacles:
            if math.hypot(x - tx, y - ty) <= radius:
                obstacles_in_range += 1
        # 归一化到0-1（假设每平方米最多1个障碍物）
        return min(1.0, obstacles_in_range / (math.pi * radius**2))

    def recruit_experts(self, task):
        """动态招募最佳机器人（整合负载均衡和任务依赖）"""
        task_features = self.extract_task_features(task)
        candidates = self._get_candidates(task)  # 获取候选机器人
        
        best_match = -1
        best_robot = None
        
        for bot in candidates:
            # 负载检查：跳过高负载机器人
            if bot.is_busy and self.calculate_load_factor(bot) > 0.8:
                continue
            
            # 计算多维匹配得分
            distance = math.hypot(bot.x - task['target_pos'][0], bot.y - task['target_pos'][1])
            bot_type = self._get_robot_type(bot.robot_id)
            bot_expertise = self.robot_expertise[bot_type][bot.robot_id]
            
            # 专业度得分
            expertise_score = self._calculate_expertise_score(bot.robot_id, task_features)
            # 距离得分（归一化）
            distance_score = max(0, 10 - distance)
            # 环境适应力得分
            env_score = bot_expertise.get('env_adaptability', 5) * task_features['obstacle_density']
            # 时间敏感度得分
            time_score = bot_expertise.get('time_sensitivity', 5) * task_features['priority_weight']
            
            # 综合得分（加权求和）
            total_score = (
                0.4 * expertise_score +
                0.2 * distance_score +
                0.2 * env_score +
                0.2 * time_score
            )
            
            if total_score > best_match:
                best_match = total_score
                best_robot = bot
        
        # 记录招募结果
        if best_robot:
            self.task_performance[best_robot.robot_id].append({
                'task_type': task['type'],
                'score': best_match,
                'time': datetime.now()
            })
        return best_robot

    def calculate_load_factor(self, bot):
        """计算机器人当前负载系数（0-1）"""
        completed_tasks = len(bot.task_history)
        pending_tasks = sum(1 for t in self.controller.task_queue 
                          if t[1].get('target_robot') == bot.robot_id)
        return min(1.0, (completed_tasks + pending_tasks) / 10)  # 最大承载10个任务

    def update_expertise_after_completion(self, robot_id, task, success=True, delay=0):
        """任务完成后更新能力矩阵（反馈学习）"""
        robot_type = self._get_robot_type(robot_id)
        task_type = f"{task['type']}_{task['content'].get('item','')}"
        current_score = self.robot_expertise[robot_type][robot_id].get(task_type, 5.0)
        
        # 基于执行结果调整得分
        score_delta = 0.3 if success else -0.5
        score_delta -= min(0.2, delay / 60)  # 延迟惩罚
        new_score = max(0, min(10, current_score + score_delta))
        
        self.robot_expertise[robot_type][robot_id][task_type] = new_score

    # 内部辅助方法
    def _get_candidates(self, task):
        """根据任务类型筛选候选机器人"""
        if task['type'] == 'supply':
            return self.controller.robots['logistics']
        elif task['type'] == 'disinfect':
            return self.controller.robots['disinfect']
        return []

    def _get_robot_type(self, robot_id):
        """根据ID判断机器人类型（A=床头, B=物流, C=消毒）"""
        type_map = {'A': 'bedside', 'B': 'logistics', 'C': 'disinfect'}
        return type_map.get(robot_id[0], 'unknown')

    def _calculate_expertise_score(self, robot_id, task_features):
        """计算专业度匹配得分"""
        robot_type = self._get_robot_type(robot_id)
        task_key = f"{task_features['type']}_{task_features['task_subtype']}"
        expertise = self.robot_expertise[robot_type].get(robot_id, {})
        
        # 历史表现加权
        recent_tasks = [t for t in self.task_performance[robot_id] 
                       if t['task_type'] == task_features['type']][-3:]
        if recent_tasks:
            return sum(t['score'] for t in recent_tasks) / len(recent_tasks)
        return expertise.get(task_key, 5.0)  # 无历史则返回基础分


# 与IANI框架集成（包含任务拆分功能）
class IANI_Controller:
    def __init__(self):
        self.robots = {'bedside': [], 'logistics': [], 'disinfect': []}
        self.task_queue = []
        self.map_obstacles = set()
        self.agent_verse = AgentVerseScheduler(self)  # 集成调度器

    def dispatch_task(self, task):
        """任务调度主入口（支持复杂任务拆分）"""
        # 复杂任务拆分（如样本运输=取样本+送检验）
        if self._is_complex_task(task):
            subtasks = self.split_complex_task(task)
            for subtask in subtasks:
                target_robot = self.agent_verse.recruit_experts(subtask)
                if target_robot:
                    subtask['target_robot'] = target_robot.robot_id
                    target_robot.receive_task(subtask)
        else:
            target_robot = self.agent_verse.recruit_experts(task)
            if target_robot:
                task['target_robot'] = target_robot.robot_id
                target_robot.receive_task(task)

    def _is_complex_task(self, task):
        """判断是否为复杂任务"""
        return (task['type'] == 'supply' and 
                'sample' in task['content'].get('item', '') and 
                'destination' in task['content'])

    def split_complex_task(self, task):
        """拆分复杂任务为依赖子任务"""
        return [
            {
                'type': 'supply',
                'subtype': 'pick_sample',
                'priority': task['priority'],
                'target_pos': task['target_pos'],
                'content': {'item': 'sample', 'quantity': task['content']['quantity']},
                'sender': task['sender']
            },
            {
                'type': 'supply',
                'subtype': 'deliver_sample',
                'priority': task['priority'],
                'target_pos': task['content']['destination'],
                'content': {'item': 'sample', 'quantity': task['content']['quantity']},
                'depend_on': 'pick_sample',
                'sender': task['sender']
            }
        ]

    # 其他原有方法（注册机器人、添加障碍物等）
    def register_robot(self, robot_type, robot):
        if robot_type in self.robots:
            self.robots[robot_type].append(robot)
            robot.controller = self

    def add_obstacle(self, x, y):
        self.map_obstacles.add((x, y))