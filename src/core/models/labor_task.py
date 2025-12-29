"""Labor task model.

Represents a task claimed from the Labor platform.
"""

from dataclasses import dataclass
from enum import IntEnum


class TaskState(IntEnum):
    """任务状态枚举。"""
    NO_TASK = 0       # 无任务信息
    COMPLETE = 1      # 任务信息完整
    MISSING_ID = 2    # 缺少酒店ID


@dataclass
class LaborTask:
    """劳保平台任务数据模型。
    
    Attributes:
        hotel_name: 酒店名称
        hotel_id: 酒店ID（可能为空）
        checkin: 入住日期 (格式: YYYY-MM-DD)
        checkout: 离店日期 (格式: YYYY-MM-DD)
        city_name: 城市名称
        hotel_url: 携程酒店URL（可选）
        state: 任务状态 (0=无任务, 1=完整, 2=缺少酒店ID)
    """
    hotel_name: str = ""
    hotel_id: str | None = None
    checkin: str = ""
    checkout: str = ""
    city_name: str = ""
    hotel_url: str | None = None
    state: TaskState = TaskState.NO_TASK
    
    @property
    def is_complete(self) -> bool:
        """检查任务信息是否完整。"""
        return self.state == TaskState.COMPLETE
    
    @property
    def is_empty(self) -> bool:
        """检查是否无任务。"""
        return self.state == TaskState.NO_TASK
    
    def build_ctrip_url(self) -> str:
        """构建携程酒店详情页URL。
        
        Returns:
            携程酒店详情页完整URL
        """
        if self.hotel_url:
            # 如果已有URL，添加日期参数
            separator = "&" if "?" in self.hotel_url else "?"
            return f"{self.hotel_url}{separator}checkIn={self.checkin}&checkOut={self.checkout}"
        
        if self.hotel_id:
            base_url = f"https://hotels.ctrip.com/hotels/{self.hotel_id}.html"
            return f"{base_url}?checkIn={self.checkin}&checkOut={self.checkout}"
        
        return ""
    
    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "hotel_name": self.hotel_name,
            "hotel_id": self.hotel_id,
            "checkin": self.checkin,
            "checkout": self.checkout,
            "city_name": self.city_name,
            "hotel_url": self.hotel_url,
            "state": self.state.value if isinstance(self.state, TaskState) else self.state,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LaborTask":
        """从字典创建实例。"""
        state = data.get("state", 0)
        if isinstance(state, int):
            state = TaskState(state)
        
        return cls(
            hotel_name=data.get("hotel_name", ""),
            hotel_id=data.get("hotel_id"),
            checkin=data.get("checkin", ""),
            checkout=data.get("checkout", ""),
            city_name=data.get("city_name", ""),
            hotel_url=data.get("hotel_url"),
            state=state,
        )
    
    def __str__(self) -> str:
        return f"LaborTask({self.hotel_name}, {self.checkin}~{self.checkout}, state={self.state.name})"
