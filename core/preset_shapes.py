"""
预设图形基类及具体实现
用于交互式建模可视化界面
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict
import numpy as np
from core.material_properties import MaterialProperties


def round_to_2_decimals(value):
    """将值四舍五入到2位小数"""
    if isinstance(value, (list, np.ndarray)):
        return np.round(value, 2)
    return round(float(value), 2)


class PresetShape(ABC):
    """预设图形基类"""
    
    def __init__(self, id: str, name: Optional[str] = None, 
                 properties: Optional[MaterialProperties] = None):
        self.id = id
        self.name = name
        self.properties = properties
    
    @abstractmethod
    def get_center(self) -> np.ndarray:
        """获取图形中心点（2位小数）"""
        pass
    
    @abstractmethod
    def get_bounds(self) -> np.ndarray:
        """获取边界框 [xmin, xmax, ymin, ymax, zmin, zmax]（2位小数）"""
        pass
    
    @abstractmethod
    def translate(self, vector: np.ndarray):
        """平移图形"""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict:
        """转换为字典"""
        pass
    
    @abstractmethod
    def get_mesh_data(self) -> Dict:
        """获取用于可视化的网格数据"""
        pass


class Sphere(PresetShape):
    """球体预设图形"""
    
    def __init__(self, id: str, center: np.ndarray, radius: float,
                 name: Optional[str] = None, 
                 properties: Optional[MaterialProperties] = None):
        super().__init__(id, name, properties)
        self.center = round_to_2_decimals(np.array(center))
        self.radius = round_to_2_decimals(radius)
    
    def get_center(self) -> np.ndarray:
        """获取中心点"""
        return self.center.copy()
    
    def get_bounds(self) -> np.ndarray:
        """获取边界框"""
        return np.array([
            round_to_2_decimals(self.center[0] - self.radius),
            round_to_2_decimals(self.center[0] + self.radius),
            round_to_2_decimals(self.center[1] - self.radius),
            round_to_2_decimals(self.center[1] + self.radius),
            round_to_2_decimals(self.center[2] - self.radius),
            round_to_2_decimals(self.center[2] + self.radius)
        ])
    
    def translate(self, vector: np.ndarray):
        """平移球体"""
        vector = round_to_2_decimals(vector)
        self.center = round_to_2_decimals(self.center + np.array(vector))
    
    def set_center(self, x: float, y: float, z: float):
        """设置中心"""
        self.center = round_to_2_decimals(np.array([x, y, z]))
    
    def set_radius(self, radius: float):
        """设置半径"""
        self.radius = round_to_2_decimals(radius)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': 'sphere',
            'center': [float(self.center[0]), float(self.center[1]), float(self.center[2])],
            'radius': float(self.radius),
            'name': self.name,
            'properties': self.properties.to_dict() if self.properties else None
        }
    
    def get_mesh_data(self) -> Dict:
        """获取网格数据"""
        return {
            'type': 'sphere',
            'center': self.center.tolist(),
            'radius': float(self.radius)
        }


class Box(PresetShape):
    """立方体/长方体预设图形"""
    
    def __init__(self, id: str, center: np.ndarray, extents: np.ndarray,
                 name: Optional[str] = None,
                 properties: Optional[MaterialProperties] = None):
        super().__init__(id, name, properties)
        self.center = round_to_2_decimals(np.array(center))
        self.extents = round_to_2_decimals(np.array(extents))
    
    def get_center(self) -> np.ndarray:
        """获取中心点"""
        return self.center.copy()
    
    def get_bounds(self) -> np.ndarray:
        """获取边界框"""
        half_extents = self.extents / 2.0
        return np.array([
            round_to_2_decimals(self.center[0] - half_extents[0]),
            round_to_2_decimals(self.center[0] + half_extents[0]),
            round_to_2_decimals(self.center[1] - half_extents[1]),
            round_to_2_decimals(self.center[1] + half_extents[1]),
            round_to_2_decimals(self.center[2] - half_extents[2]),
            round_to_2_decimals(self.center[2] + half_extents[2])
        ])
    
    def translate(self, vector: np.ndarray):
        """平移立方体"""
        vector = round_to_2_decimals(vector)
        self.center = round_to_2_decimals(self.center + np.array(vector))
    
    def set_center(self, x: float, y: float, z: float):
        """设置中心"""
        self.center = round_to_2_decimals(np.array([x, y, z]))
    
    def set_extents(self, dx: float, dy: float, dz: float):
        """设置尺寸"""
        self.extents = round_to_2_decimals(np.array([dx, dy, dz]))
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': 'box',
            'center': [float(self.center[0]), float(self.center[1]), float(self.center[2])],
            'extents': [float(self.extents[0]), float(self.extents[1]), float(self.extents[2])],
            'name': self.name,
            'properties': self.properties.to_dict() if self.properties else None
        }
    
    def get_mesh_data(self) -> Dict:
        """获取网格数据"""
        return {
            'type': 'box',
            'center': self.center.tolist(),
            'extents': self.extents.tolist()
        }


class Ellipsoid(PresetShape):
    """椭球体预设图形"""
    
    def __init__(self, id: str, center: np.ndarray, radii: np.ndarray,
                 name: Optional[str] = None,
                 properties: Optional[MaterialProperties] = None):
        super().__init__(id, name, properties)
        self.center = round_to_2_decimals(np.array(center))
        self.radii = round_to_2_decimals(np.array(radii))
    
    def get_center(self) -> np.ndarray:
        """获取中心点"""
        return self.center.copy()
    
    def get_bounds(self) -> np.ndarray:
        """获取边界框"""
        return np.array([
            round_to_2_decimals(self.center[0] - self.radii[0]),
            round_to_2_decimals(self.center[0] + self.radii[0]),
            round_to_2_decimals(self.center[1] - self.radii[1]),
            round_to_2_decimals(self.center[1] + self.radii[1]),
            round_to_2_decimals(self.center[2] - self.radii[2]),
            round_to_2_decimals(self.center[2] + self.radii[2])
        ])
    
    def translate(self, vector: np.ndarray):
        """平移椭球体"""
        vector = round_to_2_decimals(vector)
        self.center = round_to_2_decimals(self.center + np.array(vector))
    
    def set_center(self, x: float, y: float, z: float):
        """设置中心"""
        self.center = round_to_2_decimals(np.array([x, y, z]))
    
    def set_radii(self, rx: float, ry: float, rz: float):
        """设置半径"""
        self.radii = round_to_2_decimals(np.array([rx, ry, rz]))
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': 'ellipsoid',
            'center': [float(self.center[0]), float(self.center[1]), float(self.center[2])],
            'radii': [float(self.radii[0]), float(self.radii[1]), float(self.radii[2])],
            'name': self.name,
            'properties': self.properties.to_dict() if self.properties else None
        }
    
    def get_mesh_data(self) -> Dict:
        """获取网格数据"""
        return {
            'type': 'ellipsoid',
            'center': self.center.tolist(),
            'radii': self.radii.tolist()
        }


class Cylinder(PresetShape):
    """圆柱体预设图形"""
    
    def __init__(self, id: str, center: np.ndarray, radius: float, height: float,
                 name: Optional[str] = None,
                 properties: Optional[MaterialProperties] = None):
        super().__init__(id, name, properties)
        self.center = round_to_2_decimals(np.array(center))
        self.radius = round_to_2_decimals(radius)
        self.height = round_to_2_decimals(height)
    
    def get_center(self) -> np.ndarray:
        """获取中心点"""
        return self.center.copy()
    
    def get_bounds(self) -> np.ndarray:
        """获取边界框"""
        half_height = self.height / 2.0
        return np.array([
            round_to_2_decimals(self.center[0] - self.radius),
            round_to_2_decimals(self.center[0] + self.radius),
            round_to_2_decimals(self.center[1] - self.radius),
            round_to_2_decimals(self.center[1] + self.radius),
            round_to_2_decimals(self.center[2] - half_height),
            round_to_2_decimals(self.center[2] + half_height)
        ])
    
    def translate(self, vector: np.ndarray):
        """平移圆柱体"""
        vector = round_to_2_decimals(vector)
        self.center = round_to_2_decimals(self.center + np.array(vector))
    
    def set_center(self, x: float, y: float, z: float):
        """设置中心"""
        self.center = round_to_2_decimals(np.array([x, y, z]))
    
    def set_radius(self, radius: float):
        """设置半径"""
        self.radius = round_to_2_decimals(radius)
    
    def set_height(self, height: float):
        """设置高度"""
        self.height = round_to_2_decimals(height)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': 'cylinder',
            'center': [float(self.center[0]), float(self.center[1]), float(self.center[2])],
            'radius': float(self.radius),
            'height': float(self.height),
            'name': self.name,
            'properties': self.properties.to_dict() if self.properties else None
        }
    
    def get_mesh_data(self) -> Dict:
        """获取网格数据"""
        return {
            'type': 'cylinder',
            'center': self.center.tolist(),
            'radius': float(self.radius),
            'height': float(self.height)
        }
