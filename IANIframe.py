import time
import math
from datetime import datetime, timedelta

# ------------------------------
# IANI框架核心控制类
# ------------------------------
class IANI_Controller:
    """IANI框架中央控制器，负责任务调度、路径规划与数据交互"""
    def __init__(self):
        self.robots = {  # 存储所有机器人实例
            'bedside': [],    # 床头护理机器人
            'logistics': [],  # 物流机器人
            'disinfect': []   # 消毒机器人
        }
        self.task_queue = []  # 任务队列[(优先级, 任务信息, 时间戳)]
        self.map_obstacles = set()  # 障碍物坐标集合

    def register_robot(self, robot_type, robot):
        """注册机器人到系统"""
        if robot_type in self.robots:
            self.robots[robot_type].append(robot)
            robot.controller = self  # 绑定控制器引用

    def add_obstacle(self, x, y):
        """添加障碍物坐标"""
        self.map_obstacles.add((x, y))

    def calculate_path(self, start_x, start_y, target_x, target_y):
        """
        基于Neural A*启发式算法的路径规划
        返回：路径坐标列表[(x1,y1), (x2,y2)...]
        """
        # 简化实现：直线优先，遇障碍物绕行
        path = [(start_x, start_y)]
        current_x, current_y = start_x, start_y
        step = 0.5  # 步长0.5米
        
        # 计算方向向量
        dx = target_x - start_x
        dy = target_y - start_y
        distance = math.hypot(dx, dy)
        steps = int(distance / step)
        
        for i in range(steps):
            next_x = current_x + dx * step / distance
            next_y = current_y + dy * step / distance
            # 检查是否为障碍物
            if (round(next_x), round(next_y)) not in self.map_obstacles:
                path.append((round(next_x, 1), round(next_y, 1)))
                current_x, current_y = next_x, next_y
            else:
                # 简单绕行逻辑：沿x轴偏移0.5米
                offset_x = 0.5 if next_x < target_x else -0.5
                path.append((round(next_x + offset_x, 1), round(next_y, 1)))
                current_x, current_y = next_x + offset_x, next_y
        
        path.append((target_x, target_y))
        return path

    def dispatch_task(self, task):
        """
        任务调度逻辑：基于AgentVerse动态专家招募机制
        task格式：{
            'type': 'supply'/'disinfect'/'transport',
            'sender': 发送者实例,
            'target_pos': (x,y),
            'priority': 'P0'/'P1'/'P2',  # P0最高
            'content': 任务内容
        }
        """
        # 优先级映射：P0→0, P1→1, P2→2（数字越小优先级越高）
        priority_map = {'P0':0, 'P1':1, 'P2':2}
        task_priority = priority_map[task['priority']]
        self.task_queue.append((task_priority, task, datetime.now()))
        
        # 按优先级排序任务队列
        self.task_queue.sort(key=lambda x: x[0])
        
        # 分配任务给最合适的机器人
        if task['type'] == 'supply':
            # 选择距离最近的物流机器人
            min_distance = float('inf')
            target_robot = None
            for bot in self.robots['logistics']:
                distance = math.hypot(
                    bot.x - task['target_pos'][0],
                    bot.y - task['target_pos'][1]
                )
                if distance < min_distance and not bot.is_busy:
                    min_distance = distance
                    target_robot = bot
            if target_robot:
                target_robot.receive_task(task)
                
        elif task['type'] == 'disinfect':
            # 选择负责该区域的消毒机器人
            for bot in self.robots['disinfect']:
                if bot.responsible_area[0] <= task['target_pos'][0] <= bot.responsible_area[1]:
                    bot.receive_task(task)
                    break

# ------------------------------
# 机器人基类
# ------------------------------
class Robot:
    """机器人基础类，包含通用属性与方法"""
    def __init__(self, robot_id, x, y, speed=0.5):
        self.robot_id = robot_id  # 机器人ID
        self.x = x  # 当前x坐标
        self.y = y  # 当前y坐标
        self.speed = speed  # 移动速度(m/s)
        self.is_busy = False  # 是否忙碌
        self.controller = None  # 控制器引用
        self.task_history = []  # 任务历史记录

    def move_to(self, target_x, target_y):
        """移动到目标坐标，返回耗时(秒)"""
        if not self.controller:
            raise Exception("未绑定控制器")
            
        path = self.controller.calculate_path(self.x, self.y, target_x, target_y)
        total_distance = 0
        
        # 计算总距离
        for i in range(1, len(path)):
            x1, y1 = path[i-1]
            x2, y2 = path[i]
            total_distance += math.hypot(x2-x1, y2-y1)
            
        # 更新当前位置
        self.x, self.y = target_x, target_y
        time_cost = total_distance / self.speed
        return round(time_cost, 1)

    def receive_task(self, task):
        """接收任务并执行"""
        self.is_busy = True
        start_time = datetime.now()
        self.task_history.append({
            'task': task,
            'start_time': start_time,
            'status': 'executing'
        })
        self.execute_task(task)

# ------------------------------
# 床头护理机器人类
# ------------------------------
class BedsideRobot(Robot):
    """床头护理机器人：执行抽血、测血压等任务"""
    def __init__(self, robot_id, x, y):
        super().__init__(robot_id, x, y)
        self.supplies = {  # 物资库存
            'cotton_swab': 50,  # 棉签
            'tourniquet': 10,   # 止血带
            'blood_tube': 20    # 采血管
        }
        self.work_count = 0  # 作业次数计数器

    def execute_task(self, task):
        """执行护理任务"""
        if task['type'] == 'self_operate':
            # 执行预编程医疗操作
            operation = task['content']['operation']
            op_time = {
                'throat_swab': 90,  # 咽喉试纸(秒)
                'blood_draw': 120,  # 抽血(秒)
                'blood_pressure': 60  # 测血压(秒)
            }[operation]
            
            # 模拟操作耗时
            time.sleep(op_time / 100)  # 加速模拟，实际需乘以100
            self.work_count += 1
            print(f"[{datetime.now()}] {self.robot_id}完成{operation}，位置({self.x},{self.y})")
            
            # 消耗物资
            if operation == 'throat_swab':
                self.supplies['cotton_swab'] -= 1
                # 低于阈值时请求补给
                if self.supplies['cotton_swab'] <= 5:
                    self.request_supply('cotton_swab', 20)
            
            # 每次操作后请求消毒
            self.request_disinfect()
            
            # 每5次操作请求样本传送
            if self.work_count % 5 == 0:
                self.request_transport()

        # 任务完成后更新状态
        for t in self.task_history:
            if t['status'] == 'executing':
                t['end_time'] = datetime.now()
                t['status'] = 'completed'
        self.is_busy = False

    def request_supply(self, item, quantity):
        """向物流机器人请求物资"""
        task = {
            'type': 'supply',
            'sender': self,
            'target_pos': (self.x, self.y),
            'priority': 'P1',
            'content': {'item': item, 'quantity': quantity}
        }
        self.controller.dispatch_task(task)
        print(f"[{datetime.now()}] {self.robot_id}请求{quantity}个{item}")

    def request_disinfect(self):
        """请求消毒"""
        task = {
            'type': 'disinfect',
            'sender': self,
            'target_pos': (self.x, self.y),
            'priority': 'P2',
            'content': {'area': 'operation', 'radius': 1.5}  # 1.5米范围
        }
        self.controller.dispatch_task(task)

    def request_transport(self):
        """请求样本传送"""
        task = {
            'type': 'supply',  # 复用物资传送通道
            'sender': self,
            'target_pos': (self.x, self.y),
            'priority': 'P1',
            'content': {'item': 'sample', 'quantity': 3, 'destination': (25, 10)}
        }
        self.controller.dispatch_task(task)

# ------------------------------
# 物流机器人类
# ------------------------------
class LogisticsRobot(Robot):
    """物流机器人：负责物资运输"""
    def __init__(self, robot_id, x, y):
        super().__init__(robot_id, x, y)
        self.cargo = {}  # 运载的物资

    def execute_task(self, task):
        """执行物流任务"""
        # 前往目标位置
        target_x, target_y = task['target_pos']
        move_time = self.move_to(target_x, target_y)
        print(f"[{datetime.now()}] {self.robot_id}抵达({target_x},{target_y})，耗时{move_time}秒")
        
        # 处理物资
        if task['content']['item'] != 'sample':
            # 运送物资：先去物资库取货
            if not self.cargo.get(task['content']['item']):
                self.move_to(5, 10)  # 物资库坐标
                self.cargo[task['content']['item']] = task['content']['quantity']
                print(f"[{datetime.now()}] {self.robot_id}从物资库取货{task['content']['quantity']}个{task['content']['item']}")
                self.move_to(target_x, target_y)  # 再次前往目标位置
            
            # 交付物资
            task['sender'].supplies[task['content']['item']] += task['content']['quantity']
            del self.cargo[task['content']['item']]
            print(f"[{datetime.now()}] {self.robot_id}完成{task['content']['quantity']}个{task['content']['item']}交付")
        
        else:
            # 传送样本
            self.cargo['sample'] = task['content']['quantity']
            dest_x, dest_y = task['content']['destination']
            move_time = self.move_to(dest_x, dest_y)
            print(f"[{datetime.now()}] {self.robot_id}将样本送达检验科，耗时{move_time}秒")
            del self.cargo['sample']

        # 任务完成
        for t in self.task_history:
            if t['status'] == 'executing':
                t['end_time'] = datetime.now()
                t['status'] = 'completed'
        self.is_busy = False

# ------------------------------
# 消毒机器人类
# ------------------------------
class DisinfectRobot(Robot):
    """消毒机器人：负责环境与设备消毒"""
    def __init__(self, robot_id, x, y, responsible_area):
        super().__init__(robot_id, x, y)
        self.responsible_area = responsible_area  # 负责区域(x_min, x_max)
        self.disinfectant = 100  # 消毒剂余量(%)

    def execute_task(self, task):
        """执行消毒任务"""
        # 前往目标位置
        target_x, target_y = task['target_pos']
        move_time = self.move_to(target_x, target_y)
        print(f"[{datetime.now()}] {self.robot_id}抵达消毒点({target_x},{target_y})，耗时{move_time}秒")
        
        # 执行消毒
        radius = task['content']['radius']
        disinfect_time = 45  # 固定消毒耗时(秒)
        time.sleep(disinfect_time / 100)  # 加速模拟
        self.disinfectant -= 5  # 消耗消毒剂
        coverage = 98  # 消毒覆盖率(%)
        print(f"[{datetime.now()}] {self.robot_id}完成{radius}米范围消毒，覆盖率{coverage}%，耗时{disinfect_time}秒")
        
        # 任务完成
        for t in self.task_history:
            if t['status'] == 'executing':
                t['end_time'] = datetime.now()
                t['status'] = 'completed'
        self.is_busy = False

# ------------------------------
# 场景测试代码
# ------------------------------
if __name__ == "__main__":
    # 初始化IANI控制器
    iani = IANI_Controller()
    
    # 添加障碍物（示例：走廊拐角）
    iani.add_obstacle(10, 9)
    iani.add_obstacle(15, 9)
    
    # 创建机器人实例
    bedside_bots = [
        BedsideRobot("A1", 10, 5),
        BedsideRobot("A2", 15, 5),
        BedsideRobot("A3", 20, 5)
    ]
    logistics_bots = [
        LogisticsRobot("B1", 5, 10),
        LogisticsRobot("B2", 10, 10),
        LogisticsRobot("B3", 15, 10)
    ]
    disinfect_bots = [
        DisinfectRobot("C1", 10, 8, (5, 12)),    # 负责5-12x区域
        DisinfectRobot("C2", 15, 8, (12, 18)),  # 负责12-18x区域
        DisinfectRobot("C3", 20, 8, (18, 25))   # 负责18-25x区域
    ]
    
    # 注册机器人
    for bot in bedside_bots:
        iani.register_robot('bedside', bot)
    for bot in logistics_bots:
        iani.register_robot('logistics', bot)
    for bot in disinfect_bots:
        iani.register_robot('disinfect', bot)
    
    # 模拟场景1：A1执行咽喉试纸采样并请求补给
    print("\n====== 场景1：床头护理与物资补给 ======")
    a1 = bedside_bots[0]
    a1.receive_task({
        'type': 'self_operate',
        'content': {'operation': 'throat_swab'}
    })
    
    # 等待任务完成（实际环境中由控制器异步调度）
    time.sleep(2)  # 模拟时间流逝
    
    # 模拟场景3：A3突发止血带短缺
    print("\n====== 场景3：突发物资短缺 ======")
    a3 = bedside_bots[2]
    a3.supplies['tourniquet'] = 0  # 手动设置为0
    a3.request_supply('tourniquet', 5)  # 主动请求
    
    time.sleep(3)  # 模拟时间流逝