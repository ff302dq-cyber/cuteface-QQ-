import random
import re
import logging
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import AstrBotConfig
import astrbot.api.message_components as Comp

logger = logging.getLogger("cute_face")

# QQ表情ID -> 表情名称 的完整映射表
FACE_NAME_MAP = {
    0: "惊讶", 1: "撇嘴", 2: "色", 3: "发呆", 4: "得意", 5: "流泪",
    6: "害羞", 7: "闭嘴", 8: "睡", 9: "大哭", 10: "尴尬", 11: "发怒",
    12: "调皮", 13: "呲牙", 14: "微笑", 15: "难过", 16: "酷", 18: "抓狂",
    19: "吐", 20: "偷笑", 21: "可爱", 22: "白眼", 23: "傲慢", 24: "饥饿",
    25: "困", 26: "惊恐", 27: "流汗", 28: "憨笑", 29: "悠闲", 30: "奋斗",
    31: "咒骂", 32: "疑问", 33: "嘘", 34: "晕", 35: "折磨", 36: "衰",
    37: "骷髅", 38: "敲打", 39: "再见", 41: "发抖", 42: "爱情", 43: "跳跳",
    46: "猪头", 49: "拥抱", 53: "蛋糕", 54: "闪电", 55: "炸弹", 56: "刀",
    59: "便便", 60: "咖啡", 63: "玫瑰", 64: "凋谢", 66: "爱心", 67: "心碎",
    69: "礼物", 74: "太阳", 75: "月亮", 76: "赞", 77: "踩", 78: "握手",
    79: "胜利", 85: "飞吻", 86: "怄火", 89: "西瓜", 96: "冷汗", 97: "擦汗",
    98: "抠鼻", 99: "鼓掌", 100: "糗大了", 101: "坏笑", 102: "左哼哼",
    103: "右哼哼", 104: "哈欠", 106: "委屈", 109: "左亲亲", 111: "可怜",
    116: "示爱", 118: "抱拳", 120: "拳头", 122: "爱你", 123: "NO", 124: "OK",
    125: "转圈", 129: "挥手", 144: "喝彩", 147: "棒棒糖", 171: "茶",
    173: "泪奔", 174: "无奈", 175: "卖萌", 176: "小纠结", 179: "doge",
    180: "惊喜", 181: "骚扰", 182: "笑哭", 183: "我最美", 201: "点赞",
    203: "托脸", 212: "托腮", 214: "啵啵", 219: "蹭一蹭", 222: "抱抱",
    227: "拍手", 232: "佛系", 240: "喷脸", 243: "甩头", 246: "加油抱抱",
    262: "脑阔疼", 264: "捂脸", 265: "辣眼睛", 266: "哦哟", 267: "头秃",
    268: "问号脸", 269: "暗中观察", 270: "emm", 271: "吃瓜", 272: "呵呵哒",
    273: "我酸了", 277: "汪汪", 278: "汗", 281: "无眼笑", 282: "敬礼",
    284: "面无表情", 285: "摸鱼", 287: "哦", 289: "睁眼", 290: "敲开心",
    293: "摸锦鲤", 294: "期待", 297: "拜谢", 298: "元宝", 299: "牛啊",
    305: "右亲亲", 306: "牛气冲天", 307: "喵喵", 314: "仔细分析", 315: "加油",
    318: "崇拜", 319: "比心", 320: "庆祝", 322: "拒绝", 324: "吃糖", 326: "生气",
}

JUDGE_PROMPT_TEMPLATE = """从下面的QQ表情池中，选出{num}个最匹配这条消息情感和语境的表情。

表情池：
{pool_desc}

消息内容：{text}

要求：只返回表情ID数字，用英文逗号分隔，不要任何其他内容。"""


@register("cute_face", "菌菌", "短消息自动追加匹配情感的QQ小表情", "1.1.0")
class CuteFace(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        self.emoji_pool: list = config.get("emoji_pool", [179])
        self.max_text_length: int = config.get("max_text_length", 35)
        self.probability: float = config.get("probability", 0.6)
        self.min_faces: int = config.get("min_faces", 1)
        self.max_faces: int = config.get("max_faces", 3)

        # 构建当前表情池的描述文本（供LLM理解每个表情的含义）
        self._pool_desc = self._build_pool_desc()

    def _build_pool_desc(self) -> str:
        """把表情池里的ID翻译成 'ID=名称' 的格式，方便LLM理解"""
        parts = []
        for fid in self.emoji_pool:
            fid = int(fid)
            name = FACE_NAME_MAP.get(fid, f"未知表情{fid}")
            parts.append(f"{fid}={name}")
        return ", ".join(parts)

    def _parse_face_ids(self, text: str) -> list[int]:
        """从LLM返回的文本中解析出表情ID列表"""
        pool_set = set(int(x) for x in self.emoji_pool)
        ids = []
        for num_str in re.findall(r"\d+", text):
            fid = int(num_str)
            if fid in pool_set:
                ids.append(fid)
        return ids

    @filter.on_decorating_result()
    async def append_cute_face(self, event: AstrMessageEvent):
        if not self.emoji_pool:
            return

        result = event.get_result()
        chain = result.chain
        if not chain:
            return

        # 检查消息链：只处理纯文本短消息
        text_parts = []
        for c in chain:
            if isinstance(c, Comp.Plain):
                text_parts.append(c.text.strip())
            elif isinstance(c, (Comp.Image, Comp.Record, Comp.Video)):
                return  # 含多媒体的消息不追加

        full_text = "".join(text_parts)
        if not full_text or len(full_text) > self.max_text_length:
            return

        # 概率判断
        if random.random() > self.probability:
            return

        # 决定这次追加几个表情
        num_faces = random.randint(self.min_faces, self.max_faces)

        try:
            # 获取当前会话的LLM provider
            umo = event.unified_msg_origin
            provider_id = await self.context.get_current_chat_provider_id(umo=umo)
            if not provider_id:
                # 没有配置LLM的话就回退到随机
                self._append_random(chain, num_faces)
                return

            # 构建判断prompt
            prompt = JUDGE_PROMPT_TEMPLATE.format(
                num=num_faces,
                pool_desc=self._pool_desc,
                text=full_text
            )

            # 调用LLM判断情感并选表情
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )

            face_ids = self._parse_face_ids(llm_resp.completion_text)

            if face_ids:
                for fid in face_ids[:num_faces]:
                    chain.append(Comp.Face(id=fid))
            else:
                self._append_random(chain, num_faces)

        except Exception as e:
            logger.warning(f"[cute_face] LLM判断表情失败，回退到随机: {e}")
            self._append_random(chain, num_faces)

    def _append_random(self, chain: list, num: int):
        """LLM不可用时的随机回退"""
        for _ in range(num):
            fid = random.choice(self.emoji_pool)
            chain.append(Comp.Face(id=int(fid)))
