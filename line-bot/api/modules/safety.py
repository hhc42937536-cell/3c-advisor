"""
modules/safety.py — 防詐辨識 & 法律常識 & 工具選單模組
包含：
  - FRAUD_PATTERNS 詐騙關鍵字資料庫（2025-2026）
  - analyze_fraud()          文字詐騙風險評分
  - build_fraud_intro()      防詐辨識引導介面
  - build_fraud_trends()     最新詐騙手法 TOP 8
  - build_fraud_result()     詐騙分析結果 Flex
  - LEGAL_QA                 法律問答資料庫
  - build_legal_guide_intro() 法律常識入口
  - build_legal_answer()     特定法律主題說明
  - build_tools_menu()       所有功能磚塊格選單
"""

from __future__ import annotations

from modules.safety_fraud import analyze_fraud
from modules.safety_fraud import build_fraud_intro
from modules.safety_fraud import build_fraud_result
from modules.safety_fraud import build_fraud_trends
from modules.safety_legal import LEGAL_QA
from modules.safety_legal import build_legal_answer
from modules.safety_legal import build_legal_guide_intro
from modules.safety_menu import build_tools_menu


# ════════════════════════════════════════════════
# 防詐辨識模組
# ════════════════════════════════════════════════


# ════════════════════════════════════════════════
# 法律常識模組
# ════════════════════════════════════════════════


# ════════════════════════════════════════════════
# 工具選單
# ════════════════════════════════════════════════

