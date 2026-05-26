import random
import re
import logging
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import AstrBotConfig
import astrbot.api.message_components as Comp

logger = logging.getLogger("cute_face")

# QQ表情ID -> 表情名称 完整映射表（203条，来源 QFace 官方数据）
FACE_NAME_MAP = {
    0: "惊讶", 1: "撇嘴", 2: "色", 3: "发呆", 4: "得意", 5: "流泪",
    6: "害羞", 7: "闭嘴", 8: "睡", 9: "大哭", 10: "尴尬", 11: "发怒",
    12: "调皮", 13: "呲牙", 14: "微笑", 15: "难过", 16: "酷", 18: "抓狂",
    19: "吐", 20: "偷笑", 21: "可爱", 22: "白眼", 23: "傲慢", 24: "饥饿",
    25: "困", 26: "惊恐", 27: "流汗", 28: "憨笑", 29: "悠闲", 30: "奋斗",
    31: "咒骂", 32: "疑问", 33: "嘘", 34: "晕", 35: "折磨", 36: "衰",
    37: "骷髅", 38: "敲打", 39: "再见", 41: "发抖", 42: "爱情", 43: "跳跳",
    46: "猪头", 49: "拥抱", 53: "蛋糕", 54: "闪电", 55: "炸弹", 56: "刀",
    57: "足球", 59: "便便", 60: "咖啡", 63: "玫瑰", 64: "凋谢", 66: "爱心",
    67: "心碎", 69: "礼物", 74: "太阳", 75: "月亮", 76: "赞", 77: "踩",
    78: "握手", 79: "胜利", 85: "飞吻", 86: "怄火", 89: "西瓜", 96: "冷汗",
    97: "擦汗", 98: "抠鼻", 99: "鼓掌", 100: "糗大了", 101: "坏笑",
    102: "左哼哼", 103: "右哼哼", 104: "哈欠", 105: "鄙视", 106: "委屈",
    107: "快哭了", 108: "阴险", 109: "左亲亲", 110: "吓", 111: "可怜",
    112: "菜刀", 114: "篮球", 116: "示爱", 118: "抱拳", 119: "勾引",
    120: "拳头", 121: "差劲", 122: "爱你", 123: "NO", 124: "OK",
    125: "转圈", 129: "挥手", 137: "鞭炮", 144: "喝彩", 146: "爆筋",
    147: "棒棒糖", 148: "喝奶", 169: "手枪", 171: "茶", 172: "眨眼睛",
    173: "泪奔", 174: "无奈", 175: "卖萌", 176: "小纠结", 177: "喷血",
    178: "斜眼笑", 179: "doge", 180: "惊喜", 181: "戳一戳", 182: "笑哭",
    183: "我最美", 185: "羊驼", 187: "幽灵", 193: "大笑", 194: "不开心",
    198: "呃", 200: "求求", 201: "点赞", 202: "无聊", 203: "托脸",
    204: "吃", 206: "害怕", 210: "飙泪", 211: "我不看", 212: "托腮",
    214: "啵啵", 215: "糊脸", 216: "拍头", 217: "扯一扯", 218: "舔一舔",
    219: "蹭一蹭", 221: "顶呱呱", 222: "抱抱", 223: "暴击", 224: "开枪",
    225: "撩一撩", 227: "拍手", 232: "佛系", 240: "喷脸", 243: "甩头",
    246: "加油抱抱", 262: "脑阔疼", 264: "捂脸", 265: "辣眼睛", 266: "哦哟",
    267: "头秃", 268: "问号脸", 269: "暗中观察", 270: "emm", 271: "吃瓜",
    272: "呵呵哒", 273: "我酸了", 277: "汪汪", 278: "汗", 281: "无眼笑",
    282: "敬礼", 284: "面无表情", 285: "摸鱼", 287: "哦", 289: "睁眼",
    290: "敲开心", 293: "摸锦鲤", 294: "期待", 297: "拜谢", 298: "元宝",
    299: "牛啊", 305: "右亲亲", 306: "牛气冲天", 307: "喵喵",
    312: "拿到红包", 314: "仔细分析", 315: "加油", 317: "拜托",
    318: "崇拜", 319: "比心", 320: "庆祝", 322: "拒绝", 324: "吃糖",
    326: "生气", 332: "惊吓", 334: "哈哈哈", 336: "打call", 337: "变形",
    338: "嗑到了", 341: "我没事", 342: "菜狗", 344: "花朵脸",
    345: "我想开了", 346: "舔屏", 347: "热化了", 348: "打招呼",
    349: "你真棒棒", 350: "酸Q", 351: "我方了", 352: "大怨种",
    353: "红包多多", 354: "你真棒", 355: "大展宏兔",
}

JUDGE_PROMPT_TEMPLATE = """从下面的QQ表情池中，选出{num}个最匹配这条消息情感和语境的表情。

表情池：
{pool_desc}

消息内容：{text}

要求：只返回表情ID数字，用英文逗号分隔，不要任何其他内容。"""


@register("cute_face", "菌菌", "QQ小表情增强：bot发表情+读懂用户表情", "1.4.0")
class CuteFace(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 发表情相关配置
        self.emoji_pool: list = config.get("emoji_pool", [179])
        self.max_text_length: int = config.get("max_text_length", 35)
        self.probability: float = config.get("probability", 0.6)
        self.min_faces: int = config.get("min_faces", 1)
        self.max_faces: int = config.get("max_faces", 3)
        self.reply_with_quote: bool = config.get("reply_with_quote", True)

        # 读表情相关配置
        self.face_reading: bool = config.get("face_reading", True)

        # 构建当前表情池的描述文本（供LLM理解每个表情的含义）
        self._pool_desc = self._build_pool_desc()

    def _build_pool_desc(self) -> str:
        parts = []
        for fid in self.emoji_pool:
            fid = int(fid)
            name = FACE_NAME_MAP.get(fid, f"未知表情{fid}")
            parts.append(f"{fid}={name}")
        return ", ".join(parts)

    def _parse_face_ids(self, text: str) -> list[int]:
        pool_set = set(int(x) for x in self.emoji_pool)
        ids = []
        for num_str in re.findall(r"\d+", text):
            fid = int(num_str)
            if fid in pool_set:
                ids.append(fid)
        return ids

    def _strip_wake_prefix(self, event: AstrMessageEvent, text: str) -> str:
        msg = (text or "").strip()
        try:
            astrbot_config = self.context.get_config()
            wake_prefix = astrbot_config.get("wake_prefix", "/")
            if isinstance(wake_prefix, list):
                prefixes = [str(p) for p in wake_prefix if str(p)]
            elif isinstance(wake_prefix, str) and wake_prefix:
                prefixes = [wake_prefix]
            else:
                prefixes = []

            for prefix in sorted(prefixes, key=len, reverse=True):
                if msg.startswith(prefix):
                    return msg[len(prefix):].strip()
        except Exception:
            pass
        return msg

    def _is_forw_command(self, event: AstrMessageEvent) -> bool:
        return self._strip_wake_prefix(event, event.message_str).startswith("forw")

    # ==================== 读表情：把用户发的 Face 翻译成文字 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def translate_face_to_text(self, event: AstrMessageEvent):
        """在消息到达LLM之前，把 Face 组件翻译成 (表情:名称) 的文字"""
        if not self.face_reading:
            return
        if self._is_forw_command(event):
            return

        message = event.message_obj.message
        if not message:
            return

        changed = False
        new_chain = []

        for comp in message:
            if isinstance(comp, Comp.Face):
                face_id = getattr(comp, "id", None)
                if face_id is not None:
                    name = FACE_NAME_MAP.get(int(face_id), f"表情{face_id}")
                    new_chain.append(Comp.Plain(f"(表情:{name})"))
                    changed = True
                else:
                    new_chain.append(comp)
            else:
                new_chain.append(comp)

        if changed:
            # 同时更新 message 列表和 message_str
            message.clear()
            message.extend(new_chain)

            # 重建 message_str 让下游（包括LLM）能看到表情文字
            text_parts = []
            for comp in new_chain:
                if isinstance(comp, Comp.Plain):
                    text_parts.append(comp.text)
            event.message_str = "".join(text_parts)

    # ==================== 发表情：bot回复时追加匹配情感的小表情 ====================

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
            elif isinstance(c, Comp.Face):
                return
            elif isinstance(c, (Comp.Image, Comp.Record, Comp.Video)):
                return

        full_text = "".join(text_parts)
        if not full_text or len(full_text) > self.max_text_length:
            return

        if random.random() > self.probability:
            return

        num_faces = random.randint(self.min_faces, self.max_faces)
        appended = False

        try:
            umo = event.unified_msg_origin
            provider_id = await self.context.get_current_chat_provider_id(umo=umo)
            if not provider_id:
                self._append_random(chain, num_faces)
                appended = True
            else:
                prompt = JUDGE_PROMPT_TEMPLATE.format(
                    num=num_faces,
                    pool_desc=self._pool_desc,
                    text=full_text
                )
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
                appended = True

        except Exception as e:
            logger.warning(f"[cute_face] LLM判断表情失败，回退到随机: {e}")
            self._append_random(chain, num_faces)
            appended = True

        if appended:
            # 跳过 AstrBot 的 LLM 分段流水线，防止 Face 被拆成单独消息
            try:
                result.result_content_type = None
            except Exception:
                pass

            # 手动补回引用（因为跳过流水线后自动引用也被跳过了）
            if self.reply_with_quote:
                try:
                    msg_id = event.message_obj.message_id
                    if msg_id:
                        has_reply = any(isinstance(c, Comp.Reply) for c in chain)
                        if not has_reply:
                            chain.insert(0, Comp.Reply(id=str(msg_id)))
                except Exception:
                    pass

    def _append_random(self, chain: list, num: int):
        for _ in range(num):
            fid = random.choice(self.emoji_pool)
            chain.append(Comp.Face(id=int(fid)))
