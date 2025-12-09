"""
网格类 - 管理网格数据和属性
用于交互式建模可视化界面
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple, Union
import numpy as np
from scipy.spatial import cKDTree


def round_to_2_decimals(value):
    """将值四舍五入到2位小数"""
    if isinstance(value, (list, np.ndarray)):
        return np.round(value, 2)
    return round(float(value), 2)


class Mesh:
    """网格类 - 管理网格数据和属性"""
    
    def __init__(self, id: str, nodes: np.ndarray, elements: np.ndarray,
                 element_type: str = 'tetra', name: Optional[str] = None):
        """
        初始化网格
        
        Parameters:
        -----------
        id : str
            网格ID
        nodes : np.ndarray
            节点坐标 (Nx3)
        elements : np.ndarray
            单元节点索引 (MxK)，K取决于单元类型
        element_type : str
            单元类型 ('tetra', 'hexa', 'mixed')
        name : str, optional
            网格名称
        """
        self.id = id
        self.name = name
        
        # 处理节点数据（四舍五入到2位小数）
        if not isinstance(nodes, np.ndarray):
            nodes = np.array(nodes, dtype=np.float32)
        if len(nodes.shape) != 2 or nodes.shape[1] != 3:
            raise ValueError("Nodes must be Nx3 array")
        self.nodes = round_to_2_decimals(nodes)
        
        # 处理单元数据
        if not isinstance(elements, np.ndarray):
            elements = np.array(elements, dtype=np.int32)
        if len(elements.shape) != 2:
            raise ValueError("Elements must be 2D array")
        self.elements = elements
        
        # 确定单元类型
        num_nodes_per_element = elements.shape[1]
        if element_type == 'auto':
            if num_nodes_per_element == 4:
                self.element_type = 'tetra'
            elif num_nodes_per_element == 8:
                self.element_type = 'hexa'
            else:
                self.element_type = 'mixed'
        else:
            self.element_type = element_type
        
        # 验证单元索引
        max_node_idx = elements.max()
        if max_node_idx >= len(nodes):
            raise ValueError(f"Element index {max_node_idx} exceeds node count {len(nodes)}")
        
        # 属性数据
        self.cell_data: Dict[str, np.ndarray] = {}
        self.point_data: Dict[str, np.ndarray] = {}
        
        # 元数据
        self.metadata: Dict = {}
        
        # 缓存
        self._element_centers = None
        self._element_volumes = None
        self._bounds = None
        self._kd_tree = None
    
    @property
    def num_nodes(self) -> int:
        """节点数"""
        return len(self.nodes)
    
    @property
    def num_elements(self) -> int:
        """单元数"""
        return len(self.elements)
    
    def get_bounds(self) -> np.ndarray:
        """获取边界框 [xmin, xmax, ymin, ymax, zmin, zmax]（2位小数）"""
        if self._bounds is None:
            self._bounds = round_to_2_decimals(np.array([
                self.nodes[:, 0].min(), self.nodes[:, 0].max(),
                self.nodes[:, 1].min(), self.nodes[:, 1].max(),
                self.nodes[:, 2].min(), self.nodes[:, 2].max()
            ]))
        return self._bounds.copy()
    
    def get_element_centers(self) -> np.ndarray:
        """获取所有单元中心点（2位小数）"""
        if self._element_centers is None:
            centers = []
            for elem in self.elements:
                center = self.nodes[elem].mean(axis=0)
                centers.append(center)
            self._element_centers = round_to_2_decimals(np.array(centers))
        return self._element_centers.copy()
    
    def get_element_volumes(self) -> np.ndarray:
        """计算所有单元体积（2位小数）"""
        if self._element_volumes is None:
            volumes = []
            for elem in self.elements:
                if self.element_type == 'tetra':
                    # 四面体体积
                    v0, v1, v2, v3 = self.nodes[elem]
                    volume = abs(np.dot(v1 - v0, np.cross(v2 - v0, v3 - v0))) / 6.0
                elif self.element_type == 'hexa':
                    # 六面体体积（简化为8个四面体）
                    # 使用第一个顶点作为公共顶点
                    v0 = self.nodes[elem[0]]
                    volume = 0.0
                    # 分解为6个四面体
                    for i in range(1, 7):
                        v1 = self.nodes[elem[i]]
                        v2 = self.nodes[elem[i+1] if i < 6 else elem[1]]
                        v3 = self.nodes[elem[7]]
                        volume += abs(np.dot(v1 - v0, np.cross(v2 - v0, v3 - v0))) / 6.0
                else:
                    # 其他类型，使用边界框体积近似
                    elem_nodes = self.nodes[elem]
                    bounds = np.array([
                        elem_nodes[:, 0].max() - elem_nodes[:, 0].min(),
                        elem_nodes[:, 1].max() - elem_nodes[:, 1].min(),
                        elem_nodes[:, 2].max() - elem_nodes[:, 2].min()
                    ])
                    volume = np.prod(bounds)
                volumes.append(volume)
            self._element_volumes = round_to_2_decimals(np.array(volumes))
        return self._element_volumes.copy()
    
    def get_total_volume(self) -> float:
        """获取网格总体积（2位小数）"""
        volumes = self.get_element_volumes()
        return round_to_2_decimals(volumes.sum())
    
    # ========== 属性管理 ==========
    
    def set_cell_data(self, name: str, data: np.ndarray):
        """
        设置单元属性
        
        Parameters:
        -----------
        name : str
            属性名称
        data : np.ndarray
            属性数据，长度必须等于单元数
        """
        if len(data) != self.num_elements:
            raise ValueError(f"Cell data length {len(data)} must match element count {self.num_elements}")
        self.cell_data[name] = np.array(data)
        # 清除相关缓存
        self._element_centers = None
        self._element_volumes = None
    
    def set_point_data(self, name: str, data: np.ndarray):
        """
        设置节点属性
        
        Parameters:
        -----------
        name : str
            属性名称
        data : np.ndarray
            属性数据，长度必须等于节点数
        """
        if len(data) != self.num_nodes:
            raise ValueError(f"Point data length {len(data)} must match node count {self.num_nodes}")
        self.point_data[name] = np.array(data)
    
    def get_cell_data(self, name: str) -> Optional[np.ndarray]:
        """获取单元属性"""
        return self.cell_data.get(name)
    
    def get_point_data(self, name: str) -> Optional[np.ndarray]:
        """获取节点属性"""
        return self.point_data.get(name)
    
    def remove_cell_data(self, name: str):
        """删除单元属性"""
        if name in self.cell_data:
            del self.cell_data[name]
    
    def remove_point_data(self, name: str):
        """删除节点属性"""
        if name in self.point_data:
            del self.point_data[name]
    
    def has_cell_data(self, name: str) -> bool:
        """检查是否有单元属性"""
        return name in self.cell_data
    
    def has_point_data(self, name: str) -> bool:
        """检查是否有节点属性"""
        return name in self.point_data
    
    # ========== 网格质量 ==========
    
    def check_quality(self) -> Dict:
        """
        检查网格质量
        
        Returns:
        --------
        Dict
            质量报告，包含长宽比、体积等信息
        """
        volumes = self.get_element_volumes()
        
        # 检查负体积
        negative_volumes = np.where(volumes < 0)[0]
        
        # 计算长宽比（仅对四面体）
        aspect_ratios = None
        if self.element_type == 'tetra':
            aspect_ratios = []
            for elem in self.elements:
                elem_nodes = self.nodes[elem]
                # 计算6条边
                edges = []
                for i in range(4):
                    for j in range(i+1, 4):
                        edge_length = np.linalg.norm(elem_nodes[i] - elem_nodes[j])
                        edges.append(edge_length)
                edges = np.array(edges)
                if edges.min() > 0:
                    aspect_ratio = edges.max() / edges.min()
                    aspect_ratios.append(aspect_ratio)
                else:
                    aspect_ratios.append(float('inf'))
            aspect_ratios = np.array(aspect_ratios)
        
        return {
            'num_elements': self.num_elements,
            'num_nodes': self.num_nodes,
            'total_volume': float(self.get_total_volume()),
            'volume_stats': {
                'min': float(volumes.min()),
                'max': float(volumes.max()),
                'mean': float(volumes.mean()),
                'std': float(volumes.std())
            },
            'negative_volumes': len(negative_volumes),
            'negative_volume_indices': negative_volumes.tolist() if len(negative_volumes) > 0 else [],
            'aspect_ratio': {
                'min': float(aspect_ratios.min()) if aspect_ratios is not None else None,
                'max': float(aspect_ratios.max()) if aspect_ratios is not None else None,
                'mean': float(aspect_ratios.mean()) if aspect_ratios is not None else None
            } if aspect_ratios is not None else None
        }
    
    def get_quality_report(self) -> str:
        """生成质量报告字符串"""
        quality = self.check_quality()
        report = f"网格质量报告 - {self.name or self.id}\n"
        report += "=" * 60 + "\n"
        report += f"节点数: {quality['num_nodes']}\n"
        report += f"单元数: {quality['num_elements']}\n"
        report += f"总体积: {quality['total_volume']:.2f}\n"
        report += f"\n体积统计:\n"
        report += f"  最小: {quality['volume_stats']['min']:.2f}\n"
        report += f"  最大: {quality['volume_stats']['max']:.2f}\n"
        report += f"  平均: {quality['volume_stats']['mean']:.2f}\n"
        report += f"  标准差: {quality['volume_stats']['std']:.2f}\n"
        if quality['negative_volumes'] > 0:
            report += f"\n警告: 发现 {quality['negative_volumes']} 个负体积单元\n"
        if quality['aspect_ratio'] is not None:
            report += f"\n长宽比统计:\n"
            report += f"  最小: {quality['aspect_ratio']['min']:.2f}\n"
            report += f"  最大: {quality['aspect_ratio']['max']:.2f}\n"
            report += f"  平均: {quality['aspect_ratio']['mean']:.2f}\n"
        return report
    
    def find_bad_elements(self, min_volume: float = 0.0, 
                         max_aspect_ratio: float = float('inf')) -> np.ndarray:
        """
        查找低质量单元
        
        Parameters:
        -----------
        min_volume : float
            最小体积阈值
        max_aspect_ratio : float
            最大长宽比阈值
            
        Returns:
        --------
        np.ndarray
            低质量单元的索引
        """
        volumes = self.get_element_volumes()
        bad_indices = np.where(volumes < min_volume)[0]
        
        if self.element_type == 'tetra' and max_aspect_ratio < float('inf'):
            aspect_ratios = []
            for elem in self.elements:
                elem_nodes = self.nodes[elem]
                edges = []
                for i in range(4):
                    for j in range(i+1, 4):
                        edge_length = np.linalg.norm(elem_nodes[i] - elem_nodes[j])
                        edges.append(edge_length)
                edges = np.array(edges)
                if edges.min() > 0:
                    aspect_ratio = edges.max() / edges.min()
                    aspect_ratios.append(aspect_ratio)
                else:
                    aspect_ratios.append(float('inf'))
            aspect_ratios = np.array(aspect_ratios)
            bad_aspect = np.where(aspect_ratios > max_aspect_ratio)[0]
            bad_indices = np.unique(np.concatenate([bad_indices, bad_aspect]))
        
        return bad_indices
    
    # ========== 网格操作 ==========
    
    def translate(self, vector: np.ndarray):
        """
        平移网格
        
        Parameters:
        -----------
        vector : np.ndarray
            平移向量 [dx, dy, dz]
        """
        vector = round_to_2_decimals(vector)
        self.nodes = round_to_2_decimals(self.nodes + np.array(vector))
        # 清除缓存
        self._element_centers = None
        self._bounds = None
        self._kd_tree = None
    
    def scale(self, factor: Union[float, np.ndarray]):
        """
        缩放网格
        
        Parameters:
        -----------
        factor : float or np.ndarray
            缩放因子（单个值或[x, y, z]）
        """
        if isinstance(factor, (int, float)):
            factor = np.array([factor, factor, factor])
        factor = round_to_2_decimals(factor)
        
        # 获取中心点
        center = self.get_bounds().reshape(3, 2).mean(axis=1)
        
        # 缩放
        self.nodes = round_to_2_decimals((self.nodes - center) * factor + center)
        
        # 清除缓存
        self._element_centers = None
        self._element_volumes = None
        self._bounds = None
        self._kd_tree = None
    
    # ========== 查询功能 ==========
    
    def find_elements_in_region(self, bounds: np.ndarray) -> np.ndarray:
        """
        查找区域内的单元
        
        Parameters:
        -----------
        bounds : np.ndarray
            区域边界 [xmin, xmax, ymin, ymax, zmin, zmax]
            
        Returns:
        --------
        np.ndarray
            单元索引
        """
        centers = self.get_element_centers()
        mask = ((centers[:, 0] >= bounds[0]) & (centers[:, 0] <= bounds[1]) &
                (centers[:, 1] >= bounds[2]) & (centers[:, 1] <= bounds[3]) &
                (centers[:, 2] >= bounds[4]) & (centers[:, 2] <= bounds[5]))
        return np.where(mask)[0]
    
    def find_nodes_in_region(self, bounds: np.ndarray) -> np.ndarray:
        """
        查找区域内的节点
        
        Parameters:
        -----------
        bounds : np.ndarray
            区域边界 [xmin, xmax, ymin, ymax, zmin, zmax]
            
        Returns:
        --------
        np.ndarray
            节点索引
        """
        mask = ((self.nodes[:, 0] >= bounds[0]) & (self.nodes[:, 0] <= bounds[1]) &
                (self.nodes[:, 1] >= bounds[2]) & (self.nodes[:, 1] <= bounds[3]) &
                (self.nodes[:, 2] >= bounds[4]) & (self.nodes[:, 2] <= bounds[5]))
        return np.where(mask)[0]
    
    def find_nearest_node(self, point: np.ndarray) -> int:
        """
        查找最近的节点
        
        Parameters:
        -----------
        point : np.ndarray
            查询点 [x, y, z]
            
        Returns:
        --------
        int
            最近节点的索引
        """
        if self._kd_tree is None:
            self._kd_tree = cKDTree(self.nodes)
        distance, index = self._kd_tree.query(point)
        return int(index)
    
    def get_element_by_index(self, index: int) -> np.ndarray:
        """根据索引获取单元"""
        if index < 0 or index >= self.num_elements:
            raise IndexError(f"Element index {index} out of range")
        return self.elements[index].copy()
    
    def get_node_by_index(self, index: int) -> np.ndarray:
        """根据索引获取节点"""
        if index < 0 or index >= self.num_nodes:
            raise IndexError(f"Node index {index} out of range")
        return self.nodes[index].copy()
    
    # ========== 统计信息 ==========
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        volumes = self.get_element_volumes()
        bounds = self.get_bounds()
        
        return {
            'id': self.id,
            'name': self.name,
            'element_type': self.element_type,
            'num_nodes': self.num_nodes,
            'num_elements': self.num_elements,
            'bounds': bounds.tolist(),
            'total_volume': float(self.get_total_volume()),
            'volume_stats': {
                'min': float(volumes.min()),
                'max': float(volumes.max()),
                'mean': float(volumes.mean()),
                'std': float(volumes.std())
            },
            'cell_data_fields': list(self.cell_data.keys()),
            'point_data_fields': list(self.point_data.keys())
        }
    
    def get_property_statistics(self, property_name: str, 
                               data_type: str = 'cell') -> Dict:
        """
        获取属性统计
        
        Parameters:
        -----------
        property_name : str
            属性名称
        data_type : str
            数据类型 ('cell' or 'point')
            
        Returns:
        --------
        Dict
            统计信息
        """
        if data_type == 'cell':
            data = self.get_cell_data(property_name)
            if data is None:
                raise ValueError(f"Cell data '{property_name}' not found")
        else:
            data = self.get_point_data(property_name)
            if data is None:
                raise ValueError(f"Point data '{property_name}' not found")
        
        return {
            'name': property_name,
            'type': data_type,
            'min': float(data.min()),
            'max': float(data.max()),
            'mean': float(data.mean()),
            'std': float(data.std()),
            'median': float(np.median(data))
        }
    
    # ========== 数据转换 ==========
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            'id': self.id,
            'name': self.name,
            'element_type': self.element_type,
            'nodes': self.nodes.tolist(),
            'elements': self.elements.tolist(),
            'cell_data': {k: v.tolist() for k, v in self.cell_data.items()},
            'point_data': {k: v.tolist() for k, v in self.point_data.items()},
            'metadata': self.metadata
        }
        return result
    
    def to_meshio(self):
        """转换为meshio格式"""
        import meshio
        
        # 确定单元类型
        if self.element_type == 'tetra':
            cell_type = "tetra"
        elif self.element_type == 'hexa':
            cell_type = "hexahedron"
        else:
            raise ValueError(f"Unsupported element type: {self.element_type}")
        
        cells = [(cell_type, self.elements)]
        
        # 格式化cell_data
        formatted_cell_data = {}
        for key, value in self.cell_data.items():
            formatted_cell_data[key] = [value]
        
        return meshio.Mesh(
            points=self.nodes,
            cells=cells,
            cell_data=formatted_cell_data if formatted_cell_data else None,
            point_data=self.point_data if self.point_data else None
        )
    
    def to_pyvista(self):
        """转换为PyVista格式"""
        import pyvista as pv
        
        if self.element_type == 'tetra':
            cell_type = pv.CellType.TETRA
        elif self.element_type == 'hexa':
            cell_type = pv.CellType.HEXAHEDRON
        else:
            raise ValueError(f"Unsupported element type: {self.element_type}")
        
        grid = pv.UnstructuredGrid(
            {cell_type: self.elements},
            self.nodes
        )
        
        # 添加属性数据
        for key, value in self.cell_data.items():
            grid.cell_data[key] = value
        
        for key, value in self.point_data.items():
            grid.point_data[key] = value
        
        return grid
    
    def copy(self) -> 'Mesh':
        """复制网格"""
        new_mesh = Mesh(
            id=f"{self.id}_copy",
            nodes=self.nodes.copy(),
            elements=self.elements.copy(),
            element_type=self.element_type,
            name=self.name
        )
        
        # 复制属性数据
        for key, value in self.cell_data.items():
            new_mesh.cell_data[key] = value.copy()
        
        for key, value in self.point_data.items():
            new_mesh.point_data[key] = value.copy()
        
        # 复制元数据
        new_mesh.metadata = self.metadata.copy()
        
        return new_mesh
    
    # ========== 类方法（工厂方法） ==========
    
    @classmethod
    def from_nodes_elements(cls, id: str, nodes: np.ndarray, elements: np.ndarray,
                           element_type: str = 'auto', name: Optional[str] = None) -> 'Mesh':
        """
        从节点和单元创建网格
        
        Parameters:
        -----------
        id : str
            网格ID
        nodes : np.ndarray
            节点坐标 (Nx3)
        elements : np.ndarray
            单元节点索引 (MxK)
        element_type : str
            单元类型 ('tetra', 'hexa', 'auto')
        name : str, optional
            网格名称
            
        Returns:
        --------
        Mesh
            网格对象
        """
        return cls(id, nodes, elements, element_type, name)
    
    @classmethod
    def from_gmsh(cls, id: str, nodes: np.ndarray, elements: np.ndarray,
                  name: Optional[str] = None) -> 'Mesh':
        """
        从Gmsh生成结果创建网格
        
        Parameters:
        -----------
        id : str
            网格ID
        nodes : np.ndarray
            节点坐标
        elements : np.ndarray
            单元节点索引
        name : str, optional
            网格名称
            
        Returns:
        --------
        Mesh
            网格对象
        """
        return cls(id, nodes, elements, element_type='auto', name=name)
    
    @classmethod
    def from_file(cls, filename: str, id: Optional[str] = None) -> 'Mesh':
        """
        从文件加载网格
        
        Parameters:
        -----------
        filename : str
            文件路径
        id : str, optional
            网格ID，如果为None则使用文件名
            
        Returns:
        --------
        Mesh
            网格对象
        """
        import meshio
        
        mesh_data = meshio.read(filename)
        
        # 确定单元类型
        if len(mesh_data.cells) == 0:
            raise ValueError("No cells found in mesh file")
        
        cell_type, cell_data = mesh_data.cells[0]
        element_type = 'tetra' if cell_type == 'tetra' else 'hexa' if cell_type == 'hexahedron' else 'mixed'
        
        if id is None:
            import os
            id = os.path.splitext(os.path.basename(filename))[0]
        
        mesh = cls(
            id=id,
            nodes=mesh_data.points,
            elements=cell_data,
            element_type=element_type,
            name=id
        )
        
        # 加载属性数据
        if mesh_data.cell_data:
            for key, value_list in mesh_data.cell_data.items():
                if len(value_list) > 0:
                    mesh.cell_data[key] = value_list[0]
        
        if mesh_data.point_data:
            for key, value in mesh_data.point_data.items():
                mesh.point_data[key] = value
        
        return mesh

