from IANIvic import TaskPriority,RobotType,Task,Robot,HospitalEnv,LMInterface
class TaskSchedulingModule:
    def __init__(self, llm: LLMInterface, data_module: DataTransmissionModule):
        self.llm = llm
        self.data_module = data_module
        self.tasks = {}  # task_id: Task
        self.task_dag = nx.DiGraph()
        self.task_history = []  # 历史任务执行记录
        self.robot_expertise = {}  # robot_id: 擅长的任务类型
    
    def add_task(self, task: Task):
        # 添加新任务
        self.tasks[task.task_id] = task
        # 更新任务依赖图
        self.task_dag = self.llm.generate_task_dag(list(self.tasks.values()))
    
    def parse_and_create_task(self, natural_language: str, task_id: str, 
                             location: Tuple[float, float], dependencies: List[str] = None) -> Task:
        # 解析自然语言并创建任务
        parsed = self.llm.parse_task_description(natural_language)
        task = Task(
            task_id=task_id,
            description=natural_language,
            priority=parsed["priority"],
            location=location,
            estimated_duration=parsed["duration"],
            dependencies=dependencies if dependencies else []
        )
        self.add_task(task)
        return task
    
    def recruit_robots(self, task: Task, robots: List[Robot], env: HospitalEnv) -> List[Robot]:
        # 招募适合的机器人（AgentVerse的动态专家招募机制）
        suitable_robots = []
        
        # 根据任务类型和优先级筛选
        for robot in robots:
            # 检查机器人是否空闲
            if robot.status != "idle" and robot.status != "error":
                continue
                
            # 检查机器人能力是否匹配任务需求
            task_type = self.llm.parse_task_description(task.description)["task_type"]
            if task_type == "disinfection" and "消毒" not in robot.capabilities:
                continue
            if task_type == "patient_care" and "护理" not in robot.capabilities:
                continue
            if task_type == "emergency" and "急救" not in robot.capabilities:
                continue
                
            # 检查电池是否充足
            if robot.battery_level < 30:  # 电池低于30%不分配新任务
                continue
                
            # 检查通信状态
            if not self.data_module.check_robot_connection(robot, datetime.now()):
                continue
                
            suitable_robots.append(robot)
        
        # 根据任务优先级和机器人类型排序
        if task.priority in [TaskPriority.CRITICAL, TaskPriority.HIGH]:
            # 高优先级任务优先考虑T类机器人
            suitable_robots.sort(key=lambda r: (
                0 if r.robot_type == RobotType.T_CELL else 1,  # T类在前
                self._distance(r.position, task.location)  # 距离近的在前
            ))
        else:
            # 低优先级任务优先考虑B类机器人
            suitable_robots.sort(key=lambda r: (
                0 if r.robot_type == RobotType.B_CELL else 1,  # B类在前
                self._distance(r.position, task.location)  # 距离近的在前
            ))
            
        return suitable_robots
    
    def assign_task(self, task: Task, robots: List[Robot], env: HospitalEnv) -> bool:
        # 分配任务给最合适的机器人
        if task.status != "pending":
            return False  # 任务已分配或完成
        
        # 招募适合的机器人
        suitable_robots = self.recruit_robots(task, robots, env)
        
        if not suitable_robots:
            return False  # 没有合适的机器人
        
        # 选择最佳机器人
        best_robot = suitable_robots[0]
        
        # 分配任务
        task.assigned_robot = best_robot.robot_id
        task.status = "assigned"
        task.start_time = datetime.now()
        
        best_robot.current_task = task
        best_robot.status = "busy"
        
        # 更新机器人专长记录
        task_type = self.llm.parse_task_description(task.description)["task_type"]
        if best_robot.robot_id not in self.robot_expertise:
            self.robot_expertise[best_robot.robot_id] = {}
        if task_type not in self.robot_expertise[best_robot.robot_id]:
            self.robot_expertise[best_robot.robot_id][task_type] = 0
        self.robot_expertise[best_robot.robot_id][task_type] += 1
        
        return True
    
    def process_task_feedback(self, robot_id: str, feedback: Dict):
        # 处理任务反馈并更新系统状态
        task_id = feedback.get("task_id")
        if not task_id or task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        status = feedback.get("status")
        
        if status == "completed":
            task.status = "completed"
            task.end_time = datetime.now()
            self.task_history.append(task.to_dict())
            
            # 更新机器人状态
            for robot in [r for r in feedback.get("robots", []) if r.robot_id == robot_id]:
                robot.current_task = None
                robot.status = "idle"
                
        elif status == "failed":
            task.status = "failed"
            task.end_time = datetime.now()
            self.task_history.append(task.to_dict())
            
            # 记录失败原因，用于未来调度优化
            failure_reason = feedback.get("reason", "")
            
            # 更新机器人状态
            for robot in [r for r in feedback.get("robots", []) if r.robot_id == robot_id]:
                robot.current_task = None
                robot.status = "idle" if feedback.get("recoverable", True) else "error"
                
            # 重新分配失败的任务
            task.status = "pending"
            task.assigned_robot = None
            task.start_time = None
            task.end_time = None
            
        elif status == "in_progress":
            task.status = "in_progress"
            task.progress = feedback.get("progress", 0)
    
    def schedule_tasks(self, robots: List[Robot], env: HospitalEnv) -> List[Dict]:
        # 调度所有任务
        results = []
        
        # 先处理有依赖的任务
        for task_id in nx.topological_sort(self.task_dag):
            task = self.tasks[task_id]
            
            # 检查任务是否已完成或正在进行
            if task.status in ["completed", "in_progress", "assigned"]:
                continue
                
            # 检查依赖是否都已完成
            dependencies_met = all(
                self.tasks[dep_id].status == "completed" 
                for dep_id in task.dependencies if dep_id in self.tasks
            )
            
            if not dependencies_met:
                continue
                
            # 尝试分配任务
            success = self.assign_task(task, robots, env)
            results.append({
                "task_id": task.task_id,
                "assigned": success,
                "robot_id": task.assigned_robot,
                "time": datetime.now()
            })
            
        return results
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        # 计算两点之间的距离
        return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])** 2)**0.5