"""
物性参数类
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MaterialProperties:
    """物性参数"""
    density: Optional[float] = None          # 密度 (kg/m³)
    velocity_p: Optional[float] = None       # P波速度 (m/s)
    velocity_s: Optional[float] = None       # S波速度 (m/s)
    resistivity: Optional[float] = None      # 电阻率 (Ω·m)
    porosity: Optional[float] = None          # 孔隙度
    permeability: Optional[float] = None     # 渗透率
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'density': self.density,
            'velocity_p': self.velocity_p,
            'velocity_s': self.velocity_s,
            'resistivity': self.resistivity,
            'porosity': self.porosity,
            'permeability': self.permeability
        }

