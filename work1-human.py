from IANIvic import TaskPriority,RobotType,Task,Robot,HospitalEnv,LMInterface

#此部分负责用大模型翻译人类指令 和 安全检查

#人机交互
class HumanRobotInteractionModule:
    def __init__(self, llm: LLMInterface):
        self.llm = llm #大模型语言接口
        self.interaction_history = []  # 存储人机交互历史 用于反馈提升
        #安全约束配置（机器人行为的安全准则）
        self.safety_constraints = {
            "max_speed": 1.0,  # 最大速度
            "max_force": 5.0,  # 最大作用力（对于难处理的污渍  难搬运的物品）
            "min_distance_to_human": 1.5,  # 与人的最小距离
            "no_go_zones": []  # 禁止进入的区域（正在进行手术的室等）
        }
    
    def parse_human_command(self, command: str, context: Dict) -> Dict:
        
        #三方位护航
        #结合LLM的基础解系和上下文信息（如已知位置），提升解析准确性，特别标记安全相关指令
        
        # 解析人类指令（提取关键信息）（注：python使用前要赋值，不需要声明）
        parsed = self.llm.parse_task_description(command)
        
        # 结合上下文增强解析（如已知位置优先使用）
        location = context.get("location", "unknown")
        if location != "unknown":
            parsed["location"] = location
        
        # 提取安全相关信息（如指令中包含“小心”“注意”）
        if "小心" in command or "注意" in command:
            parsed["safety_alert"] = True
        else:
            parsed["safety_alert"] = False
            
        return parsed
    
    def generate_robot_response(self, robot_id: str, task_status: Dict, human_query: str = None) -> str:
        # 生成机器人对人类的响应
        if human_query:
            # 回答人类查询（如”任务完成了吗？“”你在哪儿？“）
            task_id = task_status.get("task_id", "unknown")
            status = task_status.get("status", "unknown")
            progress = task_status.get("progress", 0)
            
            if "完成" in human_query or "结束" in human_query:
                if status == "completed":
                    return f"机器人 {robot_id} 已完成任务 {task_id}"
                else:
                    return f"机器人 {robot_id} 正在执行任务 {task_id}，进度: {progress}%"
            elif "位置" in human_query:
                pos = task_status.get("position", (0, 0))
                return f"机器人 {robot_id} 当前位置: X={pos[0]:.1f}, Y={pos[1]:.1f}"
            else:
                return f"机器人 {robot_id} 正在执行任务: {task_status.get('description', '未知任务')}"
        else:
            # 主动汇报状态（如，完成成功/失败时）
            task_id = task_status.get("task_id", "unknown")
            status = task_status.get("status", "unknown")
            
            if status == "completed":
                return f"任务 {task_id} 已完成"
            elif status == "failed":
                return f"任务 {task_id} 执行失败: {task_status.get('reason', '未知原因')}"
            else:
                progress = task_status.get("progress", 0)
                return f"任务 {task_id} 正在进行中，进度: {progress}%"
    
    def safety_shield_check(self, robot: Robot, action: Dict, human_positions: List[Tuple[float, float]]) -> Tuple[bool, str]:
        # 安全盾检查：评估动作安全性
        # 检查速度限制
        speed = action.get("speed", 0)
        if speed > self.safety_constraints["max_speed"]:
            return False, f"速度超过限制: {speed} > {self.safety_constraints['max_speed']}"
        
        # 检查与人的距离
        for pos in human_positions:
            distance = self._distance(robot.position, pos)
            if distance < self.safety_constraints["min_distance_to_human"]:
                return False, f"与人距离过近: {distance:.2f} < {self.safety_constraints['min_distance_to_human']}"
        
        # 检查是否在禁止区域
        for (x, y, w, h) in self.safety_constraints["no_go_zones"]:
            if x <= robot.position[0] <= x + w and y <= robot.position[1] <= y + h:
                return False, f"进入禁止区域"
                                #（f语法，用于在字符串中嵌入变量或表达式）
        # 检查作用力限制（如果是物理交互任务）
        force = action.get("force", 0)
        if force > self.safety_constraints["max_force"]:
            return False, f"作用力超过限制: {force} > {self.safety_constraints['max_force']}"
        
        return True, "安全检查通过"
    
    def adjust_action_for_safety(self, robot: Robot, action: Dict, human_positions: List[Tuple[float, float]]) -> Dict:
        #调整执行的参数
        
        # 调整动作以满足安全约束
        adjusted = action.copy()
        #复制原动作，避免修改原始数据
        
        # 限制速度不超过最大值
        if adjusted.get("speed", 0) > self.safety_constraints["max_speed"]:
            adjusted["speed"] = self.safety_constraints["max_speed"]
        
        # 检查与人的距离，如果过近则减速
        for pos in human_positions:
            distance = self._distance(robot.position, pos)
            if distance < self.safety_constraints["min_distance_to_human"] * 1.5:
                # 距离接近阈值，减速
                adjusted["speed"] = adjusted.get("speed", 0) * (distance / (self.safety_constraints["min_distance_to_human"] * 1.5))
                break
        
        # 限制作用力
        if adjusted.get("force", 0) > self.safety_constraints["max_force"]:
            adjusted["force"] = self.safety_constraints["max_force"]
        
        return adjusted
    
    def execute_safe_action(self, robot: Robot, action: Dict, human_positions: List[Tuple[float, float]]) -> Dict:
        
        #检查->调整->再检查 ->执行/取消
        
        # 执行安全动作
        # 安全检查
        is_safe, message = self.safety_shield_check(robot, action, human_positions)
        
        if not is_safe:
            # 不安全，尝试调整动作
            adjusted_action = self.adjust_action_for_safety(robot, action, human_positions)
            is_safe_after_adjust, message = self.safety_shield_check(robot, adjusted_action, human_positions)
            
            if not is_safe_after_adjust:
                # 调整后仍不安全，取消动作
                return {
                    "success": False,
                    "action": action,
                    "reason": message_after,
                    "adjusted": False
                }
            else:
                # 执行调整后的动作
                result = self._execute_action(robot, adjusted_action)
                result["adjusted"] = True  #标记动作已调整
                return result
        else:
            # 安全，执行原动作
            result = self._execute_action(robot, action)
            result["adjusted"] = False
            return result
    
    def _execute_action(self, robot: Robot, action: Dict) -> Dict:
        # 执行动作（底层控制接口）  此处进行了简化，实际主要靠预编程
        action_type = action.get("type")
        
        if action_type == "move":
            # 移动动作
            target_pos = action.get("target")
            if target_pos:
                # 更新位置（简化实现）
                robot.update_position(target_pos)
                return {
                    "success": True,
                    "action": action,
                    "new_position": target_pos,
                    "timestamp": datetime.now()
                }
            else:
                return {
                    "success": False,
                    "action": action,
                    "reason": "缺少目标位置",
                    "timestamp": datetime.now()
                }
        
        elif action_type == "perform_task":
            # 执行任务动作
            task_id = action.get("task_id")
            return {
                "success": True,
                "action": action,
                "task_id": task_id,
                "timestamp": datetime.now()
            }
        
        elif action_type == "stop":
            # 停止动作
            return {
                "success": True,
                "action": action,
                "status": "stopped",
                "timestamp": datetime.now()
            }
        
        else:
            return {
                "success": False,
                "action": action,
                "reason": "未知动作类型",
                "timestamp": datetime.now()
            }
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        # 计算两点之间的距离
        return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])** 2)**0.5
    
    def update_human_positions(self, positions: Dict[str, Tuple[float, float]]):
        # 更新人员位置
        self.human_positions = positions
    
    def get_human_proximity_alert(self, robot: Robot) -> Dict:
        # 检查是否有人靠近机器人
        if not hasattr(self, 'human_positions'):
            return {"alert": False}
        
        min_distance = min(
            self._distance(robot.position, pos) 
            for pos in self.human_positions.values()
        ) if self.human_positions else float('inf')
        
        if min_distance < self.safety_constraints["min_distance_to_human"]:
            # 过近，发出警报
            return {
                "alert": True,
                "min_distance": min_distance,
                "recommended_action": "减速并停止"
            }
        elif min_distance < self.safety_constraints["min_distance_to_human"] * 1.5:
            # 较近，建议减速
            return {
                "alert": True,
                "min_distance": min_distance,
                "recommended_action": "减速"
            }
        else:
            return {"alert": False}