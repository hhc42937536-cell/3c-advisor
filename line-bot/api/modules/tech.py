"""
3C 推薦、硬體升級諮詢、導引式問卷、規格說明、購買指南模組
=============================================================
從 webhook.py 萃取的獨立模組，保留所有產品推薦邏輯。
"""


from modules.tech_wizard import build_scenario_menu
from modules.tech_wizard import build_wizard_budget
from modules.tech_wizard import build_wizard_use
from modules.tech_wizard import build_wizard_who
from modules.tech_wizard import parse_wizard_state
from modules.tech_upgrade import build_upgrade_gpu
from modules.tech_upgrade import build_upgrade_menu
from modules.tech_upgrade import build_upgrade_message
from modules.tech_upgrade import build_upgrade_performance_check
from modules.tech_upgrade import build_upgrade_ram
from modules.tech_upgrade import build_upgrade_ssd
from modules.tech_guides import build_compare_price_message
from modules.tech_guides import build_purchase_guide_message
from modules.tech_guides import build_spec_explainer
from modules.tech_products import DEVICE_KEYWORDS
from modules.tech_products import LINE_BOT_ID
from modules.tech_products import PRODUCTS_URL
from modules.tech_products import USE_KEYWORDS
from modules.tech_products import build_product_flex
from modules.tech_products import build_recommendation_message
from modules.tech_products import build_suitability_message
from modules.tech_products import detect_device
from modules.tech_products import detect_use
from modules.tech_products import filter_products
from modules.tech_products import load_products
from modules.tech_products import parse_budget
from modules.tech_products import spec_to_plain_line

# ─── 產品資料來源 ─────────────────────────────────

# LINE Bot ID（用於分享邀請連結）

# ─── 產品資料快取 ─────────────────────────────────


# ─── 3C 推薦模組 ─────────────────────────────────

# 關鍵字 → 裝置類別（laptop 放最前，避免 vivobook 被 vivo(phone) 誤判）

# 關鍵字 → 用途偏好


# ─── 硬體升級諮詢 ─────────────────────────────────────


# ─── 導引式問卷（狀態用 | 編碼）────────────────────
# 格式：裝置|使用者|用途|預算
# 例如：手機|長輩|拍照|20000
# 每一步從按鈕中累積，直到 4 個欄位齊全才顯示推薦


# ─── 購買指南 & 比價 ──────────────────────────────


