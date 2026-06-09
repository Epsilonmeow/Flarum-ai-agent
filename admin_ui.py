"""
Flarum AI Agent V2 - Streamlit 可视化后台管理界面
支持 Provider 架构、三层记忆系统、好感度系统、世界书V3
"""

import json
import html
import os
import sys
import subprocess
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import streamlit as st

# 导入世界书V3
sys.path.insert(0, str(Path(__file__).parent))
from core.worldbook import WorldBookManager, migrate_to_v3, load_world_book_legacy

# 页面配置
st.set_page_config(
    page_title="🐱 Flarum AI Agent V2 管理后台",
    page_icon="🐱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 路径配置
# ==========================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = DATA_DIR / "memory"
AFFECTION_DIR = DATA_DIR / "affection"
WORLD_BOOK_PATH = DATA_DIR / os.getenv("WORLD_BOOK_FILE", "worldbook.json")
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"
SANDBOX_DIR = DATA_DIR / "sandbox"
SANDBOX_REPORT_DIR = SANDBOX_DIR / "reports"
SANDBOX_CASES_PATH = BASE_DIR / "tests" / "sandbox_cases.json"

# ==========================================
# 视觉样式
# ==========================================

st.markdown(
    """
    <style>
    :root {
        --sus-bg: #f7fafc;
        --sus-bg-2: #f4f8ff;
        --sus-panel: #ffffff;
        --sus-panel-soft: rgba(255, 255, 255, 0.86);
        --sus-border: #e6edf5;
        --sus-text: #172033;
        --sus-muted: #667085;
        --sus-blue: #2f80ed;
        --sus-cyan: #18b6a8;
        --sus-orange: #ffb86b;
        --sus-green: #16a34a;
        --sus-red: #ef4444;
        --sus-yellow: #d99a20;
        --sus-shadow: 0 14px 38px rgba(28, 64, 110, 0.08);
        --sus-shadow-soft: 0 8px 22px rgba(28, 64, 110, 0.06);
        --sus-radius: 18px;
    }

    .stApp {
        color: var(--sus-text);
        background:
            radial-gradient(circle at 8% 8%, rgba(47, 128, 237, 0.08), transparent 28%),
            radial-gradient(circle at 92% 2%, rgba(24, 182, 168, 0.10), transparent 26%),
            linear-gradient(135deg, var(--sus-bg) 0%, var(--sus-bg-2) 100%);
    }
    .block-container {
        padding-top: 1.35rem;
        padding-bottom: 2.5rem;
        max-width: 1360px;
    }
    h1, h2, h3 {
        color: var(--sus-text);
        letter-spacing: -0.02em;
    }

    div[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.90);
        border-right: 1px solid var(--sus-border);
        box-shadow: 10px 0 32px rgba(28, 64, 110, 0.045);
    }
    div[data-testid="stSidebar"] > div:first-child {
        padding-top: 1.25rem;
    }
    div[role="radiogroup"] label {
        border-radius: 13px;
        padding: 0.42rem 0.55rem;
        margin: 0.12rem 0;
        transition: all 160ms ease;
    }
    div[role="radiogroup"] label:hover {
        background: rgba(47, 128, 237, 0.08);
        transform: translateX(2px);
    }

    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--sus-border);
        border-radius: var(--sus-radius);
        padding: 1rem 1.05rem;
        box-shadow: var(--sus-shadow-soft);
    }
    div[data-testid="stMetric"] label {
        color: var(--sus-muted) !important;
    }
    div[data-testid="stMetricValue"] {
        color: var(--sus-text);
        font-weight: 800;
    }
    div[data-testid="stExpander"] {
        border: 1px solid var(--sus-border);
        border-radius: var(--sus-radius);
        overflow: hidden;
        box-shadow: var(--sus-shadow-soft);
        background: rgba(255, 255, 255, 0.78);
    }
    div[data-testid="stDataFrame"], div[data-testid="stJson"] {
        border-radius: 14px;
        overflow: hidden;
    }
    .stButton > button {
        border-radius: 12px;
        border: 1px solid #d7e3f2;
        box-shadow: 0 6px 16px rgba(47, 128, 237, 0.08);
        transition: all 160ms ease;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        line-height: 1;
    }
    .stButton > button p {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        line-height: 1;
        margin: 0;
        width: 100%;
    }
    .stButton > button:hover {
        border-color: rgba(47, 128, 237, 0.55);
        box-shadow: 0 10px 22px rgba(47, 128, 237, 0.13);
        transform: translateY(-1px);
    }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {
        border-radius: 12px !important;
        border-color: #dbe7f3 !important;
    }

    .sus-sidebar-brand {
        position: relative;
        padding: 1rem 1rem 0.95rem;
        border-radius: 20px;
        background: linear-gradient(145deg, rgba(255,255,255,0.96), rgba(240,247,255,0.96));
        border: 1px solid var(--sus-border);
        box-shadow: var(--sus-shadow-soft);
        overflow: hidden;
        margin-bottom: 1rem;
    }
    .sus-sidebar-brand::after {
        content: "";
        position: absolute;
        right: -26px;
        top: -30px;
        width: 92px;
        height: 92px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(24,182,168,0.20), transparent 66%);
    }
    .sus-brand-title {
        font-size: 1.05rem;
        font-weight: 850;
        color: var(--sus-text);
        letter-spacing: -0.02em;
    }
    .sus-brand-subtitle {
        margin-top: 0.22rem;
        color: var(--sus-muted);
        font-size: 0.82rem;
        line-height: 1.45;
    }
    .sus-sidebar-card {
        padding: 0.78rem 0.85rem;
        border-radius: 16px;
        background: rgba(247,250,252,0.88);
        border: 1px solid var(--sus-border);
        color: var(--sus-muted);
        font-size: 0.84rem;
        line-height: 1.55;
    }
    .sus-sidebar-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #dce7f3, transparent);
        margin: 0.95rem 0;
    }

    .sus-hero {
        position: relative;
        padding: 1.45rem 1.55rem;
        border-radius: 24px;
        background:
            linear-gradient(135deg, rgba(255,255,255,0.96), rgba(245,250,255,0.94)),
            linear-gradient(120deg, rgba(47,128,237,0.10), rgba(24,182,168,0.10));
        border: 1px solid rgba(218, 230, 244, 0.98);
        box-shadow: var(--sus-shadow);
        overflow: hidden;
        margin-bottom: 1.15rem;
    }
    .sus-hero::before {
        content: "";
        position: absolute;
        inset: 0;
        background-image:
            linear-gradient(rgba(47,128,237,0.045) 1px, transparent 1px),
            linear-gradient(90deg, rgba(47,128,237,0.045) 1px, transparent 1px);
        background-size: 34px 34px;
        mask-image: linear-gradient(90deg, transparent, black 18%, black 80%, transparent);
        pointer-events: none;
    }
    .sus-hero-content { position: relative; z-index: 1; }
    .sus-eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 0.42rem;
        color: var(--sus-blue);
        font-weight: 800;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .sus-hero-title {
        margin: 0.34rem 0 0.22rem;
        font-size: 2rem;
        line-height: 1.18;
        font-weight: 880;
        color: var(--sus-text);
        letter-spacing: -0.045em;
    }
    .sus-hero-subtitle {
        max-width: 760px;
        color: var(--sus-muted);
        font-size: 0.98rem;
        line-height: 1.65;
    }

    .sus-card {
        padding: 1rem 1.1rem;
        border-radius: var(--sus-radius);
        background: var(--sus-panel-soft);
        border: 1px solid var(--sus-border);
        box-shadow: var(--sus-shadow-soft);
        margin-bottom: 0.75rem;
    }
    .sus-card-title {
        font-weight: 820;
        color: var(--sus-text);
        margin-bottom: 0.25rem;
    }
    .sus-muted {
        color: var(--sus-muted);
        font-size: 0.92rem;
    }
    .sus-status-card {
        min-height: 128px;
        padding: 1.05rem 1.05rem 0.95rem;
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid var(--sus-border);
        box-shadow: var(--sus-shadow-soft);
        position: relative;
        overflow: hidden;
        margin-bottom: 0.75rem;
    }
    .sus-status-card::after {
        content: "";
        position: absolute;
        right: -34px;
        bottom: -36px;
        width: 96px;
        height: 96px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(47,128,237,0.10), transparent 68%);
    }
    .sus-status-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        color: var(--sus-muted);
        font-size: 0.82rem;
        font-weight: 720;
    }
    .sus-status-value {
        position: relative;
        z-index: 1;
        margin-top: 0.65rem;
        color: var(--sus-text);
        font-size: 1.24rem;
        font-weight: 850;
        letter-spacing: -0.02em;
    }
    .sus-status-caption {
        position: relative;
        z-index: 1;
        margin-top: 0.32rem;
        color: var(--sus-muted);
        font-size: 0.84rem;
    }
    .sus-dot {
        width: 0.62rem;
        height: 0.62rem;
        border-radius: 999px;
        display: inline-block;
        box-shadow: 0 0 0 4px rgba(47,128,237,0.10);
        background: var(--sus-blue);
    }
    .sus-status-success .sus-dot { background: var(--sus-green); box-shadow: 0 0 0 4px rgba(22,163,74,0.12); }
    .sus-status-warn .sus-dot { background: var(--sus-yellow); box-shadow: 0 0 0 4px rgba(217,154,32,0.13); }
    .sus-status-danger .sus-dot { background: var(--sus-red); box-shadow: 0 0 0 4px rgba(239,68,68,0.13); }
    .sus-status-cyan .sus-dot { background: var(--sus-cyan); box-shadow: 0 0 0 4px rgba(24,182,168,0.12); }

    .sus-info-card {
        padding: 1.05rem 1.1rem;
        border-radius: 20px;
        background: rgba(255,255,255,0.86);
        border: 1px solid var(--sus-border);
        box-shadow: var(--sus-shadow-soft);
        margin-bottom: 0.8rem;
    }
    .sus-info-title {
        display: flex;
        align-items: center;
        gap: 0.44rem;
        font-weight: 820;
        color: var(--sus-text);
        margin-bottom: 0.35rem;
    }
    .sus-info-body {
        color: var(--sus-muted);
        font-size: 0.92rem;
        line-height: 1.68;
    }
    .sus-panel-title {
        margin: 1rem 0 0.72rem;
        font-size: 1.08rem;
        font-weight: 850;
        color: var(--sus-text);
        letter-spacing: -0.02em;
    }
    .sus-kv {
        display: grid;
        grid-template-columns: 6.5rem 1fr;
        gap: 0.38rem 0.6rem;
        color: var(--sus-muted);
        font-size: 0.88rem;
        line-height: 1.45;
    }
    .sus-kv b { color: var(--sus-text); }
    .sus-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.22rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 780;
        border: 1px solid transparent;
    }
    .sus-badge-ok {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        background: #e8fff1;
        color: #147a3d;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .sus-badge-warn {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        background: #fff6df;
        color: #9a6400;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .sus-badge-danger {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        background: #ffecec;
        color: #a42a2a;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .sus-badge-blue { background: #edf5ff; color: #1d63b7; border-color: #d7e9ff; }
    .sus-badge-cyan { background: #eafbf8; color: #087b72; border-color: #c9f2ec; }
    .sus-badge-green { background: #ecfdf3; color: #147a3d; border-color: #d7f7e2; }
    .sus-badge-orange { background: #fff7ed; color: #a35a00; border-color: #ffe4c2; }
    .sus-badge-red { background: #fff1f2; color: #b42318; border-color: #ffd7dc; }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# 辅助函数
# ==========================================

def _safe_html(value: Any) -> str:
    """转义用于自定义 HTML 片段的文本。"""
    return html.escape(str(value), quote=True)

def render_page_header(title: str, subtitle: str = "", eyebrow: str = "Flarum AI Agent V2"):
    """渲染清爽浅色 + 轻科技感页面头部。"""
    st.markdown(
        f"""
        <div class="sus-hero">
          <div class="sus-hero-content">
            <div class="sus-eyebrow">● {_safe_html(eyebrow)}</div>
            <div class="sus-hero-title">{_safe_html(title)}</div>
            <div class="sus-hero-subtitle">{_safe_html(subtitle)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_status_card(title: str, value: str, caption: str = "", variant: str = "blue"):
    """渲染统一状态卡片。variant: blue / cyan / success / warn / danger。"""
    variant_class = {
        "success": "sus-status-success",
        "warn": "sus-status-warn",
        "danger": "sus-status-danger",
        "cyan": "sus-status-cyan",
        "blue": ""
    }.get(variant, "")
    st.markdown(
        f"""
        <div class="sus-status-card {variant_class}">
          <div class="sus-status-head">
            <span>{_safe_html(title)}</span>
            <span class="sus-dot"></span>
          </div>
          <div class="sus-status-value">{_safe_html(value)}</div>
          <div class="sus-status-caption">{_safe_html(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_info_card(title: str, body: str, icon: str = "✨"):
    """渲染说明/提示信息卡。"""
    st.markdown(
        f"""
        <div class="sus-info-card">
          <div class="sus-info-title"><span>{_safe_html(icon)}</span><span>{_safe_html(title)}</span></div>
          <div class="sus-info-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_panel_title(title: str):
    """渲染轻量分区标题。"""
    st.markdown(f"<div class='sus-panel-title'>{_safe_html(title)}</div>", unsafe_allow_html=True)

def get_worldbook_light(enabled: bool) -> tuple[str, str]:
    """返回世界书启用状态灯：绿色=启用，灰色=禁用。"""
    if enabled:
        return ":green[●]", "启用：该世界书参与扫描"
    return ":gray[●]", "禁用：该世界书不参与扫描"

def get_entry_light(entry: Dict[str, Any]) -> tuple[str, str, str]:
    """返回条目状态灯，仿 SillyTavern：绿=关键词触发，蓝=constant，灰=关闭。"""
    enabled = entry.get("enabled", True)
    if not enabled:
        return ":gray[●]", "关闭", "灰灯：条目已关闭，不会发送给 AI"
    if entry.get("constant", False):
        return ":blue[●]", "常驻", "蓝灯（constant）：始终存在于发送给 AI 的上下文中"
    return ":green[●]", "关键词", "绿灯：条目开启，按关键词触发后发送给 AI"

def load_world_book():
    """加载世界书 JSON"""
    try:
        if WORLD_BOOK_PATH.exists():
            with open(WORLD_BOOK_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        st.error(f"加载世界书失败: {str(e)}")
        return {}

def save_world_book(data):
    """保存世界书 JSON"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data['last_updated'] = datetime.now().isoformat()
        with open(WORLD_BOOK_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存世界书失败: {str(e)}")
        return False

def load_env():
    """加载 .env 文件"""
    env_data = {}
    try:
        if ENV_PATH.exists():
            with open(ENV_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_data[key] = value
    except Exception as e:
        st.error(f"加载 .env 失败: {str(e)}")
    return env_data

def save_env(env_data):
    """保存 .env 文件"""
    try:
        lines = []
        if ENV_EXAMPLE_PATH.exists():
            with open(ENV_EXAMPLE_PATH, 'r', encoding='utf-8') as f:
                template = f.read()
            
            for key, value in env_data.items():
                safe_value = value.replace('\\n', '\\\\n').replace('\\r', '\\\\r')
                template = template.replace(f"{key}=your-", f"{key}={safe_value}")
                template = template.replace(f"{key}=gpt-", f"{key}={safe_value}")
                template = template.replace(f"{key}=https://", f"{key}={safe_value}")
                template = template.replace(f"{key}=INFO", f"{key}={safe_value}")
                template = template.replace(f"{key}=60", f"{key}={safe_value}")
                template = template.replace(f"{key}=0.3", f"{key}={safe_value}")
                template = template.replace(f"{key}=5", f"{key}={safe_value}")
                template = template.replace(f"{key}=8000", f"{key}={safe_value}")
                template = template.replace(f"{key}=8501", f"{key}={safe_value}")
            
            with open(ENV_PATH, 'w', encoding='utf-8') as f:
                f.write(template)
        else:
            with open(ENV_PATH, 'w', encoding='utf-8') as f:
                for key, value in env_data.items():
                    f.write(f"{key}={value}\\n")
        return True
    except Exception as e:
        st.error(f"保存 .env 失败: {str(e)}")
        return False

def load_json_file(path: Path, default=None):
    """安全加载 JSON 文件"""
    if default is None:
        default = {}
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        st.warning(f"读取 JSON 失败: {path.name} - {e}")
    return default

def count_json_files(path: Path, pattern: str = "*.json") -> int:
    """递归统计 JSON 文件数量"""
    if not path.exists():
        return 0
    return len(list(path.rglob(pattern)))

def load_sandbox_cases() -> List[Dict[str, Any]]:
    """加载沙盒测试用例"""
    data = load_json_file(SANDBOX_CASES_PATH, [])
    return data if isinstance(data, list) else []

def get_latest_sandbox_report() -> Dict[str, Any]:
    """获取最近一次沙盒测试报告"""
    if not SANDBOX_REPORT_DIR.exists():
        return {}
    reports = sorted(SANDBOX_REPORT_DIR.glob("sandbox_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        return {}
    report = load_json_file(reports[0], {})
    if isinstance(report, dict):
        report["_path"] = str(reports[0])
    return report

def run_sandbox_command(case_id: str = None, keep_data: bool = False) -> subprocess.CompletedProcess:
    """从管理后台运行沙盒测试命令"""
    cmd = [sys.executable, str(BASE_DIR / "sandbox_test.py")]
    if case_id:
        cmd.extend(["--case", case_id])
    if keep_data:
        cmd.append("--keep-data")
    return subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120
    )

# ==========================================
# V2 系统初始化
# ==========================================

@st.cache_resource
def init_v2_system():
    """初始化 V2 系统组件"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        
        # 导入 V2 组件
        from core.providers.manager import provider_manager
        from core.memory import LayeredMemory
        from core.affection import AffectionManager
        
        # 初始化
        memory = LayeredMemory(MEMORY_DIR)
        affection = AffectionManager(AFFECTION_DIR)
        
        return {
            "provider_manager": provider_manager,
            "memory": memory,
            "affection": affection,
            "initialized": True
        }
    except Exception as e:
        st.error(f"V2 系统初始化失败: {e}")
        return {"initialized": False, "error": str(e)}

# ==========================================
# 侧边栏导航
# ==========================================

st.sidebar.markdown(
    """
    <div class="sus-sidebar-brand">
      <div class="sus-brand-title">Flarum AI Agent</div>
      <div class="sus-brand-subtitle">清爽轻科技风管理控制台<br/>Provider · Memory · Affection</div>
    </div>
    """,
    unsafe_allow_html=True
)

page = st.sidebar.radio(
    "选择页面",
    [
        "📊 系统状态",
        "🔌 Provider 管理",
        "🧪 沙盒测试",
        "📖 世界书编辑",
        "🧠 三层记忆",
        "❤️ 好感度系统",
        "⚙️ 系统配置",
        "⏱️ 冷却监控"
    ]
)

st.sidebar.markdown('<div class="sus-sidebar-divider"></div>', unsafe_allow_html=True)
st.sidebar.markdown(
    """
    <div class="sus-sidebar-card">
      <b style="color:#172033;">● Admin Online</b><br/>
      版本：v2.0.0<br/>
      架构：Provider + 三层记忆 + 好感度<br/>
      <a href="http://localhost:8000/docs" target="_blank">打开 API 文档 ↗</a>
    </div>
    """,
    unsafe_allow_html=True
)

# ==========================================
# 页面: 系统状态
# ==========================================

if page == "📊 系统状态":
    render_page_header(
        "系统状态监控",
        "集中查看 Webhook、Admin UI、Provider、配置文件、沙盒测试与核心数据文件状态。"
    )
    
    # 初始化 V2 系统
    v2_system = init_v2_system()
    
    # 状态卡片
    latest_report = get_latest_sandbox_report()
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        webhook_ready = WORLD_BOOK_PATH.exists()
        render_status_card("Webhook 服务", "运行中" if webhook_ready else "待配置", "端口 8000", "success" if webhook_ready else "warn")
    
    with col2:
        render_status_card("Admin UI", "运行中", "端口 8501", "cyan")
    
    with col3:
        env_ready = ENV_PATH.exists()
        render_status_card("配置文件", "已配置" if env_ready else "未配置", ".env", "success" if env_ready else "danger")
    
    with col4:
        v2_ready = v2_system.get("initialized")
        render_status_card("V2 核心", "已初始化" if v2_ready else "未初始化", "Provider / Memory / Affection", "success" if v2_ready else "danger")

    with col5:
        if latest_report:
            sandbox_passed = latest_report.get("failed_cases", 1) == 0
            render_status_card(
                "沙盒测试",
                "PASS" if sandbox_passed else "FAIL",
                f"{latest_report.get('passed_cases', 0)}/{latest_report.get('total_cases', 0)}",
                "success" if sandbox_passed else "danger"
            )
        else:
            render_status_card("沙盒测试", "无报告", "建议先运行一次离线测试", "warn")
    
    # Provider 状态
    render_panel_title("🔌 Provider 状态")
    if v2_system.get("initialized"):
        try:
            provider_manager = v2_system["provider_manager"]
            
            # 异步运行健康检查
            async def check_providers():
                return await provider_manager.health_check()
            
            health = asyncio.run(check_providers())
            
            cols = st.columns(len(health) if health else 1)
            for idx, (name, available) in enumerate(health.items()):
                with cols[idx % 3]:
                    render_status_card(f"Provider · {name}", "可用" if available else "不可用", "健康检查", "success" if available else "danger")
        except Exception as e:
            st.error(f"Provider 检查失败: {e}")
    else:
        st.info("V2 系统未初始化")
    
    # 文件状态
    render_panel_title("📁 数据文件状态")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🌍 世界书**")
        if WORLD_BOOK_PATH.exists():
            world_book = load_world_book()
            st.success(f"✅ 已加载")
            st.json({
                "名称": world_book.get("name", "N/A"),
                "版本": world_book.get("version", "N/A"),
                "条目数": len(world_book.get("entries", {})),
                "最后更新": world_book.get("last_updated", "N/A")[:10] if world_book.get("last_updated") else "N/A"
            })
        else:
            st.error(f"❌ 未找到")
    
    with col2:
        st.markdown("**🧠 记忆数据**")
        if MEMORY_DIR.exists():
            memory_files_count = count_json_files(MEMORY_DIR)
            st.success(f"✅ 已加载")
            st.json({
                "存储路径": str(MEMORY_DIR),
                "用户文件数": memory_files_count,
                "状态": "活跃"
            })
        else:
            st.info("等待初始化")
    
    with col3:
        st.markdown("**❤️ 好感度数据**")
        if AFFECTION_DIR.exists():
            affection_files_count = count_json_files(AFFECTION_DIR, "*_affection.json")
            st.success(f"✅ 已加载")
            st.json({
                "存储路径": str(AFFECTION_DIR),
                "用户文件数": affection_files_count,
                "状态": "活跃"
            })
        else:
            st.info("等待初始化")

# ==========================================
# 页面: Provider 管理
# ==========================================

elif page == "🔌 Provider 管理":
    render_page_header(
        "Provider 多模型管理",
        "集中管理多模型 Provider、主 Provider 选择、健康状态检查与临时注册。"
    )
    
    v2_system = init_v2_system()
    
    if not v2_system.get("initialized"):
        st.error("V2 系统未初始化")
    else:
        provider_manager = v2_system["provider_manager"]
        providers = provider_manager.providers

        col1, col2, col3 = st.columns(3)
        with col1:
            render_status_card("已注册 Provider", str(len(providers)), "当前进程内", "blue")
        with col2:
            render_status_card("主 Provider", provider_manager.primary_provider or "未设置", "Primary route", "success" if provider_manager.primary_provider else "warn")
        with col3:
            render_status_card("Fallback 队列", str(len(getattr(provider_manager, "fallback_order", []))), "故障转移顺序", "cyan")
        
        # Provider 列表
        render_panel_title("📋 已注册 Provider")
        
        if not providers:
            render_info_card(
                "暂无已注册 Provider",
                "请检查 <code>.env</code> / <code>PROVIDER_CONFIGS</code>，或在下方临时注册一个 Mock / OpenAI 兼容 Provider。",
                "ℹ️"
            )
        
        for name, provider in providers.items():
            info = provider.get_info()
            is_primary = name == provider_manager.primary_provider
            model_name = getattr(provider, "model", "N/A")
            with st.expander(f"{name} {'· 主 Provider' if is_primary else '· 备用 Provider'}", expanded=True):
                async def check_single(name):
                    provider = provider_manager.providers.get(name)
                    if provider:
                        return await provider.is_available()
                    return False

                is_healthy = asyncio.run(check_single(name))

                col1, col2, col3 = st.columns(3)
                
                with col1:
                    render_status_card("模型", model_name, f"类型：{info.provider_type}", "blue")
                
                with col2:
                    render_status_card("健康状态", "可用" if is_healthy else "不可用", "实时健康检查", "success" if is_healthy else "danger")
                
                with col3:
                    render_status_card("能力", "支持工具调用" if info.supports_tools else "普通对话", "Tool calling", "cyan" if info.supports_tools else "warn")

                action_col1, action_col2 = st.columns([2, 1])
                with action_col1:
                    role_badge = "sus-badge-green" if is_primary else "sus-badge-blue"
                    health_badge = "sus-badge-green" if is_healthy else "sus-badge-red"
                    st.markdown(
                        f"<span class='sus-badge {role_badge}'>{'主 Provider' if is_primary else '备用 Provider'}</span> "
                        f"<span class='sus-badge {health_badge}'>{'Online' if is_healthy else 'Offline'}</span>",
                        unsafe_allow_html=True
                    )
                with action_col2:
                    if is_primary:
                        st.caption("当前主路由")
                    else:
                        if st.button(f"设为主Provider", key=f"primary_{name}"):
                            provider_manager.primary_provider = name
                            provider_manager.fallback_order = [name] + [n for n in provider_manager.fallback_order if n != name]
                            st.success(f"已将 {name} 设为主 Provider（当前进程内生效）")
                            st.rerun()
        
        # 添加新 Provider
        render_panel_title("➕ 添加新 Provider")
        render_info_card(
            "临时注册说明",
            "此处注册的 Provider 在当前 Streamlit 进程内生效。若需要持久化配置，建议同步更新 <code>.env</code> 或 Provider 配置。",
            "🧩"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_provider_name = st.text_input("Provider 名称", key="new_prov_name")
            new_provider_type = st.selectbox(
                "Provider 类型",
                ["openai", "deepseek", "qwen", "mock"],
                key="new_prov_type"
            )
        
        with col2:
            new_provider_model = st.text_input("模型名称", "gpt-3.5-turbo", key="new_prov_model")
            new_provider_key = st.text_input("API Key", type="password", key="new_prov_key")
        
        new_is_primary = st.checkbox("设为主Provider", key="new_prov_primary")
        
        if st.button("注册 Provider", type="primary"):
            if new_provider_name and (new_provider_key or new_provider_type == "mock"):
                try:
                    from core.providers.openai_provider import OpenAIProvider, DeepSeekProvider, QwenProvider
                    from core.providers.mock_provider import MockProvider
                    
                    # 根据类型创建
                    if new_provider_type == "mock":
                        provider = MockProvider(model=new_provider_model or "mock-sandbox")
                    elif new_provider_type == "deepseek":
                        provider = DeepSeekProvider(api_key=new_provider_key, model=new_provider_model)
                    elif new_provider_type == "qwen":
                        provider = QwenProvider(api_key=new_provider_key, model=new_provider_model)
                    else:
                        provider = OpenAIProvider(api_key=new_provider_key, model=new_provider_model)
                    
                    provider_manager.register_provider(
                        new_provider_name, 
                        provider, 
                        is_primary=new_is_primary
                    )
                    st.success(f"✅ Provider {new_provider_name} 注册成功")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 注册失败: {e}")
            else:
                st.warning("请填写完整信息")

# ==========================================
# 页面: 沙盒测试
# ==========================================

elif page == "🧪 沙盒测试":
    render_page_header(
        "离线沙盒测试",
        "使用 MockProvider 验证回复生成、三层记忆和好感度流程；不调用真实 API，也不会向 Flarum 发帖。"
    )

    render_info_card(
        "安全边界",
        "沙盒测试只写入 <code>data/sandbox/memory</code> 和 <code>data/sandbox/affection</code>，默认测试结束后清理运行数据，仅保留报告。",
        "🛡️"
    )

    cases = load_sandbox_cases()
    latest_report = get_latest_sandbox_report()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_status_card("测试用例", str(len(cases)), "tests/sandbox_cases.json", "blue")
    with col2:
        render_status_card("最近通过", str(latest_report.get("passed_cases", "—") if latest_report else "—"), "Passed cases", "success")
    with col3:
        failed_count = latest_report.get("failed_cases", "—") if latest_report else "—"
        render_status_card("最近失败", str(failed_count), "Failed cases", "danger" if failed_count not in (0, "—") else "warn")
    with col4:
        render_status_card("沙盒报告", str(count_json_files(SANDBOX_REPORT_DIR) if SANDBOX_REPORT_DIR.exists() else 0), "data/sandbox/reports", "cyan")

    render_panel_title("▶️ 运行测试")

    case_options = ["全部用例"] + [case.get("id", "unknown") for case in cases]
    selected_case = st.selectbox("选择要运行的用例", case_options)
    keep_data = st.checkbox("测试结束后保留沙盒 memory/affection 数据", value=False)

    if st.button("运行沙盒测试", type="primary", use_container_width=True):
        with st.spinner("正在运行沙盒测试..."):
            try:
                result = run_sandbox_command(
                    case_id=None if selected_case == "全部用例" else selected_case,
                    keep_data=keep_data
                )
                if result.returncode == 0:
                    st.success("✅ 沙盒测试通过")
                else:
                    st.error(f"❌ 沙盒测试失败，退出码: {result.returncode}")
                with st.expander("查看命令输出", expanded=result.returncode != 0):
                    st.code(result.stdout or "", language="text")
                    if result.stderr:
                        st.code(result.stderr, language="text")
                st.rerun()
            except subprocess.TimeoutExpired:
                st.error("沙盒测试超时，请检查脚本或环境。")
            except Exception as e:
                st.error(f"运行沙盒测试失败: {e}")

    render_panel_title("📋 测试用例")
    if cases:
        st.dataframe([
            {
                "id": case.get("id"),
                "说明": case.get("description", ""),
                "用户": case.get("user_id", ""),
                "消息数": len(case.get("messages", [])),
            }
            for case in cases
        ], use_container_width=True)
    else:
        st.info("暂无沙盒测试用例。")

    render_panel_title("📈 最近测试报告")
    latest_report = get_latest_sandbox_report()
    if latest_report:
        status = "✅ PASS" if latest_report.get("failed_cases", 1) == 0 else "❌ FAIL"
        st.markdown(f"**状态**: {status}")
        st.caption(latest_report.get("_path", ""))
        results = latest_report.get("results", [])
        if results:
            st.dataframe([
                {
                    "case": item.get("id"),
                    "结果": "PASS" if item.get("passed") else "FAIL",
                    "用户": item.get("user_id"),
                    "记忆轮数": item.get("profile", {}).get("memory", {}).get("total_turns"),
                    "好感度": item.get("profile", {}).get("affection", {}).get("score"),
                }
                for item in results
            ], use_container_width=True)
            for item in results:
                with st.expander(f"{item.get('id')} 详情", expanded=False):
                    for turn in item.get("turns", []):
                        st.markdown(f"**👤 用户**: {turn.get('user')}")
                        st.markdown(f"**🐱 回复**: {turn.get('assistant')}")
                        st.caption(f"Provider={turn.get('provider')} | Model={turn.get('model')} | memory_saved={turn.get('memory_saved')}")
                        st.divider()
        else:
            st.info("报告中暂无 case 详情。")
    else:
        st.info("暂无沙盒测试报告，请先运行一次测试。")

# ==========================================
# 页面: 世界书编辑 (V3 多世界书系统)
# ==========================================

elif page == "📖 世界书编辑":
    render_page_header(
        "世界书编辑器 V3",
        "以多世界书结构管理角色知识、触发关键词与插入策略；支持世界书与条目的独立启用/禁用。"
    )
    render_info_card(
        "层级与开关机制",
        "<b>世界书</b> 是条目的集合容器，<b>条目</b> 是关键词与内容规则。世界书禁用时，其下所有条目不生效；世界书启用但条目禁用时，仅该条目不生效。",
        "📚"
    )
    
    # 初始化世界书管理器
    if "wb_manager" not in st.session_state:
        st.session_state.wb_manager = WorldBookManager(DATA_DIR)
    
    manager = st.session_state.wb_manager
    
    # 自动迁移旧格式
    legacy_data = load_world_book_legacy(DATA_DIR)
    if legacy_data and "entries" in legacy_data and not manager.list_worldbooks():
        st.info("🔄 检测到旧格式世界书，正在自动迁移到 V3...")
        if migrate_to_v3(manager, legacy_data):
            st.success("✅ 迁移完成")
            st.rerun()

    worldbooks = manager.list_worldbooks()
    total_entries = sum(wb.get("entry_count", 0) for wb in worldbooks)
    enabled_worldbooks = sum(1 for wb in worldbooks if wb.get("enabled", True))

    wb_stat_col1, wb_stat_col2, wb_stat_col3 = st.columns(3)
    with wb_stat_col1:
        render_status_card("世界书数量", str(len(worldbooks)), "Worldbooks", "blue")
    with wb_stat_col2:
        render_status_card("条目总数", str(total_entries), "Entries", "cyan")
    with wb_stat_col3:
        render_status_card("启用世界书", str(enabled_worldbooks), "Enabled", "success" if enabled_worldbooks else "warn")
    
    # ============ 世界书列表侧边栏 ============
    col_main, col_sidebar = st.columns([3, 1])
    
    with col_sidebar:
        render_panel_title("📚 世界书列表")
        
        # 创建新世界书
        with st.expander("➕ 新建世界书", expanded=False):
            new_wb_name = st.text_input("名称", key="new_wb_name")
            new_wb_desc = st.text_area("描述", key="new_wb_desc", height=60)
            if st.button("创建", key="create_wb"):
                if new_wb_name:
                    wb = manager.create_worldbook(new_wb_name, new_wb_desc)
                    st.success(f"✅ 已创建: {new_wb_name}")
                    st.rerun()
        
        if not worldbooks:
            st.info("暂无世界书，请创建")
        else:
            for wb in worldbooks:
                wb_id = wb["id"]
                
                # 世界书行
                col_toggle, col_expand, col_name = st.columns([0.3, 0.3, 2])
                
                with col_toggle:
                    # 世界书开关
                    is_enabled = wb.get("enabled", True)
                    toggle_label, toggle_help = get_worldbook_light(is_enabled)
                    if st.button(toggle_label, key=f"wb_toggle_{wb_id}", help=f"{toggle_help}；点击切换启用/禁用"):
                        manager.set_worldbook_enabled(wb_id, not is_enabled)
                        st.rerun()
                
                with col_expand:
                    # 展开/折叠按钮
                    is_expanded = wb.get("expanded", False)
                    expand_icon = "▼" if is_expanded else "▶"
                    if st.button(expand_icon, key=f"wb_expand_{wb_id}"):
                        # 切换展开状态
                        full_wb = manager.load_worldbook(wb_id)
                        if full_wb:
                            full_wb["expanded"] = not is_expanded
                            manager.save_worldbook(full_wb)
                            st.rerun()
                
                with col_name:
                    wb_status_class = "sus-badge-green" if wb.get("enabled", True) else "sus-badge-orange"
                    wb_status_text = "启用" if wb.get("enabled", True) else "禁用"
                    st.markdown(
                        f"**{_safe_html(wb['name'])}**<br/>"
                        f"<span class='sus-badge {wb_status_class}'>{wb_status_text}</span>",
                        unsafe_allow_html=True
                    )
                    st.caption(f"{wb['entry_count']} 条目")
                
                # 展开的条目列表
                if is_expanded:
                    full_wb = manager.load_worldbook(wb_id)
                    if full_wb:
                        for entry in full_wb.get("entries", []):
                            entry_uid = entry.get("uid", "")
                            entry_title = entry.get("comment", "未命名")
                            entry_enabled = entry.get("enabled", True)
                            entry_light, entry_status_text, entry_help = get_entry_light(entry)
                            
                            entry_col1, entry_col2 = st.columns([0.5, 2])
                            with entry_col1:
                                if st.button(entry_light, key=f"entry_toggle_{entry_uid}", help=f"{entry_help}；点击切换开启/关闭"):
                                    manager.set_entry_enabled(wb_id, entry_uid, not entry_enabled)
                                    st.rerun()
                            with entry_col2:
                                entry_class = "" if entry_enabled else "opacity: 0.5;"
                                entry_badge_class = "sus-badge-blue" if entry.get("constant", False) else "sus-badge-green"
                                if not entry_enabled:
                                    entry_badge_class = "sus-badge-orange"
                                st.markdown(
                                    f"<span style='{entry_class}'>{_safe_html(entry_title)}</span> "
                                    f"<span class='sus-badge {entry_badge_class}'>{_safe_html(entry_status_text)}</span>",
                                    unsafe_allow_html=True
                                )
                
                st.divider()
        
        # 删除世界书
        if worldbooks:
            render_panel_title("危险操作")
            del_wb_id = st.selectbox(
                "删除世界书",
                options=[""] + [wb["id"] for wb in worldbooks],
                format_func=lambda x: next((wb["name"] for wb in worldbooks if wb["id"] == x), "选择...") if x else "选择要删除的世界书..."
            )
            if del_wb_id and st.button("🗑️ 删除", type="secondary"):
                if manager.delete_worldbook(del_wb_id):
                    st.success("✅ 已删除")
                    st.rerun()
    
    # ============ 主编辑区 ============
    with col_main:
        # 选择要编辑的世界书
        if worldbooks:
            render_panel_title("🧭 当前编辑对象")
            selected_wb_id = st.selectbox(
                "选择要编辑的世界书",
                options=[wb["id"] for wb in worldbooks],
                format_func=lambda x: next((wb["name"] for wb in worldbooks if wb["id"] == x), x)
            )
            
            if selected_wb_id:
                wb = manager.load_worldbook(selected_wb_id)
                
                if wb:
                    selected_entry_count = len(wb.get("entries", []))
                    selected_enabled_count = sum(1 for entry in wb.get("entries", []) if entry.get("enabled", True))
                    sel_col1, sel_col2, sel_col3 = st.columns(3)
                    with sel_col1:
                        render_status_card("当前世界书", wb.get("name", "未命名"), "Selected", "blue")
                    with sel_col2:
                        render_status_card("条目数量", str(selected_entry_count), "Entries", "cyan")
                    with sel_col3:
                        render_status_card("启用条目", str(selected_enabled_count), "Enabled entries", "success" if selected_enabled_count else "warn")

                    # 世界书基本信息
                    with st.expander("📝 世界书信息", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            wb["name"] = st.text_input("名称", wb.get("name", ""), key=f"wb_name_{selected_wb_id}")
                        with col2:
                            wb["description"] = st.text_input("描述", wb.get("description", ""), key=f"wb_desc_{selected_wb_id}")
                        
                        if st.button("💾 保存信息", key=f"save_wb_{selected_wb_id}"):
                            manager.save_worldbook(wb)
                            st.success("✅ 已保存")
                    
                    # 添加新条目
                    render_panel_title("➕ 添加新条目")
                    with st.expander("➕ 添加新条目", expanded=False):
                        entry_col1, entry_col2 = st.columns(2)
                        
                        with entry_col1:
                            new_comment = st.text_input("条目标题", key=f"new_comment_{selected_wb_id}")
                            new_keys = st.text_input(
                                "关键词 (逗号分隔)",
                                key=f"new_keys_{selected_wb_id}",
                                help="例如: 魔法, 法术, 咒语"
                            )
                        
                        with entry_col2:
                            new_order = st.number_input("优先级", min_value=1, max_value=9999, value=100, key=f"new_order_{selected_wb_id}")
                            new_position = st.selectbox(
                                "插入位置",
                                [("Before Char", 0), ("After Char", 1), ("AN Top", 2), ("AN Bottom", 3), ("At Depth", 4)],
                                format_func=lambda x: x[0],
                                key=f"new_pos_{selected_wb_id}"
                            )[1]
                        
                        new_content = st.text_area(
                            "条目内容 (发送给 LLM)",
                            height=150,
                            key=f"new_content_{selected_wb_id}"
                        )
                        
                        # 高级选项
                        with st.expander("⚙️ 高级选项"):
                            adv_col1, adv_col2, adv_col3 = st.columns(3)
                            with adv_col1:
                                new_selective = st.checkbox("启用次级关键词", key=f"new_selective_{selected_wb_id}")
                                new_secondary = st.text_input("次级关键词", key=f"new_secondary_{selected_wb_id}")
                            with adv_col2:
                                new_probability = st.slider("触发概率", 0, 100, 100, key=f"new_prob_{selected_wb_id}")
                                new_depth = st.number_input("扫描深度", 1, 20, 4, key=f"new_depth_{selected_wb_id}")
                            with adv_col3:
                                new_constant = st.checkbox("常驻模式", key=f"new_constant_{selected_wb_id}")
                                new_exclude_recursion = st.checkbox("不参与递归", key=f"new_exclude_{selected_wb_id}")
                        
                        if st.button("✅ 添加条目", type="primary", key=f"add_entry_btn_{selected_wb_id}"):
                            if new_comment and new_content:
                                entry_data = {
                                    "comment": new_comment,
                                    "content": new_content,
                                    "keysStr": new_keys,
                                    "order": new_order,
                                    "position": new_position,
                                    "selective": new_selective,
                                    "keysecondary": [k.strip() for k in new_secondary.split(",") if k.strip()] if new_secondary else [],
                                    "probability": new_probability,
                                    "depth": new_depth,
                                    "constant": new_constant,
                                    "excludeRecursion": new_exclude_recursion
                                }
                                new_entry = manager.add_entry(selected_wb_id, entry_data)
                                if new_entry:
                                    st.success(f"✅ 已添加: {new_comment}")
                                    st.rerun()
                                else:
                                    st.error("❌ 添加失败")
                            else:
                                st.warning("请填写标题和内容")
                    
                    # 条目列表
                    render_panel_title(f"📄 {wb['name']} 的条目")
                    
                    entries = wb.get("entries", [])
                    if not entries:
                        st.info("暂无条目，请添加")
                    else:
                        # 按优先级排序
                        sorted_entries = sorted(entries, key=lambda x: x.get("order", 0), reverse=True)
                        
                        for entry in sorted_entries:
                            entry_uid = entry.get("uid", "")
                            entry_comment = entry.get("comment", "未命名")
                            entry_enabled = entry.get("enabled", True)
                            entry_constant = entry.get("constant", False)
                            entry_order = entry.get("order", 100)
                            
                            with st.expander(f"{entry_comment} (优先级: {entry_order})", expanded=False):
                                edit_col1, edit_col2 = st.columns([3, 1])
                                
                                with edit_col1:
                                    # 编辑表单
                                    e_col1, e_col2 = st.columns(2)
                                    with e_col1:
                                        edit_comment = st.text_input("标题", entry.get("comment", ""), key=f"edit_comment_{entry_uid}")
                                        edit_keys = st.text_input(
                                            "关键词",
                                            value=", ".join(entry.get("key", [])),
                                            key=f"edit_keys_{entry_uid}"
                                        )
                                    with e_col2:
                                        edit_order = st.number_input("优先级", 1, 9999, entry.get("order", 100), key=f"edit_order_{entry_uid}")
                                        edit_enabled = st.checkbox("启用", entry_enabled, key=f"edit_enabled_{entry_uid}")
                                        edit_constant = st.checkbox("常驻模式 (constant)", entry_constant, key=f"edit_constant_{entry_uid}")
                                    
                                    edit_content = st.text_area("内容", entry.get("content", ""), height=120, key=f"edit_content_{entry_uid}")
                                    
                                    if st.button("💾 保存修改", key=f"save_entry_{entry_uid}"):
                                        updates = {
                                            "comment": edit_comment,
                                            "content": edit_content,
                                            "keysStr": edit_keys,
                                            "order": edit_order,
                                            "enabled": edit_enabled,
                                            "constant": edit_constant
                                        }
                                        if manager.update_entry(selected_wb_id, entry_uid, updates):
                                            st.success("✅ 已保存")
                                            st.rerun()
                                
                                with edit_col2:
                                    st.markdown("**操作**")
                                    
                                    # 开关状态显示
                                    preview_entry = {**entry, "enabled": edit_enabled, "constant": edit_constant}
                                    _, status_text, status_help = get_entry_light(preview_entry)
                                    st.markdown(f"**状态：** {status_text}")
                                    st.caption(status_help)
                                    
                                    if st.button("🗑️ 删除", key=f"del_entry_{entry_uid}", type="secondary"):
                                        manager.delete_entry(selected_wb_id, entry_uid)
                                        st.success("✅ 已删除")
                                        st.rerun()
                else:
                    st.error("无法加载世界书")
        else:
            st.info("👈 请在左侧创建或选择一个世界书")

# ==========================================
# 页面: 三层记忆管理
# ==========================================

elif page == "🧠 三层记忆":
    st.title("🧠 三层记忆系统管理")
    st.markdown("""
    **L1 摘要层** | **L2 块层 (10轮)** | **L3 历史层**
    
    三层架构实现长期记忆的动态管理
    """)
    
    v2_system = init_v2_system()
    
    if not v2_system.get("initialized"):
        st.error("V2 系统未初始化")
    else:
        memory = v2_system["memory"]
        
        # 用户选择
        st.subheader("👤 选择用户")
        
        # 获取所有用户
        try:
            async def get_memory_user_ids():
                return await memory.get_all_user_ids()

            user_ids = asyncio.run(get_memory_user_ids())
            
            if not user_ids:
                st.info("暂无记忆数据。V2 记忆文件采用子目录分片存储，正式数据位于 data/memory。")
            else:
                selected_user = st.selectbox("选择用户查看记忆", sorted(user_ids))
                
                if selected_user:
                    # 异步获取统计
                    async def get_user_memory_stats():
                        return await memory.get_user_stats(selected_user)
                    
                    stats = asyncio.run(get_user_memory_stats())
                    
                    # 显示统计
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("总轮数", stats.get("total_turns", 0))
                    with col2:
                        st.metric("总块数", stats.get("total_blocks", 0))
                    with col3:
                        st.metric("摘要数", stats.get("summaries_count", 0))
                    with col4:
                        last_interaction = stats.get("last_interaction", "")
                        st.metric("最后互动", last_interaction[:10] if last_interaction else "N/A")
                    
                    st.markdown("---")
                    
                    # 获取记忆内容
                    async def get_user_memory():
                        return await memory.get_memory_for_prompt(selected_user)
                    
                    prompt_memory = asyncio.run(get_user_memory())
                    
                    # 显示摘要
                    st.subheader("📝 L1 摘要层")
                    summaries = prompt_memory.get("summaries", "")
                    if summaries:
                        st.info(summaries)
                    else:
                        st.info("暂无摘要（需要完成 2 个块后自动生成）")
                    
                    # 显示近期消息
                    st.subheader("💬 L2/L3 近期对话")
                    recent = prompt_memory.get("recent_context", [])
                    if recent:
                        for msg in recent:
                            role = msg.get("role", "unknown")
                            content = msg.get("content", "")
                            timestamp = msg.get("timestamp", "")[11:19] if msg.get("timestamp") else ""
                            
                            if role == "user":
                                st.markdown(f"**👤 用户** ({timestamp}): {content}")
                            else:
                                st.markdown(f"**🐱 AI** ({timestamp}): {content}")
                    else:
                        st.info("暂无近期对话")
                    
                    # 操作
                    st.markdown("---")
                    st.subheader("🛠️ 操作")
                    st.warning("以下操作会影响正式记忆数据；如需安全测试，请使用 🧪 沙盒测试 页面。")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 刷新记忆缓存", type="secondary"):
                            memory.clear_cache()
                            st.success("已清理内存缓存，页面刷新后会重新读取磁盘数据")
                            st.rerun()
                    with col2:
                        confirm_delete = st.checkbox("确认删除该用户正式记忆", key=f"confirm_memory_delete_{selected_user}")
                        if st.button("⚠️ 删除该用户所有记忆", type="primary", disabled=not confirm_delete):
                            async def clear_memory():
                                await memory.clear_user_memory(selected_user)
                            asyncio.run(clear_memory())
                            st.success(f"✅ 已删除用户 {selected_user} 的记忆")
                            st.rerun()
        except Exception as e:
            st.error(f"加载记忆失败: {e}")

# ==========================================
# 页面: 好感度系统
# ==========================================

elif page == "❤️ 好感度系统":
    st.title("❤️ 好感度系统管理")
    st.markdown("""
    **5级关系系统**: 陌生人 → 熟人 → 朋友 → 挚友 → 羁绊
    
    基于互动类型智能计算好感度
    """)
    
    v2_system = init_v2_system()
    
    if not v2_system.get("initialized"):
        st.error("V2 系统未初始化")
    else:
        affection = v2_system["affection"]
        
        # 全局统计
        st.subheader("📊 全局统计")
        
        try:
            # 获取所有用户（V2 好感度文件采用子目录分片存储）
            user_files = list(AFFECTION_DIR.rglob("*_affection.json"))
            top_users = asyncio.run(affection.get_top_users(100))
            scores = [u.get("score", 0) for u in top_users]
            avg_score = sum(scores) / len(scores) if scores else 0
            highest_level = top_users[0].get("level", "N/A") if top_users else "N/A"
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总用户数", len(user_files))
            with col2:
                st.metric("平均好感度", f"{avg_score:.1f}" if scores else "N/A")
            with col3:
                st.metric("最高等级", highest_level)

            if top_users:
                st.subheader("🏅 好感度排行")
                st.dataframe(top_users[:20], use_container_width=True)
            
            st.markdown("---")
            
            # 用户详情
            st.subheader("👤 用户好感度详情")
            
            if user_files:
                user_ids = [f.stem.replace("_affection", "") for f in user_files]
                selected_user = st.selectbox("选择用户", sorted(user_ids))
                
                if selected_user:
                    # 异步获取数据
                    async def get_affection_data():
                        summary = await affection.get_affection_summary(selected_user)
                        detail = await affection.get_user_affection(selected_user)
                        return summary, detail
                    
                    summary, detail = asyncio.run(get_affection_data())
                    level = detail.level
                    history = list(reversed(detail.interaction_history[-10:]))
                    
                    # 显示等级信息
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("当前等级", level.label)
                    with col2:
                        st.metric("好感度", summary.get("score", 0))
                    with col3:
                        progress = summary.get("level_progress", 0) * 100
                        st.metric("升级进度", f"{progress:.1f}%")
                    with col4:
                        st.metric("互动次数", summary.get("total_interactions", 0))
                    
                    # 进度条
                    st.progress(summary.get("level_progress", 0))
                    
                    # 互动历史
                    st.subheader("📜 最近互动")
                    
                    if history:
                        for record in history:
                            with st.container():
                                col1, col2 = st.columns([1, 3])
                                with col1:
                                    st.markdown(f"**{record.get('timestamp', '')[:10]}**")
                                    st.markdown(f"类型: `{record.get('type', 'unknown')}`")
                                    st.markdown(f"得分: +{record.get('points', 0)}")
                                with col2:
                                    metadata = record.get("metadata", {})
                                    st.markdown(f"**分数后**: {record.get('score_after', 0)}")
                                    if metadata:
                                        st.json(metadata)
                    else:
                        st.info("暂无互动记录")
                    
                    # 成就
                    st.subheader("🏆 成就")
                    achievements = detail.achievements
                    if achievements:
                        for ach in achievements:
                            st.success(f"✅ {ach}")
                    else:
                        st.info("暂无成就")
            else:
                st.info("暂无用户数据")
        
        except Exception as e:
            st.error(f"加载好感度数据失败: {e}")

# ==========================================
# 页面: 系统配置
# ==========================================

elif page == "⚙️ 系统配置":
    st.title("⚙️ 系统配置")
    st.markdown("编辑 `.env` 环境变量配置 (V2 版本)")
    
    env_data = load_env()
    
    if not env_data and ENV_EXAMPLE_PATH.exists():
        st.info("从 .env.example 加载默认配置")
        with open(ENV_EXAMPLE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _ = line.split('=', 1)
                    env_data[key] = ""
    
    # LLM 配置
    st.subheader("🧠 大模型配置")
    col1, col2 = st.columns(2)
    
    with col1:
        env_data["LLM_API_KEY"] = st.text_input(
            "API Key",
            value=env_data.get("LLM_API_KEY", ""),
            type="password"
        )
        env_data["LLM_BASE_URL"] = st.text_input(
            "API 基础地址",
            value=env_data.get("LLM_BASE_URL", "https://api.openai.com/v1")
        )
    
    with col2:
        env_data["LLM_MODEL"] = st.text_input(
            "模型名称",
            value=env_data.get("LLM_MODEL", "gpt-3.5-turbo")
        )
    
    env_data["SYSTEM_PROMPT"] = st.text_area(
        "系统人设 Prompt",
        value=env_data.get("SYSTEM_PROMPT", ""),
        height=100
    )
    
    # V2 新增配置
    st.markdown("---")
    st.subheader("🆕 V2 新增配置")
    
    col1, col2 = st.columns(2)
    with col1:
        env_data["DASHSCOPE_API_KEY"] = st.text_input(
            "通义千问 Embedding API Key",
            value=env_data.get("DASHSCOPE_API_KEY", ""),
            type="password",
            help="用于语义检索的 Embedding 模型"
        )
    with col2:
        env_data["BGE_MODEL_PATH"] = st.text_input(
            "BGE 模型路径",
            value=env_data.get("BGE_MODEL_PATH", ""),
            help="本地 BGE-M3 模型路径（可选）"
        )
    
    # 记忆系统配置
    st.markdown("---")
    st.subheader("🧠 三层记忆配置")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        env_data["MEMORY_BLOCK_SIZE"] = str(st.number_input(
            "每块对话轮数",
            value=int(env_data.get("MEMORY_BLOCK_SIZE", "10")),
            min_value=5,
            max_value=50
        ))
    with col2:
        env_data["SUMMARY_TRIGGER_THRESHOLD"] = str(st.number_input(
            "摘要触发阈值（块数）",
            value=int(env_data.get("SUMMARY_TRIGGER_THRESHOLD", "2")),
            min_value=1,
            max_value=10
        ))
    with col3:
        env_data["MAX_CONTEXT_MESSAGES"] = str(st.number_input(
            "最大上下文消息数",
            value=int(env_data.get("MAX_CONTEXT_MESSAGES", "5")),
            min_value=1,
            max_value=20
        ))
    
    # 好感度配置
    st.markdown("---")
    st.subheader("❤️ 好感度系统配置")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        env_data["DAILY_BONUS_POINTS"] = str(st.number_input(
            "每日首次互动奖励",
            value=int(env_data.get("DAILY_BONUS_POINTS", "5")),
            min_value=0,
            max_value=50
        ))
    with col2:
        env_data["CONSECUTIVE_BONUS_POINTS"] = str(st.number_input(
            "连续互动奖励",
            value=int(env_data.get("CONSECUTIVE_BONUS_POINTS", "10")),
            min_value=0,
            max_value=50
        ))
    with col3:
        env_data["EMOTIONAL_SUPPORT_BONUS"] = str(st.number_input(
            "情感支持额外奖励",
            value=int(env_data.get("EMOTIONAL_SUPPORT_BONUS", "5")),
            min_value=0,
            max_value=50
        ))
    
    # 保存按钮
    st.markdown("---")
    if st.button("💾 保存配置", type="primary", use_container_width=True):
        if save_env(env_data):
            st.success("✅ 配置已保存到 .env")
            st.info("📝 重启服务后配置生效")

# ==========================================
# 页面: 冷却监控
# ==========================================

elif page == "⏱️ 冷却监控":
    st.title("⏱️ 用户冷却监控")
    st.markdown("查看和管理用户回复冷却状态")
    
    try:
        sys.path.insert(0, str(BASE_DIR))
        from core.cooldown_manager import cooldown_manager
        
        cooldowns = cooldown_manager.get_all_cooldowns()
        
        if cooldowns:
            st.subheader("📋 冷却状态列表")
            
            for user_id, info in cooldowns.items():
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                
                with col1:
                    st.code(user_id)
                with col2:
                    status_color = "🟢" if info["can_reply"] else "🔴"
                    st.markdown(f"{status_color} {info['status']}")
                with col3:
                    if not info["can_reply"]:
                        st.markdown(f"⏳ {info['remaining_seconds']}秒")
                with col4:
                    if st.button("清除", key=f"clear_{user_id}"):
                        cooldown_manager.clear_cooldown(user_id)
                        st.success(f"已清除 {user_id} 的冷却状态")
                        st.rerun()
        else:
            st.info("暂无冷却记录")
        
        # 白名单管理
        st.markdown("---")
        st.subheader("📝 白名单管理")
        
        new_whitelist = st.text_input("添加用户到白名单（输入用户ID）")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 添加到白名单"):
                if new_whitelist:
                    cooldown_manager.add_to_whitelist(new_whitelist)
                    st.success(f"已添加 {new_whitelist} 到白名单")
        
        with col2:
            if st.button("➖ 从白名单移除"):
                if new_whitelist:
                    cooldown_manager.remove_from_whitelist(new_whitelist)
                    st.success(f"已移除 {new_whitelist} 从白名单")
    
    except Exception as e:
        st.error(f"加载冷却管理器失败: {str(e)}")

# ==========================================
# 页脚
# ==========================================

st.markdown("---")
st.caption("🐱 Flarum AI Agent V2 - Provider + 三层记忆 + 好感度系统")