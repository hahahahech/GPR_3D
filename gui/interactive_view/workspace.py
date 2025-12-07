"""
工作空间相关方法和辅助函数
"""
import pyvista as pv
import numpy as np
from typing import Optional


def create_workspace_bounds_mesh(bounds: np.ndarray):
    """
    创建建模空间边界框的网格对象
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        
    Returns:
    --------
    pyvista.PolyData
        边界框线框网格
    """
    x_min, x_max = bounds[0], bounds[1]
    y_min, y_max = bounds[2], bounds[3]
    z_min, z_max = bounds[4], bounds[5]
    
    # 创建边界框的8个顶点
    vertices = np.array([
        [x_min, y_min, z_min],  # 0
        [x_max, y_min, z_min],  # 1
        [x_max, y_max, z_min],  # 2
        [x_min, y_max, z_min],  # 3
        [x_min, y_min, z_max],  # 4
        [x_max, y_min, z_max],  # 5
        [x_max, y_max, z_max],  # 6
        [x_min, y_max, z_max],  # 7
    ])
    
    # 定义12条边（立方体的12条边）
    edges = np.array([
        [0, 1], [1, 2], [2, 3], [3, 0],  # 底面
        [4, 5], [5, 6], [6, 7], [7, 4],  # 顶面
        [0, 4], [1, 5], [2, 6], [3, 7],  # 垂直边
    ])
    
    # 创建线框 - 使用PolyData格式
    lines_array = []
    for edge in edges:
        lines_array.append(2)  # 每条边有2个点
        lines_array.append(int(edge[0]))
        lines_array.append(int(edge[1]))
    
    # 创建PolyData对象
    lines_mesh = pv.PolyData(vertices)
    lines_mesh.lines = np.array(lines_array, dtype=np.int32)
    
    return lines_mesh


def calculate_workspace_center(bounds: np.ndarray) -> np.ndarray:
    """
    计算建模空间中心点
    
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        
    Returns:
    --------
    np.ndarray
        中心点坐标 [x, y, z]
    """
    return np.array([
        (bounds[0] + bounds[1]) / 2.0,
        (bounds[2] + bounds[3]) / 2.0,
        (bounds[4] + bounds[5]) / 2.0
    ])


def calculate_initial_camera_distance(bounds: np.ndarray) -> float:
    """
    计算初始摄像机距离
    
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        
    Returns:
    --------
    float
        建议的摄像机距离
    """
    # 计算空间对角线长度
    dx = bounds[1] - bounds[0]
    dy = bounds[3] - bounds[2]
    dz = bounds[5] - bounds[4]
    diagonal = np.sqrt(dx**2 + dy**2 + dz**2)
    # 距离设为对角线的1.5倍，确保能看到整个空间
    return diagonal * 1.5


def get_default_workspace_bounds() -> np.ndarray:
    """
    获取默认的建模空间边界
    
    Returns:
    --------
    np.ndarray
        默认边界 [xmin, xmax, ymin, ymax, zmin, zmax]
    """
    return np.array([-100.0, 100.0, -100.0, 100.0, -50.0, 0.0])


def create_grid_mesh(bounds: np.ndarray, grid_spacing: float = 10.0, z: float = 0.0) -> pv.PolyData:
    """
    创建Z=0平面的网格
    
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
    grid_spacing : float
        网格间距，默认10.0
    z : float
        Z坐标值，默认0.0（Z=0平面）
        
    Returns:
    --------
    pyvista.PolyData
        网格线框对象
    """
    x_min, x_max = bounds[0], bounds[1]
    y_min, y_max = bounds[2], bounds[3]
    
    # 生成网格线
    vertices = []
    lines_array = []
    
    # X方向的网格线（平行于Y轴）
    x_values = np.arange(x_min, x_max + grid_spacing, grid_spacing)
    for x in x_values:
        if x > x_max:
            x = x_max
        # 每条线2个点
        v0_idx = len(vertices)
        vertices.append([x, y_min, z])
        v1_idx = len(vertices)
        vertices.append([x, y_max, z])
        lines_array.extend([2, v0_idx, v1_idx])
    
    # Y方向的网格线（平行于X轴）
    y_values = np.arange(y_min, y_max + grid_spacing, grid_spacing)
    for y in y_values:
        if y > y_max:
            y = y_max
        # 每条线2个点
        v0_idx = len(vertices)
        vertices.append([x_min, y, z])
        v1_idx = len(vertices)
        vertices.append([x_max, y, z])
        lines_array.extend([2, v0_idx, v1_idx])
    
    # 创建PolyData对象
    vertices_array = np.array(vertices)
    mesh = pv.PolyData(vertices_array)
    mesh.lines = np.array(lines_array, dtype=np.int32)
    
    return mesh


def create_origin_axes_mesh(bounds: np.ndarray, axis_length: Optional[float] = None) -> pv.PolyData:
    """
    创建原点坐标轴（XY轴）
    
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
    axis_length : float, optional
        坐标轴长度，如果为None，则根据工作空间大小自动计算
        
    Returns:
    --------
    pyvista.PolyData
        坐标轴线框对象
    """
    x_min, x_max = bounds[0], bounds[1]
    y_min, y_max = bounds[2], bounds[3]
    z_min, z_max = bounds[4], bounds[5]
    
    # 计算坐标轴长度（取X和Y范围的较小值的80%）
    if axis_length is None:
        x_range = x_max - x_min
        y_range = y_max - y_min
        axis_length = min(x_range, y_range) * 0.4
    
    # 原点位置（在Z=0平面）
    origin = np.array([0.0, 0.0, 0.0])
    
    # 创建顶点
    vertices = [
        origin,  # 0: 原点
        [origin[0] + axis_length, origin[1], origin[2]],  # 1: X轴端点
        [origin[0], origin[1] + axis_length, origin[2]],  # 2: Y轴端点
    ]
    
    # 创建线（X轴和Y轴）
    lines_array = [
        2, 0, 1,  # X轴
        2, 0, 2,  # Y轴
    ]
    
    # 创建PolyData对象
    vertices_array = np.array(vertices)
    mesh = pv.PolyData(vertices_array)
    mesh.lines = np.array(lines_array, dtype=np.int32)
    
    return mesh
