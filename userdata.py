from datetime import timedelta
import datetime

class UserData:
    def __init__(self):
        self.checkin_count = 0  # 出勤次数
        self.total_checkin_time = timedelta()  # 总出勤时间
        self.total_checkin_days = 0  # 总出勤天数
        self.checkin_dates = set()  # 已出勤日期

    def add_checkin(self, duration: timedelta, date: datetime.date):
        self.checkin_count += 1
        self.total_checkin_time += duration
        if date not in self.checkin_dates:
            self.total_checkin_days += 1
            self.checkin_dates.add(date)

    def to_dict(self) -> dict:
        """将用户数据转换为可写入 JSON 的格式。"""
        return {
            "checkin_count": self.checkin_count,
            "total_checkin_seconds": self.total_checkin_time.total_seconds(),
            "total_checkin_days": self.total_checkin_days,
            "checkin_dates": sorted(day.isoformat() for day in self.checkin_dates),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserData":
        """从 JSON 中恢复用户数据。"""
        user_data = cls()
        user_data.checkin_count = int(data.get("checkin_count", 0))
        user_data.total_checkin_time = timedelta(
            seconds=float(data.get("total_checkin_seconds", 0))
        )
        user_data.total_checkin_days = int(data.get("total_checkin_days", 0))
        # 兼容旧版 data.json：旧版以 daily_rating 的日期键记录出勤天数。
        checkin_dates = data.get("checkin_dates", data.get("daily_rating", {}).keys())
        user_data.checkin_dates = {
            datetime.date.fromisoformat(day) for day in checkin_dates
        }
        return user_data
