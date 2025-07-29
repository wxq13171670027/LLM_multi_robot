from IANIvic import TaskPriority,RobotType,Task,Robot,HospitalEnv,LMInterface

#为不同类型的机器人规划最优路径  处理路径冲突

class PathPlanningModule:
    def __init__(self, env: HospitalEnv):
        self.env = env
        self.path_cache = {}  # 缓存路径规划结果
    
    def _is_collision(self, point: Tuple[float, float]) -> bool:
        # 检查点是否与障碍物碰撞
        x, y = point
        for (ox, oy, ow, oh) in self.env.obstacles:
            if ox <= x <= ox + ow and oy <= y <= oy + oh:
                return True
        return False
    
    def _neural_astar_heuristic(self, start: Tuple[float, float], goal: Tuple[float, float], 
                                robot_type: RobotType, time: datetime) -> float:
        # 模拟Neural A*启发式算法
        
        # 基础欧氏距离
        base_dist = ((start[0] - goal[0])**2 + (start[1] - goal[1])** 2)**0.5
        #**是乘方
        
        
        # 考虑感染风险
        zone_risk = 0.0
        for zone, risk in self.env.infection_zones.items():
            #依次获得字典的每个键 和 每个值   键用zone来存，值用risk来存
            # 简化：假设区域是矩形，这里简化为检查点是否在区域内
            # 实际应用中需要更复杂的区域判定
            zone_pos = self.env.rooms.get(zone, (0, 0))
            if abs(start[0] - zone_pos[0]) < 5 and abs(start[1] - zone_pos[1]) < 5:
                zone_risk = risk
                break
        
        # 考虑人流密度
        traffic_factor = 1.0
        for zone, density in self.env.traffic_density.items():
            zone_pos = self.env.rooms.get(zone, (0, 0))
            if abs(start[0] - zone_pos[0]) < 5 and abs(start[1] - zone_pos[1]) < 5:
                traffic_factor = 1.0 + density * 0.1  # 人流多的地方代价增加
                break
        
        # T类机器人更注重速度，B类机器人更注重安全
        if robot_type == RobotType.T_CELL:
            # T类：风险权重低，速度权重高
            return base_dist * traffic_factor + zone_risk * 0.1
        else:
            # B类：风险权重高，速度权重低
            return base_dist * traffic_factor + zone_risk * 0.5
    
    def _a_star_search(self, start: Tuple[float, float], goal: Tuple[float, float], 
                      robot_type: RobotType, time: datetime) -> List[Tuple[float, float]]:
        # A*搜索算法实现
        open_set = {start}
        #待探索的节点集合（初始包含起点）
        closed_set = set()
        #已探索的节点集合（初始为空）
        
        # 代价函数
        g_score = {start: 0}
        #从起点到当前节点的实际代价
        f_score = {start: self._neural_astar_heuristic(start, goal, robot_type, time)}
        #估计总代价 用于选择下一个探索节点
        
        # 路径追踪
        came_from = {}
        #记录路径回溯关系 键为节点 值为前序节点
        
        while open_set:
            # 找到f_score最小的节点
            current = min(open_set, key=lambda x: f_score[x])
            #lambda用于快速构建匿名函数 接受参数x 返回f_score[x]

            if current == goal: #当前是目标节点
                # 重建路径
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]  # 反转路径
            
            open_set.remove(current)
            closed_set.add(current)
            
            # 生成邻居节点（8个方向）
            neighbors = []
            steps = [-1, 0, 1]
            for dx in steps:
                for dy in steps:
                    if dx == 0 and dy == 0:
                        continue  # 跳过当前节点
                    neighbor = (current[0] + dx, current[1] + dy)
                    # 检查是否在合理范围内且不碰撞
                    if 0 <= neighbor[0] <= 100 and 0 <= neighbor[1] <= 100 and not self._is_collision(neighbor):
                        neighbors.append(neighbor)
            
            for neighbor in neighbors:
                if neighbor in closed_set:
                    continue
                
                # 计算临时g_score
                tentative_g_score = g_score[current] + 1  # 假设每步代价为1
                
                if neighbor not in open_set:
                    open_set.add(neighbor) #邻居未在open_set中，加入并更新代价
                elif tentative_g_score >= g_score.get(neighbor, float('inf')):
                    continue  # 不是更好的路径
                
                # 更新路径信息
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = g_score[neighbor] + self._neural_astar_heuristic(neighbor, goal, robot_type, time)
        
        # 如果没有找到路径，返回空
        return []
    
    def plan_path(self, robot: Robot, goal: Tuple[float, float], time: datetime) -> List[Tuple[float, float]]:
        # 规划路径
        start = robot.position
        
        # 检查缓存  生成缓存键
        cache_key = (start, goal, robot.robot_type, time.minute)  # 按分钟缓存
                                                                    #减少高频重复计算       
        if cache_key in self.path_cache:  #生成缓存键
            return self.path_cache[cache_key]
        
        # 使用A*算法规划路径
        path = self._a_star_search(start, goal, robot.robot_type, time)
        
        # 缓存路径
        self.path_cache[cache_key] = path
        
        return path
    
    def check_path_conflicts(self, robot: Robot, other_robots: List[Robot], time: datetime) -> List[Tuple[float, float, float]]:
        # 检查路径冲突  当前机器人与其他机器人的路径是否存在碰撞风险
        conflicts = []
        robot_path = robot.path
        robot_speed = 0.5  #简化假设机器人速度 单位/秒
        
        for other in other_robots:
            if other.robot_id == robot.robot_id or not other.path:
                continue
                
            other_speed = 0.5  # 假设所有机器人速度相同
            
            # 检查未来5秒内是否有冲突
            for t in range(10):  # 检查未来10步
                time_offset = t * 2  # 每2秒检查一次
                current_time = time + timedelta(seconds=time_offset)
                
                # 计算机器人在该时间点的位置
                robot_step = min(int(robot_speed * time_offset), len(robot_path) - 1)
                robot_pos = robot_path[robot_step] if robot_step < len(robot_path) else robot_path[-1]
                
                # 计算其他机器人在该时间点的位置
                other_step = min(int(other_speed * time_offset), len(other.path) - 1)
                other_pos = other.path[other_step] if other_step < len(other.path) else other.path[-1]
                
                # 检查距离是否过近
                distance = self._distance(robot_pos, other_pos)
                if distance < 1.5:  # 距离小于1.5单位视为冲突
                    conflicts.append((robot_pos[0], robot_pos[1], time_offset))
                    break  # 找到一个冲突就够了
        
        return conflicts
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        # 计算两点之间的距离
        return ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])** 2)**0.5
    
    def replan_path(self, robot: Robot, goal: Tuple[float, float], time: datetime, 
                   avoid_robots: List[Robot] = None) -> List[Tuple[float, float]]:
        # 重新规划路径，考虑避障
        avoid_robots = avoid_robots if avoid_robots else []
        
        # 临时添加机器人位置作为障碍物
        original_obstacles = self.env.obstacles.copy()
        for other in avoid_robots:
            # 将其他机器人位置视为临时障碍物
            self.env.obstacles.append((other.position[0] - 0.5, other.position[1] - 0.5, 1.0, 1.0))
        
        # 重新规划路径
        new_path = self.plan_path(robot, goal, time)
        
        # 恢复原始障碍物
        self.env.obstacles = original_obstacles
        
        return new_path
    
    def update_robot_path(self, robot: Robot, goal: Tuple[float, float], time: datetime, 
                         other_robots: List[Robot]) -> bool:
        # 更新机器人路径，处理可能的冲突
        # 规划新路径
        new_path = self.plan_path(robot, goal, time)
        
        if not new_path:
            return False  # 无法规划路径
        
        # 检查路径冲突
        conflicts = self.check_path_conflicts(robot, other_robots, time)
        
        if conflicts:
            # 有冲突，重新规划路径
            conflicting_robots = [r for r in other_robots if any(
                self._distance(r.position, (x, y)) < 2.0 for x, y, _ in conflicts
            )]
            
            new_path = self.replan_path(robot, goal, time, conflicting_robots)
            if not new_path:
                return False
        
        # 更新机器人路径
        robot.path = new_path
        return True