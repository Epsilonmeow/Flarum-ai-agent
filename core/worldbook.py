"""
世界书系统 V3 - 基于 yijiekkk-main 的扫描引擎移植
支持多世界书、层级管理、完整的关键词匹配逻辑
"""

import json
import os
import re
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

# ==========================================
# 常量定义
# ==========================================

WORLD_INFO_LOGIC = {
    "AND_ANY": 0,   # 命中任意次级关键词
    "NOT_ALL": 1,   # 不能全部命中
    "NOT_ANY": 2,   # 不能命中任何
    "AND_ALL": 3    # 必须全部命中
}

WORLD_INFO_POSITION = {
    "before": 0,      # Before Char Def
    "after": 1,       # After Char Def
    "ANTop": 2,       # Author's Note Top
    "ANBottom": 3,    # Author's Note Bottom
    "atDepth": 4,     # At Depth
    "EMTop": 5,
    "EMBottom": 6
}

# 默认扫描深度
WI_DEFAULT_SCAN_DEPTH = 4
WI_MAX_RECURSION_STEPS = 10


# ==========================================
# 扫描引擎核心
# ==========================================

def escape_regex(s: str) -> str:
    """转义正则特殊字符"""
    return re.escape(str(s) if s else "")


def read_entry_key_list(entry: Dict, primary_key: str = "key") -> List[str]:
    """
    读取条目的关键词字段（兼容多别名）
    支持的别名: key/keys/keywords/keysStr 等
    """
    if not entry:
        return []
    
    alias_map = {
        "key": ["key", "keys", "keywords", "keysStr"],
        "keysecondary": ["keysecondary", "secondary_keys", "secondaryKeys", "secondaryKeysStr"],
        "exclude_key": ["exclude_key", "excludeKeys", "exclude_keys", "excludeKeysStr"]
    }
    
    aliases = alias_map.get(primary_key, [primary_key])
    
    for name in aliases:
        value = entry.get(name)
        if isinstance(value, list):
            arr = [str(v).strip() for v in value if v is not None and str(v).strip()]
            if arr:
                return arr
        elif isinstance(value, str) and value.strip():
            # 支持逗号、换行、竖线分隔
            arr = [v.strip() for v in re.split(r'\r?\n|[,，|｜]', value) if v.strip()]
            if arr:
                return arr
    
    return []


def match_world_info_key(text: str, key: str, entry: Dict) -> bool:
    """
    单条关键词匹配
    - 正则: /pattern/flags
    - 全词匹配: matchWholeWords
    - 大小写敏感: caseSensitive
    """
    if not key:
        return False
    
    raw_key = str(key)
    
    # 正则关键词
    regex_match = re.match(r'^/(.+)/([a-z]*)$', raw_key, re.IGNORECASE)
    if regex_match:
        try:
            pattern, flags = regex_match.groups()
            regex = re.compile(pattern, re.IGNORECASE if 'i' in flags else 0)
            return bool(regex.search(text or ""))
        except re.error:
            print(f"[WorldBook] 无法解析正则关键词: {raw_key}")
            return False
    
    haystack = text or ""
    needle = raw_key.strip()
    if not needle:
        return False
    
    # 大小写处理
    if not entry.get("caseSensitive"):
        haystack = haystack.lower()
        needle = needle.lower()
    
    # 全词匹配
    if entry.get("matchWholeWords"):
        try:
            escaped = escape_regex(needle)
            pattern = rf'(?:^|[^A-Za-z0-9_]){escaped}(?:$|[^A-Za-z0-9_])'
            regex = re.compile(pattern, 0 if entry.get("caseSensitive") else re.IGNORECASE)
            return bool(regex.search(text or ""))
        except re.error:
            return needle in haystack
    
    return needle in haystack


class WorldBookScanner:
    """世界书扫描器"""
    
    def __init__(self, chat_history: List[Dict]):
        # chat_history[0] 是最早的消息，倒序方便取最近N条
        self.history = list(reversed(chat_history)) if chat_history else []
        self.activated_uids: Set[str] = set()
        self.recurse_buffer: List[str] = []
    
    def build_scan_text(self, depth: int, global_scan_data: str = "") -> str:
        """构建扫描文本：最近depth条消息 + 递归缓冲 + 全局数据"""
        safe_depth = max(0, int(depth) if depth else 0)
        slice_history = self.history[:safe_depth] if safe_depth > 0 else self.history
        
        parts = []
        for msg in slice_history:
            if msg and isinstance(msg.get("content"), str):
                parts.append(msg["content"])
        
        if self.recurse_buffer:
            parts.extend(self.recurse_buffer)
        if global_scan_data:
            parts.append(str(global_scan_data))
        
        return "\n".join(parts)
    
    def build_scan_text_for_entry(self, entry: Dict, default_depth: int, global_scan_data: str) -> str:
        """为条目构建扫描文本（支持条目级scanDepth覆盖）"""
        entry_depth = entry.get("scanDepth")
        depth = default_depth if entry_depth is None or entry_depth == "" else max(0, int(entry_depth) if entry_depth else 0)
        return self.build_scan_text(depth, global_scan_data)
    
    def check_entry(self, entry: Dict, scan_text: str) -> bool:
        """检查单个条目是否应当激活"""
        # 1. 排除关键词：命中即否决
        exclude_keys = read_entry_key_list(entry, "exclude_key")
        for k in exclude_keys:
            if match_world_info_key(scan_text, k, entry):
                return False
        
        # 2. 主关键词
        primary_keys = read_entry_key_list(entry, "key")
        primary_matched = False
        
        if entry.get("constant") is True:
            # 常驻模式：不依赖关键词，始终注入到上下文
            primary_matched = True
        elif not primary_keys:
            # 没有主关键词：视为常驻模式，兼容旧数据
            primary_matched = True
        else:
            # 关键词模式：必须命中至少一个主关键词
            for k in primary_keys:
                if match_world_info_key(scan_text, k, entry):
                    primary_matched = True
                    break
            if not primary_matched:
                return False
        
        # 3. 次级关键词 + selectiveLogic
        if entry.get("selective") is True:
            secondary = read_entry_key_list(entry, "keysecondary")
            if secondary:
                logic = entry.get("selectiveLogic", WORLD_INFO_LOGIC["AND_ANY"])
                if not isinstance(logic, int):
                    logic = WORLD_INFO_LOGIC["AND_ANY"]
                
                match_count = sum(1 for k in secondary if match_world_info_key(scan_text, k, entry))
                has_any = match_count > 0
                has_all = match_count == len(secondary)
                
                if logic == WORLD_INFO_LOGIC["AND_ANY"] and not has_any:
                    return False
                elif logic == WORLD_INFO_LOGIC["AND_ALL"] and not has_all:
                    return False
                elif logic == WORLD_INFO_LOGIC["NOT_ALL"] and has_all:
                    return False
                elif logic == WORLD_INFO_LOGIC["NOT_ANY"] and has_any:
                    return False
        
        # 4. 概率判定
        use_prob = entry.get("useProbability", True)
        prob = entry.get("probability", 100)
        if use_prob and prob < 100:
            if random.random() * 100 > prob:
                return False
        
        return True


def get_entry_uid(entry: Dict, fallback_index: int) -> str:
    """获取条目的唯一标识"""
    return str(entry.get("uid") or entry.get("id") or f"__idx_{fallback_index}")


def resolve_group_exclusions(entries: List[Dict]) -> List[Dict]:
    """
    分组互斥：同一group内只保留1条
    - 如果任意条目设置了useGroupScoring=true，按groupWeight*random加权抽签
    - 否则取order最大的那条
    """
    if not entries:
        return []
    
    grouped = {}
    ungrouped = []
    
    for entry in entries:
        group_name = str(entry.get("group") or "").strip()
        if not group_name:
            ungrouped.append(entry)
            continue
        
        if group_name not in grouped:
            grouped[group_name] = []
        grouped[group_name].append(entry)
    
    winners = []
    for members in grouped.values():
        if len(members) == 1:
            winners.append(members[0])
            continue
        
        use_scoring = any(m.get("useGroupScoring") is True for m in members)
        if use_scoring:
            best_score = -float('inf')
            chosen = members[0]
            for m in members:
                w = max(0, m.get("groupWeight", 100) if isinstance(m.get("groupWeight"), (int, float)) else 100)
                score = w * random.random()
                if score > best_score:
                    best_score = score
                    chosen = m
            winners.append(chosen)
        else:
            sorted_members = sorted(members, key=lambda x: x.get("order", 0), reverse=True)
            winners.append(sorted_members[0])
    
    return ungrouped + winners


def scan_world_info(
    chat_history: List[Dict],
    world_book: Dict,
    global_scan_data: str = "",
    runtime_options: Optional[Dict] = None
) -> List[Dict]:
    """
    主扫描入口
    
    Args:
        chat_history: 聊天历史消息列表（按时间正序）
        world_book: 世界书对象（包含entries列表）
        global_scan_data: 额外扫描文本（通常是当前用户输入）
        runtime_options: 运行期选项
            - scanDepth: 全局默认扫描深度
            - maxRecursion: 最大递归轮数（默认10）
    
    Returns:
        已激活的条目列表（按order倒序排列）
    """
    entries = world_book.get("entries", []) if isinstance(world_book, dict) else []
    if not entries:
        return []
    
    if not isinstance(entries, list):
        # 兼容旧格式 {id: entry}
        entries = list(entries.values())
    
    runtime = runtime_options or {}
    default_scan_depth = max(0, int(runtime.get("scanDepth")) if isinstance(runtime.get("scanDepth"), (int, float)) else WI_DEFAULT_SCAN_DEPTH)
    max_recursion = max(1, int(runtime.get("maxRecursion")) if isinstance(runtime.get("maxRecursion"), (int, float)) else WI_MAX_RECURSION_STEPS)
    
    scanner = WorldBookScanner(chat_history)
    all_activated = []
    pass_count = 0
    has_new = True
    
    while has_new and pass_count < max_recursion:
        pass_count += 1
        has_new = False
        pass_activated = []
        
        for i, entry in enumerate(entries):
            if not entry:
                continue
            
            # 启用状态检查
            if entry.get("disable") is True or entry.get("enabled") is False:
                continue
            
            # 已激活检查
            uid = get_entry_uid(entry, i)
            if uid in scanner.activated_uids:
                continue
            
            # 第二轮起跳过 excludeRecursion 条目
            if pass_count > 1 and entry.get("excludeRecursion") is True:
                continue
            
            scan_text = scanner.build_scan_text_for_entry(entry, default_scan_depth, global_scan_data)
            if not scanner.check_entry(entry, scan_text):
                continue
            
            pass_activated.append(entry)
        
        if not pass_activated:
            break
        
        # 分组互斥
        winners = resolve_group_exclusions(pass_activated)
        should_prevent_recursion = False
        
        for entry in winners:
            uid = get_entry_uid(entry, entries.index(entry) if entry in entries else 0)
            if uid in scanner.activated_uids:
                continue
            
            scanner.activated_uids.add(uid)
            all_activated.append(entry)
            
            # 递归注入
            if entry.get("excludeRecursion") is not True:
                content = entry.get("content", "")
                if isinstance(content, str) and content.strip():
                    scanner.recurse_buffer.append(content)
            
            # 递归控制
            if entry.get("preventRecursion") is True:
                should_prevent_recursion = True
            elif entry.get("excludeRecursion") is not True:
                has_new = True
        
        if should_prevent_recursion:
            has_new = False
    
    # 按order倒序排列
    all_activated.sort(key=lambda x: x.get("order", 0), reverse=True)
    return all_activated


# ==========================================
# 数据管理
# ==========================================

class WorldBookManager:
    """世界书管理器"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.worldbooks_dir = self.data_dir / "worldbooks"
        self.worldbooks_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前启用的世界书ID列表
        self.active_worldbook_ids: List[str] = []
        
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        config_path = self.worldbooks_dir / "config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.active_worldbook_ids = config.get("active_ids", [])
            except Exception as e:
                print(f"[WorldBook] 加载配置失败: {e}")
                self.active_worldbook_ids = []
    
    def _save_config(self):
        """保存配置"""
        config_path = self.worldbooks_dir / "config.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "active_ids": self.active_worldbook_ids,
                    "updated_at": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WorldBook] 保存配置失败: {e}")
    
    def _get_wb_path(self, wb_id: str) -> Path:
        """获取世界书文件路径"""
        return self.worldbooks_dir / f"{wb_id}.json"
    
    def create_worldbook(self, name: str, description: str = "") -> Dict:
        """创建新世界书"""
        wb_id = f"wb_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}"
        worldbook = {
            "id": wb_id,
            "name": name,
            "description": description,
            "enabled": True,
            "expanded": True,
            "entries": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self.save_worldbook(worldbook)
        return worldbook
    
    def save_worldbook(self, worldbook: Dict):
        """保存世界书"""
        if not worldbook or "id" not in worldbook:
            return False
        
        wb_id = worldbook["id"]
        worldbook["updated_at"] = datetime.now().isoformat()
        
        try:
            with open(self._get_wb_path(wb_id), 'w', encoding='utf-8') as f:
                json.dump(worldbook, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[WorldBook] 保存世界书失败: {e}")
            return False
    
    def load_worldbook(self, wb_id: str) -> Optional[Dict]:
        """加载世界书"""
        path = self._get_wb_path(wb_id)
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WorldBook] 加载世界书失败: {e}")
            return None
    
    def delete_worldbook(self, wb_id: str) -> bool:
        """删除世界书"""
        path = self._get_wb_path(wb_id)
        if path.exists():
            try:
                path.unlink()
                # 从激活列表移除
                if wb_id in self.active_worldbook_ids:
                    self.active_worldbook_ids.remove(wb_id)
                    self._save_config()
                return True
            except Exception as e:
                print(f"[WorldBook] 删除世界书失败: {e}")
        return False
    
    def list_worldbooks(self) -> List[Dict]:
        """列出所有世界书（摘要信息）"""
        worldbooks = []
        for path in self.worldbooks_dir.glob("wb_*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    wb = json.load(f)
                    worldbooks.append({
                        "id": wb.get("id"),
                        "name": wb.get("name", "未命名"),
                        "description": wb.get("description", ""),
                        "enabled": wb.get("enabled", True),
                        "expanded": wb.get("expanded", False),
                        "entry_count": len(wb.get("entries", [])),
                        "updated_at": wb.get("updated_at", "")
                    })
            except Exception as e:
                print(f"[WorldBook] 读取世界书失败 {path}: {e}")
        
        return sorted(worldbooks, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    def get_all_worldbooks(self) -> List[Dict]:
        """获取所有世界书的完整数据"""
        worldbooks = []
        for path in self.worldbooks_dir.glob("wb_*.json"):
            wb = self.load_worldbook(path.stem)
            if wb:
                worldbooks.append(wb)
        return worldbooks
    
    # ============ 条目管理 ============
    
    def add_entry(self, wb_id: str, entry_data: Dict) -> Optional[Dict]:
        """添加条目到世界书"""
        wb = self.load_worldbook(wb_id)
        if not wb:
            return None
        
        new_entry = {
            "uid": f"entry_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}",
            "worldbook_id": wb_id,
            "enabled": True,
            "order": 100,
            "position": 0,  # before char
            "depth": 4,
            "probability": 100,
            "useProbability": True,
            "selective": False,
            "selectiveLogic": WORLD_INFO_LOGIC["AND_ANY"],
            "matchWholeWords": False,
            "caseSensitive": False,
            "constant": False,
            "excludeRecursion": False,
            "preventRecursion": False,
            "created_at": datetime.now().isoformat(),
            **entry_data
        }
        
        # 处理keysStr -> key
        if "keysStr" in entry_data:
            new_entry["key"] = [k.strip() for k in str(entry_data["keysStr"]).split(",") if k.strip()]
        
        wb["entries"].append(new_entry)
        self.save_worldbook(wb)
        return new_entry
    
    def update_entry(self, wb_id: str, entry_uid: str, updates: Dict) -> bool:
        """更新条目"""
        wb = self.load_worldbook(wb_id)
        if not wb:
            return False
        
        for entry in wb["entries"]:
            if entry.get("uid") == entry_uid:
                entry.update(updates)
                entry["updated_at"] = datetime.now().isoformat()
                
                # 处理keysStr -> key
                if "keysStr" in updates:
                    entry["key"] = [k.strip() for k in str(updates["keysStr"]).split(",") if k.strip()]
                
                self.save_worldbook(wb)
                return True
        
        return False
    
    def delete_entry(self, wb_id: str, entry_uid: str) -> bool:
        """删除条目"""
        wb = self.load_worldbook(wb_id)
        if not wb:
            return False
        
        wb["entries"] = [e for e in wb["entries"] if e.get("uid") != entry_uid]
        self.save_worldbook(wb)
        return True
    
    def get_entry(self, wb_id: str, entry_uid: str) -> Optional[Dict]:
        """获取单个条目"""
        wb = self.load_worldbook(wb_id)
        if not wb:
            return None
        
        for entry in wb["entries"]:
            if entry.get("uid") == entry_uid:
                return entry
        return None
    
    # ============ 激活状态管理 ============
    
    def set_worldbook_enabled(self, wb_id: str, enabled: bool):
        """设置世界书启用状态"""
        wb = self.load_worldbook(wb_id)
        if wb:
            wb["enabled"] = enabled
            self.save_worldbook(wb)
            
            # 更新激活列表
            if enabled and wb_id not in self.active_worldbook_ids:
                self.active_worldbook_ids.append(wb_id)
            elif not enabled and wb_id in self.active_worldbook_ids:
                self.active_worldbook_ids.remove(wb_id)
            self._save_config()
    
    def set_entry_enabled(self, wb_id: str, entry_uid: str, enabled: bool):
        """设置条目启用状态"""
        self.update_entry(wb_id, entry_uid, {"enabled": enabled})
    
    def get_active_entries(self) -> List[Dict]:
        """
        获取所有激活的条目（用于提示词组装）
        层级判定：世界书启用 → 条目启用 → 关键词匹配
        """
        active_entries = []
        
        for wb_id in self.active_worldbook_ids:
            wb = self.load_worldbook(wb_id)
            if not wb or not wb.get("enabled", True):
                continue
            
            for entry in wb.get("entries", []):
                # 条目必须明确启用
                if entry.get("enabled") is False:
                    continue
                # 添加世界书上下文
                entry["_worldbook_name"] = wb.get("name", "")
                entry["_worldbook_id"] = wb_id
                active_entries.append(entry)
        
        return active_entries
    
    def scan_active_entries(self, chat_history: List[Dict], user_input: str = "") -> List[Dict]:
        """
        扫描所有激活条目，返回应当注入的条目列表
        """
        all_activated = []
        
        for wb_id in self.active_worldbook_ids:
            wb = self.load_worldbook(wb_id)
            if not wb or not wb.get("enabled", True):
                continue
            
            # 过滤启用的条目
            enabled_entries = [e for e in wb.get("entries", []) if e.get("enabled") is not False]
            if not enabled_entries:
                continue
            
            # 扫描该世界书的条目
            temp_wb = {"entries": enabled_entries}
            activated = scan_world_info(chat_history, temp_wb, user_input)
            
            # 添加来源标记
            for entry in activated:
                entry["_worldbook_name"] = wb.get("name", "")
                entry["_worldbook_id"] = wb_id
            
            all_activated.extend(activated)
        
        # 全局排序
        all_activated.sort(key=lambda x: x.get("order", 0), reverse=True)
        return all_activated


# ==========================================
# 兼容性函数（保持旧API）
# ==========================================

def load_world_book_legacy(data_dir: Path) -> Dict:
    """加载旧格式世界书"""
    world_book_path = data_dir / os.getenv("WORLD_BOOK_FILE", "worldbook.json")
    if world_book_path.exists():
        try:
            with open(world_book_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WorldBook] 加载旧格式失败: {e}")
    return {}


def migrate_to_v3(manager: WorldBookManager, legacy_data: Dict) -> bool:
    """迁移旧格式到V3格式"""
    if not legacy_data or "entries" not in legacy_data:
        return False
    
    # 创建默认世界书
    wb = manager.create_worldbook(
        name=legacy_data.get("name", "Default Worldbook"),
        description=legacy_data.get("description", "迁移自旧版本")
    )
    
    # 迁移条目
    entries = legacy_data.get("entries", {})
    if isinstance(entries, dict):
        for entry_id, entry in entries.items():
            manager.add_entry(wb["id"], {
                "comment": entry.get("title", entry_id),
                "content": entry.get("content", ""),
                "keysStr": ", ".join(entry.get("keywords", [])),
                "priority": entry.get("priority", 100),
                "position": ["@D", "@P", "@F"].index(entry.get("position", "@D")) if entry.get("position") in ["@D", "@P", "@F"] else 0,
                "scan_depth": entry.get("scan_depth", 3),
                "constant": entry.get("strategy") == "constant",
                "enabled": True
            })
    
    # 设置为激活
    manager.active_worldbook_ids.append(wb["id"])
    manager._save_config()
    
    return True