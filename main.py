from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from datetime import date, datetime, time as datetime_time, timedelta
import json
import os
from pathlib import Path
from .userdata import UserData

@register("astrbot_plugin_cardreader_kenk", "KENKshachu0", "AstrBot 插件示例。", "v1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_file = Path(__file__).parent / "data.json"
        self.user_checkin_data = {}
        self.user_data = {}
        self.user_backup_data = {}
        self._load_data()

    def _load_data(self):
        """从磁盘恢复用户数据和进行中的签到。"""
        if not self.data_file.exists():
            return

        try:
            with self.data_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
            self.user_data = {
                str(user_id): UserData.from_dict(user_data)
                for user_id, user_data in data.get("user_data", {}).items()
            }
            self.user_backup_data = {
                str(user_id): UserData.from_dict(user_data)
                for user_id, user_data in data.get("user_backup_data", {}).items()
            }
            self.user_checkin_data = {
                str(user_id): {
                    "date": date.fromisoformat(checkin["date"]),
                    "time": datetime_time.fromisoformat(checkin["time"]),
                }
                for user_id, checkin in data.get("user_checkin_data", {}).items()
            }
            logger.info("已从磁盘恢复 %s 位用户的数据", len(self.user_data))
        except (OSError, ValueError, TypeError, KeyError) as error:
            logger.warning("读取插件数据失败，将使用空数据：%s", error)
            self.user_checkin_data = {}
            self.user_data = {}
            self.user_backup_data = {}

    def _save_data(self):
        """原子写入数据，避免进程中断时留下半个 JSON 文件。"""
        data = {
            "user_checkin_data": {
                user_id: {
                    "date": checkin["date"].isoformat(),
                    "time": checkin["time"].isoformat(),
                }
                for user_id, checkin in self.user_checkin_data.items()
            },
            "user_data": {
                user_id: user_data.to_dict()
                for user_id, user_data in self.user_data.items()
            },
            "user_backup_data": {
                user_id: user_data.to_dict()
                for user_id, user_data in self.user_backup_data.items()
            },
        }
        temp_file = self.data_file.with_suffix(".tmp")
        try:
            with temp_file.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            os.replace(temp_file, self.data_file)
        except OSError as error:
            logger.error("保存插件数据失败：%s", error)

    @filter.command_group("mai")
    def mai(self):
        pass

    @mai.command("in")
    async def mai_in(self, event: AstrMessageEvent, time_str: str = None):
        user_id = str(event.get_sender_id())  # 获取用户ID
        if user_id in self.user_checkin_data:
            yield event.plain_result("你已经签到过了，请先退勤再签到")
            return

        if time_str:
            try:
                time_str = time_str.replace('：', ':')  # 将全角冒号替换为半角冒号
                time = datetime.strptime(time_str, "%H:%M").time()  # 解析时间参数
                date = datetime.now().date()  # 使用当前日期
            except ValueError:
                yield event.plain_result("时间格式错误，请使用 HH:MM 格式")
                return
        else:
            current_time = datetime.now()  # 获取当前时间
            date = current_time.date()  # 获取日期
            time = current_time.time()  # 获取时间
        self.user_checkin_data[user_id] = {"date": date, "time": time}  # 存储用户的签到信息
        if user_id not in self.user_data:
            self.user_data[user_id] = UserData()  # 初始化用户数据
        self._save_data()
        logger.info(f"用户 {user_id} 签到日期: {date}, 签到时间: {time}")  # 记录日志
        yield event.plain_result("舞萌，启动！")

    @mai.command("out")
    async def mai_out(self, event: AstrMessageEvent, time_str: str = None):
        user_id = str(event.get_sender_id())
        if user_id in self.user_checkin_data:
            if time_str:
                try:
                    time_str = time_str.replace('：', ':')  # 将全角冒号替换为半角冒号
                    out_time = datetime.strptime(time_str, "%H:%M").time()  # 解析时间参数
                    out_date = datetime.now().date()  # 使用当前日期
                except ValueError:
                    yield event.plain_result("时间格式错误，请使用 HH:MM 格式")
                    return
            else:
                checkin_data = self.user_checkin_data[user_id]
                out_date = checkin_data["date"]
                out_time = datetime.now().time()  # 使用当前时间作为退勤时间

            checkin_data = self.user_checkin_data[user_id]
            in_datetime = datetime.combine(checkin_data["date"], checkin_data["time"])
            out_datetime = datetime.combine(out_date, out_time)
            duration = out_datetime - in_datetime

            if duration < timedelta(0):
                yield event.plain_result("反方向的出勤？（出勤时间不能为负数）")
                return

            if out_datetime > datetime.now():
                yield event.plain_result("真的退勤了吗？（退勤时间不得晚于当前时间）")
                return

            if duration > timedelta(hours=12):
                yield event.plain_result("勤12小时？超人来的？")

            self.user_data[user_id].add_checkin(duration, out_date)  # 更新用户数据
            logger.info(f"用户 {user_id} 签到日期: {checkin_data['date']}, 签到时间: {checkin_data['time']}")
            logger.info(f"用户 {user_id} 退勤日期: {out_date}, 退勤时间: {out_time}")
            yield event.plain_result(f"退勤成功，你今天勤了 {duration} 小时哦！")
            del self.user_checkin_data[user_id]  # 移除用户的签到信息
            self._save_data()
        else:
            yield event.plain_result("没出勤就退勤？")

    @mai.command("day")
    async def mai_day(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        if user_id in self.user_data:
            yield event.plain_result(f"你的总出勤天数是 {self.user_data[user_id].total_checkin_days}")
        else:
            yield event.plain_result("懒比")

    @mai.command("time")
    async def mai_time(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        if user_id in self.user_data:
            yield event.plain_result(f"你的总出勤时间是 {self.user_data[user_id].total_checkin_time}")
        else:
            yield event.plain_result("懒比")

    @mai.command("reset")
    async def mai_reset(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        if user_id in self.user_data:
            self.user_backup_data[user_id] = self.user_data[user_id]  # 备份用户数据
            self.user_data[user_id] = UserData()  # 重置用户数据
            self._save_data()
            yield event.plain_result("你的数据已重置")
        else:
            yield event.plain_result("没有找到你的数据")

    @mai.command("unreset")
    async def mai_unreset(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        if user_id in self.user_backup_data:
            self.user_data[user_id] = self.user_backup_data.pop(user_id)  # 恢复备份数据
            self._save_data()
            yield event.plain_result("你的数据已恢复")
        else:
            yield event.plain_result("没有找到你的备份数据")

    @mai.command("help")
    async def mai_help(self, event: AstrMessageEvent):
        yield event.plain_result("/mai help（获取帮助）\n"
                                  "/mai in(出勤签到)\n"
                                  "/mai out（退勤签到）\n"
                                  "/mai day（获取出勤天数）\n"
                                  "/mai time（获取出勤时间）\n"
                                  "/mai reset（重置数据）\n"
                                  "/mai unreset（恢复数据）")
