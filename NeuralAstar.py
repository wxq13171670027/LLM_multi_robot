import numpy as np
import torch
import torch.nn as nn

class NeuralAStar(nn.Module):
    """Neural A*路径规划模型（简化实现）"""
    def __init__(self, grid_size=(50, 50)):
        super().__init__()
        self.grid_size = grid_size
        # 卷积网络提取环境特征
        self.conv = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 1, kernel_size=3, padding=1)
        )

    def forward(self, start_map, goal_map, obstacle_map):
        """
        输入：
        - start_map: (1, 1, H, W) 起始位置热力图
        - goal_map: (1, 1, H, W) 目标位置热力图
        - obstacle_map: (1, 1, H, W) 障碍物掩码（1为障碍）
        输出：
        - path_prob: (H, W) 路径概率图
        """
        # 融合输入特征
        x = torch.cat([start_map, goal_map, obstacle_map], dim=1)  # (1, 3, H, W)
        x = self.conv(x)  # (1, 1, H, W)
        return torch.sigmoid(x).squeeze()  # 输出概率图

def convert_to_grid(x, y, grid_size=(50, 50), grid_range=((0, 25), (0, 25))):
    """将物理坐标转换为网格坐标"""
    x_min, x_max = grid_range[0]
    y_min, y_max = grid_range[1]
    grid_x = int((x - x_min) / (x_max - x_min) * grid_size[0])
    grid_y = int((y - y_min) / (y_max - y_min) * grid_size[1])
    return np.clip(grid_x, 0, grid_size[0]-1), np.clip(grid_y, 0, grid_size[1]-1)

def neural_astar_path_planning(start_x, start_y, goal_x, goal_y, obstacles, grid_size=(50,50)):
    """
    基于Neural A*的路径规划实现
    参数：
    - start_x, start_y: 起始坐标
    - goal_x, goal_y: 目标坐标
    - obstacles: 障碍物列表[(x1,y1), (x2,y2)...]
    返回：
    - 路径坐标列表[(x1,y1), (x2,y2)...]
    """
    # 初始化网格
    H, W = grid_size
    start_map = np.zeros((H, W))
    goal_map = np.zeros((H, W))
    obstacle_map = np.zeros((H, W))

    # 填充起始/目标/障碍物信息
    s_x, s_y = convert_to_grid(start_x, start_y, grid_size)
    g_x, g_y = convert_to_grid(goal_x, goal_y, grid_size)
    start_map[s_x, s_y] = 1.0
    goal_map[g_x, g_y] = 1.0

    for (x, y) in obstacles:
        o_x, o_y = convert_to_grid(x, y, grid_size)
        obstacle_map[o_x, o_y] = 1.0

    # 转换为模型输入格式
    start_tensor = torch.FloatTensor(start_map).unsqueeze(0).unsqueeze(0)
    goal_tensor = torch.FloatTensor(goal_map).unsqueeze(0).unsqueeze(0)
    obstacle_tensor = torch.FloatTensor(obstacle_map).unsqueeze(0).unsqueeze(0)

    # 加载预训练模型（实际应用中需训练）
    model = NeuralAStar(grid_size)
    path_prob = model(start_tensor, goal_tensor, obstacle_tensor).detach().numpy()

    # 从概率图提取路径（简化的回溯法）
    path = []
    current_x, current_y = g_x, g_y
    path.append((goal_x, goal_y))  # 先添加目标点

    # 回溯到起点
    while (current_x, current_y) != (s_x, s_y) and len(path) < 100:  # 限制最大步数
        # 搜索邻域最大概率点
        max_prob = -1
        next_x, next_y = current_x, current_y
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx = current_x + dx
                ny = current_y + dy
                if 0 <= nx < H and 0 <= ny < W:
                    if path_prob[nx, ny] > max_prob and obstacle_map[nx, ny] == 0:
                        max_prob = path_prob[nx, ny]
                        next_x, next_y = nx, ny
        current_x, current_y = next_x, next_y
        
        # 转换回物理坐标
        x = (current_x / H) * 25  # 假设x范围0-25
        y = (current_y / W) * 25  # 假设y范围0-25
        path.append((round(x, 1), round(y, 1)))

    # 反转路径（从起点到目标）
    path.reverse()
    return path