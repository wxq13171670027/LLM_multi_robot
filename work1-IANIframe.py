from IANIvic import TaskPriority,RobotType,Task,Robot,HospitalEnv,LMInterface
class IANIFramework:
    def __init__(self, env: HospitalEnv):
        self.llm = LLMInterface()
        #大模型接口
        self.data_module = DataTransmissionModule(self.llm)
        #数据传输模块
        self.scheduling_module = TaskSchedulingModule(self.llm, self.data_module)
        #任务调度模块，负责分配任务给机器人
        self.path_module = PathPlanningModule(env)
        #路径规划模块，计算机器人的移动路径
        self.hri_module = HumanRobotInteractionModule(self.llm)
        #人机交互模块
        self.env = env
        #医院环境实例（保存医院环境信息）
        self.robots = []
        #管理机器人的列表 后面通过add_robot添加到系统
        self.current_time = datetime.now()
        #当前时间  用于处理任务超时，状态更新等情况
    def add_robot(self, robot: Robot):
        # 添加机器人到系统
        self.robots.append(robot)
    
    def process_human_command(self, command: str, context: Dict = None) -> Dict:
        # 处理人类指令
        #解析人类指令
        #默认上下文为空字典
        context = context if context else {}
        parsed_command = self.hri_module.parse_human_command(command, context)
        
        # 创建任务ID
        task_id = f"task_{len(self.scheduling_module.tasks) + 1}"
        
        # 获取位置信息（从医院环境中查询）
        location_name = parsed_command.get("location", "unknown")
        location = self.env.rooms.get(location_name, (0, 0))
        
        # 创建任务
        #将解析结果转换为task对象（包含ID、位置、依赖等信息）
        task = self.scheduling_module.parse_and_create_task(
            natural_language=command,
            task_id=task_id,
            location=location,
            dependencies=parsed_command.get("dependencies", [])#大模型构建任务依赖
            
        )
        
        # 记录交互历史（方便追溯，提高可解释性）
        #将时间戳，总指令，指令分解，任务编号 记录到列表中
        self.hri_module.interaction_history.append({
            "timestamp": datetime.now(), 
            "command": command,
            "parsed": parsed_command,
            "task_id": task_id
        })
        
        # 返回结果
        return {
            "success": True,
            "task_id": task_id,
            "parsed_command": parsed_command
        }
    
    #初始化与环境更新
    def step(self, human_positions: Dict[str, Tuple[float, float]] = None) -> Dict:
        # 系统运行一步
        #初始化当前时间和人类位置
        self.current_time = datetime.now()
        human_positions = human_positions if human_positions else {}
        
        # 更新环境状态   关注人类流动情况
        self.env.update_human_traffic(self.current_time)
        
        # 调整通信策略
        self.data_module.adjust_communication_strategy(self.env)
        
        # 检查机器人连接状态
        #处理失联机器人
        for robot in self.robots:
            if not self.data_module.check_robot_connection(robot, self.current_time):
                # 处理失联机器人
                self.data_module.handle_disconnected_robot(robot, self.robots, self.current_time)
        
        # 调度任务
        scheduling_results = self.scheduling_module.schedule_tasks(self.robots, self.env)
        
        # 更新路径规划
        path_updates = []
        for robot in self.robots:
            if robot.status == "busy" and robot.current_task:
                #只处理忙碌且有任务的机器人
                # 正在执行任务的机器人更新路径
                task = robot.current_task
                #更新路径（避开其他机器人
                success = self.path_module.update_robot_path(
                    robot, task.location, self.current_time, 
                    [r for r in self.robots if r.robot_id != robot.robot_id]
                    #排除自身的其他机器人 避免碰撞
                )
                #记录路径 更新结果
               
                path_updates.append({
                    "robot_id": robot.robot_id,
                    "path_updated": success,
                    "path_length": len(robot.path) if success else 0
                })
        
        # 执行机器人动作
        action_results = []
        for robot in self.robots:
            if robot.status == "busy" and robot.current_task and robot.path:
                # 执行移动动作
                if len(robot.path) > 1:
                    #路径长度>1 ->移动到下一个点
                    next_pos = robot.path[1] #下一个目标点
                    action = {
                        "type": "move",
                        "target": next_pos,
                        "speed": 0.5  # 固定速度
                    } #移动动作定义
                    
                    # 检查安全约束（如避开人类）
                    human_pos_list = list(human_positions.values())
                    action_result = self.hri_module.execute_safe_action(robot, action, human_pos_list)
                    
                    if action_result["success"]: #移动成功
                        # 移除已到达的点
                        robot.path.pop(0)
                        
                        # 消耗电池
                        distance = self.path_module._distance(robot.position, next_pos)
                        robot.update_battery(distance * 0.5)  # 每单位距离消耗0.5%电池
                        
                        # 发送状态更新
                        #不同类型传输内容不同
                        if robot.robot_type == RobotType.T_CELL:
                            #T_cell 类型 ：传输任务进度
                            task_status = {
                                "task_id": robot.current_task.task_id,
                                "progress": min(100, 100 * (1 - len(robot.path) / len(robot.path) if robot.path else 1)),
                                "priority": robot.current_task.priority
                            }
                            self.data_module.t_bot_transmit(robot, task_status, self.current_time)
                        else:
                            #其他类型：传输电池、位置等状态
                            status_summary = {
                                "completed_tasks": [],
                                "pending_tasks": [robot.current_task.task_id],
                                "sensors": {
                                    "battery": robot.battery_level,
                                    "position": robot.position
                                }
                            }
                            self.data_module.b_bot_transmit(robot, status_summary, self.current_time)
                    
                    action_results.append({
                        "robot_id": robot.robot_id,
                        "action": action,
                        "result": action_result
                    })
                else:
                    # 已到达目标位置，执行任务
                    action = {
                        "type": "perform_task",
                        "task_id": robot.current_task.task_id
                    }
                    
                    action_result = self.hri_module.execute_safe_action(robot, action, list(human_positions.values()))
                    action_results.append({
                        "robot_id": robot.robot_id,
                        "action": action,
                        "result": action_result
                    })
                    
                    # 更新任务状态，加入历史记忆中
                    if action_result["success"]:
                        feedback = {
                            "task_id": robot.current_task.task_id,
                            "status": "completed",
                            "robots": self.robots
                        }
                        self.scheduling_module.process_task_feedback(robot.robot_id, feedback)
        
        # 返回本步结果
        return {
            "timestamp": self.current_time,
            "scheduling_results": scheduling_results,
            "path_updates": path_updates,
            "action_results": action_results,
            "robot_statuses": [r.to_dict() for r in self.robots],
            "task_statuses": [t.to_dict() for t in self.scheduling_module.tasks.values()]
        }
    
    def get_system_status(self) -> Dict:
        # 获取系统状态
        return {
            "current_time": self.current_time,
            "robot_count": len(self.robots),
            "task_count": len(self.scheduling_module.tasks),
            "completed_tasks": sum(1 for t in self.scheduling_module.tasks.values() if t.status == "completed"),
            "pending_tasks": sum(1 for t in self.scheduling_module.tasks.values() if t.status == "pending"),
            "robot_statuses": [r.to_dict() for r in self.robots],
            "communication_status": self.env.communication_status,
            "human_positions": getattr(self.hri_module, 'human_positions', {})
        }