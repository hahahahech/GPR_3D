"""
基础几何元素类（点、线、面）
用于交互式建模可视化界面
"""
from dataclasses import dataclass
from typing import List, Optional, Union
import numpy as np
from scipy.interpolate import splprep, splev


def round_to_2_decimals(value):
    """将值四舍五入到2位小数"""
    if isinstance(value, (list, np.ndarray)):
        return np.round(value, 2)
    return round(float(value), 2)


@dataclass
class Point:
    """点几何元素 - 精度2位小数"""
    id: str
    position: np.ndarray  # 位置坐标 [x, y, z]，精度2位小数
    name: Optional[str] = None
    
    def __post_init__(self):
        """确保position是numpy数组并四舍五入到2位小数"""
        if not isinstance(self.position, np.ndarray):
            self.position = np.array(self.position, dtype=np.float32)
        if self.position.shape != (3,):
            raise ValueError("Position must be a 3D point [x, y, z]")
        # 四舍五入到2位小数
        self.position = round_to_2_decimals(self.position)
    
    @property
    def x(self) -> float:
        """X坐标"""
        return float(self.position[0])
    
    @property
    def y(self) -> float:
        """Y坐标"""
        return float(self.position[1])
    
    @property
    def z(self) -> float:
        """Z坐标"""
        return float(self.position[2])
    
    def distance_to(self, other: 'Point') -> float:
        """计算到另一点的距离（2位小数）"""
        dist = np.linalg.norm(self.position - other.position)
        return round_to_2_decimals(dist)
    
    def translate(self, vector: np.ndarray):
        """平移点"""
        vector = round_to_2_decimals(vector)
        self.position = round_to_2_decimals(self.position + np.array(vector))
    
    def set_position(self, x: float, y: float, z: float):
        """设置位置"""
        self.position = round_to_2_decimals(np.array([x, y, z], dtype=np.float32))
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'position': [float(self.position[0]), float(self.position[1]), float(self.position[2])],
            'name': self.name
        }
    
    def copy(self) -> 'Point':
        """复制点"""
        return Point(
            id=self.id,
            position=self.position.copy(),
            name=self.name
        )


class Line:
    """线几何元素基类 - 默认为直线（2个点）"""
    
    def __init__(self, id: str, points: List[Point], name: Optional[str] = None):
        """
        初始化线
        
        Parameters:
        -----------
        id : str
            线的ID
        points : List[Point]
            点列表（直线需要2个点）
        name : str, optional
            线的名称
        """
        if len(points) < 2:
            raise ValueError("Line must have at least 2 points")
        self.id = id
        self.points = points
        self.name = name
    
    def get_vertices(self) -> np.ndarray:
        """获取所有顶点的坐标（2位小数）"""
        vertices = np.array([p.position for p in self.points])
        return round_to_2_decimals(vertices)
    
    def get_length(self) -> float:
        """计算线的总长度（2位小数）"""
        vertices = self.get_vertices()
        if len(vertices) == 2:
            # 直线：两点间距离
            length = np.linalg.norm(vertices[1] - vertices[0])
        else:
            # 多段线：计算各段长度之和
            total = 0.0
            for i in range(len(vertices) - 1):
                total += np.linalg.norm(vertices[i+1] - vertices[i])
            length = total
        return round_to_2_decimals(length)
    
    def add_point(self, point: Point, index: Optional[int] = None):
        """添加点到线"""
        if index is None:
            self.points.append(point)
        else:
            self.points.insert(index, point)
    
    def remove_point(self, point_id: str):
        """从线中移除点"""
        self.points = [p for p in self.points if p.id != point_id]
        if len(self.points) < 2:
            raise ValueError("Line must have at least 2 points after removal")
    
    def get_bounds(self) -> np.ndarray:
        """获取边界框（2位小数）"""
        vertices = self.get_vertices()
        bounds = np.array([
            vertices[:, 0].min(), vertices[:, 0].max(),
            vertices[:, 1].min(), vertices[:, 1].max(),
            vertices[:, 2].min(), vertices[:, 2].max()
        ])
        return round_to_2_decimals(bounds)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'points': [p.to_dict() for p in self.points],
            'line_type': self.__class__.__name__.lower(),
            'name': self.name
        }
    
    def copy(self) -> 'Line':
        """复制线"""
        return self.__class__(
            id=self.id,
            points=[p.copy() for p in self.points],
            name=self.name
        )
    
    @classmethod
    def from_points(cls, id: str, points: Union[List[Point], List[np.ndarray], np.ndarray],
                   name: Optional[str] = None) -> 'Line':
        """
        根据点生成线（类方法）
        
        Parameters:
        -----------
        id : str
            线的ID
        points : List[Point] or List[np.ndarray] or np.ndarray
            点列表或坐标数组
        name : str, optional
            线的名称
            
        Returns:
        --------
        Line
            直线对象（如果只有2个点）或折线对象（如果超过2个点）
        """
        # 转换点格式
        point_objects = []
        for i, p in enumerate(points):
            if isinstance(p, Point):
                point_objects.append(p)
            elif isinstance(p, np.ndarray):
                point_objects.append(Point(id=f"p_{id}_{i}", position=p))
            elif isinstance(p, (list, tuple)):
                point_objects.append(Point(id=f"p_{id}_{i}", position=np.array(p)))
            else:
                raise TypeError(f"Unsupported point type: {type(p)}")
        
        # 根据点数决定返回类型
        if len(point_objects) == 2:
            return cls(id=id, points=point_objects, name=name)
        else:
            # 超过2个点，返回折线
            return Polyline(id=id, points=point_objects, name=name)


class Polyline(Line):
    """折线类 - 继承自Line"""
    
    def __init__(self, id: str, points: List[Point], name: Optional[str] = None):
        """
        初始化折线
        
        Parameters:
        -----------
        id : str
            折线的ID
        points : List[Point]
            点列表（至少2个点）
        name : str, optional
            折线的名称
        """
        if len(points) < 2:
            raise ValueError("Polyline must have at least 2 points")
        super().__init__(id, points, name)
    
    def get_length(self) -> float:
        """计算折线的总长度（2位小数）"""
        vertices = self.get_vertices()
        total = 0.0
        for i in range(len(vertices) - 1):
            total += np.linalg.norm(vertices[i+1] - vertices[i])
        return round_to_2_decimals(total)


class Curve(Line):
    """曲线类 - 使用B样条生成光滑曲线，继承自Line"""
    
    def __init__(self, id: str, control_points: List[Point], 
                 degree: int = 3, num_points: int = 100,
                 name: Optional[str] = None):
        """
        初始化B样条曲线
        
        Parameters:
        -----------
        id : str
            曲线的ID
        control_points : List[Point]
            控制点列表（至少2个点）
        degree : int
            B样条次数（默认3，即三次B样条）
        num_points : int
            生成的曲线上的点数（用于显示和计算）
        name : str, optional
            曲线的名称
        """
        if len(control_points) < 2:
            raise ValueError("Curve must have at least 2 control points")
        if degree < 1:
            raise ValueError("Degree must be at least 1")
        if degree >= len(control_points):
            degree = len(control_points) - 1
        
        self.control_points = control_points
        self.degree = degree
        self.num_points = num_points
        self._curve_id = id  # 保存ID用于生成点
        
        # 生成B样条曲线上的点
        curve_points = self._generate_bspline_points(id)
        
        # 调用父类构造函数，使用生成的曲线点
        super().__init__(id, curve_points, name)
    
    def _generate_bspline_points(self, curve_id: str) -> List[Point]:
        """生成B样条曲线上的点"""
        # 获取控制点坐标
        control_coords = np.array([p.position for p in self.control_points])
        
        # 如果只有2个点，直接返回直线
        if len(control_coords) == 2:
            return [self.control_points[0].copy(), self.control_points[1].copy()]
        
        # 使用scipy的B样条插值
        # 分别对x, y, z坐标进行B样条插值
        try:
            # 计算参数化
            tck, u = splprep([control_coords[:, 0], 
                             control_coords[:, 1], 
                             control_coords[:, 2]], 
                            s=0, k=min(self.degree, len(control_coords) - 1))
            
            # 生成曲线上的点
            u_new = np.linspace(0, 1, self.num_points)
            curve_coords = splev(u_new, tck)
            
            # 组合为Nx3数组
            curve_vertices = np.column_stack(curve_coords)
            curve_vertices = round_to_2_decimals(curve_vertices)
            
            # 创建Point对象列表
            curve_points = []
            for i, pos in enumerate(curve_vertices):
                curve_points.append(Point(
                    id=f"{curve_id}_curve_point_{i}",
                    position=pos
                ))
            
            return curve_points
        except Exception as e:
            # 如果B样条失败，返回折线
            print(f"B-spline generation failed: {e}, using polyline instead")
            return [p.copy() for p in self.control_points]
    
    def get_control_points(self) -> List[Point]:
        """获取控制点"""
        return self.control_points.copy()
    
    def set_degree(self, degree: int):
        """设置B样条次数"""
        if degree < 1:
            raise ValueError("Degree must be at least 1")
        if degree >= len(self.control_points):
            degree = len(self.control_points) - 1
        self.degree = degree
        # 重新生成曲线点
        self.points = self._generate_bspline_points(self.id)
    
    def set_num_points(self, num_points: int):
        """设置曲线上的点数"""
        if num_points < 2:
            raise ValueError("Number of points must be at least 2")
        self.num_points = num_points
        # 重新生成曲线点
        self.points = self._generate_bspline_points(self.id)
    
    def get_length(self) -> float:
        """计算曲线的总长度（2位小数）"""
        # 使用生成的曲线点计算长度
        vertices = self.get_vertices()
        total = 0.0
        for i in range(len(vertices) - 1):
            total += np.linalg.norm(vertices[i+1] - vertices[i])
        return round_to_2_decimals(total)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        result = super().to_dict()
        result['control_points'] = [p.to_dict() for p in self.control_points]
        result['degree'] = self.degree
        result['num_points'] = self.num_points
        return result


@dataclass
class Surface:
    """面几何元素"""
    id: str
    vertices: np.ndarray  # 顶点坐标 (Nx3)，精度2位小数
    faces: Optional[np.ndarray] = None  # 面索引 (Mx3 for triangles, Mx4 for quads)
    surface_type: str = 'polygon'  # 'polygon', 'mesh', 'nurbs', 'plane'
    name: Optional[str] = None
    
    def __post_init__(self):
        """验证数据并四舍五入到2位小数"""
        if not isinstance(self.vertices, np.ndarray):
            self.vertices = np.array(self.vertices, dtype=np.float32)
        if len(self.vertices.shape) != 2 or self.vertices.shape[1] != 3:
            raise ValueError("Vertices must be Nx3 array")
        # 四舍五入到2位小数
        self.vertices = round_to_2_decimals(self.vertices)
        
        if self.faces is not None:
            if not isinstance(self.faces, np.ndarray):
                self.faces = np.array(self.faces, dtype=np.int32)
    
    @classmethod
    def from_lines(cls, id: str, lines: List[Line], 
                   name: Optional[str] = None) -> 'Surface':
        """
        根据线生成面（类方法）
        
        Parameters:
        -----------
        id : str
            面的ID
        lines : List[Line]
            线列表（应形成封闭环）
        name : str, optional
            面的名称
            
        Returns:
        --------
        Surface
            面对象
        """
        if len(lines) < 3:
            raise ValueError("At least 3 lines are required to form a surface")
        
        # 收集所有顶点
        all_vertices = []
        vertex_set = set()
        vertex_map = {}  # 用于映射重复顶点
        
        for line in lines:
            for point in line.points:
                pos_tuple = tuple(round_to_2_decimals(point.position))
                if pos_tuple not in vertex_set:
                    vertex_set.add(pos_tuple)
                    all_vertices.append(point.position)
                    vertex_map[pos_tuple] = len(all_vertices) - 1
        
        if len(all_vertices) < 3:
            raise ValueError("Not enough unique vertices to create a surface")
        
        vertices = np.array(all_vertices)
        
        # 简单的三角剖分（扇形三角剖分）
        # 假设所有顶点形成一个多边形
        if len(vertices) >= 3:
            faces = []
            for i in range(1, len(vertices) - 1):
                faces.append([0, i, i + 1])
            faces = np.array(faces, dtype=np.int32)
            
            return cls(
                id=id,
                vertices=vertices,
                faces=faces,
                surface_type='polygon',
                name=name
            )
        else:
            raise ValueError("Not enough vertices to create a surface")
    
    def get_bounds(self) -> np.ndarray:
        """获取边界框（2位小数）"""
        bounds = np.array([
            self.vertices[:, 0].min(), self.vertices[:, 0].max(),
            self.vertices[:, 1].min(), self.vertices[:, 1].max(),
            self.vertices[:, 2].min(), self.vertices[:, 2].max()
        ])
        return round_to_2_decimals(bounds)
    
    def get_area(self) -> float:
        """计算面的面积（仅适用于三角面，2位小数）"""
        if self.faces is None:
            return 0.0
        
        area = 0.0
        for face in self.faces:
            if len(face) == 3:  # 三角形
                v0, v1, v2 = self.vertices[face]
                area += 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0))
        return round_to_2_decimals(area)
    
    def get_center(self) -> np.ndarray:
        """获取面的中心点（2位小数）"""
        center = self.vertices.mean(axis=0)
        return round_to_2_decimals(center)
    
    def translate(self, vector: np.ndarray):
        """平移面"""
        vector = round_to_2_decimals(vector)
        self.vertices = round_to_2_decimals(self.vertices + np.array(vector))
    
    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            'id': self.id,
            'vertices': self.vertices.tolist(),
            'surface_type': self.surface_type,
            'name': self.name
        }
        if self.faces is not None:
            result['faces'] = self.faces.tolist()
        return result
    
    def copy(self) -> 'Surface':
        """复制面"""
        return Surface(
            id=self.id,
            vertices=self.vertices.copy(),
            faces=self.faces.copy() if self.faces is not None else None,
            surface_type=self.surface_type,
            name=self.name
        )
