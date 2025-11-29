"""
title: Investigation Mock APIs
author: OneCloudTech Demo
description: Mock APIs for basic info, location, contacts, CDR, and company registration, for Open WebUI tool demo.
version: 1.0.0
"""

# ================================================================
# 说明（仅给开发者看，用户看不到）：
# 1. 这是一个 Open WebUI 合规的 Tools 插件文件
# 2. 放置路径建议为：
#       backend/open_webui/extensions/tools/investigation_mock_apis.py
# 3. 重启 Open WebUI 后即可在 Workspace → Tools 中启用
#
# 4. 所有接口均为 Mock（模拟数据）
# 5. 如果参数缺失，会返回统一格式的错误，供 LLM 提示用户补齐参数
# 6. ⚠ 所有对外交互内容（描述、message、ask_user_prompt、字段值等）均为英文
# ================================================================

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ================================================================
# 工具主类（必须叫 Tools）
# ================================================================
class Tools:
    """
    Investigation Mock Tools:
    Simulate 5 query APIs that the LLM can call based on user intent.

    APIs:
        - get_basic_info      Query basic person information
        - get_location_info   Query location information
        - get_contacts        Query contacts list
        - get_cdr             Query call detail records (CDR)
        - get_company_info    Query company registration information

    Unified response format:

        Success:
        {
            "code": 0,
            "message": "ok",
            "data": {...}
        }

        Missing parameters (LLM should ask user to fill them):
        {
            "code": 4001,
            "message": "...",
            "missing_params": [...],
            "ask_user_prompt": "Please provide ..."
        }
    """

    # ------------------------------------------------------------
    # 全局 Valves 配置，可在 Open WebUI 的前端控制台动态修改
    # ------------------------------------------------------------
    class Valves(BaseModel):
        # demo_mode 用于未来扩展（是否读取真实 API）
        demo_mode: bool = Field(
            True,
            description="If true, use mock data only (no real external APIs)."
        )

    def __init__(self):
        # 自动加载 Valves 配置
        self.valves = self.Valves()

    # ============================================================
    # 内部：构造统一格式成功返回
    # ============================================================
    @staticmethod
    def _ok(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "code": 0,
            "message": "ok",
            "data": data
        }

    # ============================================================
    # 内部：构造统一格式错误返回（参数缺失用）
    # ============================================================
    @staticmethod
    def _err(message: str, missing: List[str], ask: str) -> Dict[str, Any]:
        return {
            "code": 4001,
            "message": message,
            "data": None,
            "missing_params": missing,
            "ask_user_prompt": ask
        }

    # ============================================================
    # 1. 查询基本信息
    # ============================================================
    def get_basic_info(
        self,
        phone: Optional[str] = None,
        id_no: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query basic person information (mock).
        At least one of `phone` or `id_no` is required.
        """

        if not phone and not id_no:
            return self._err(
                "Missing required identifier: you must provide 'phone' or 'id_no'.",
                ["phone", "id_no"],
                "To query basic information, please provide either a phone number or an ID number."
            )

        # ——模拟数据（mock data）——
        data = {
            "name": "Zhang Wei",
            "gender": "M",
            "birthday": "1990-05-20",
            "id_no": id_no or "ID202511290001",
            "phones": [phone] if phone else ["96890001122", "96890003344"],
            "address": "Muscat, Oman",
            "tags": ["high_priority", "frequent_contacts"],
            "last_update_time": "2025-11-29 10:30:00",
            "query_id": query_id or "mock-basic-req-001",
        }
        return self._ok(data)

    # ============================================================
    # 2. 查询位置信息
    # ============================================================
    def get_location_info(
        self,
        phone: Optional[str] = None,
        id_no: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Query location information (mock).
        At least one of `phone` or `id_no` is required.
        """

        if not phone and not id_no:
            return self._err(
                "Missing required identifier: you must provide 'phone' or 'id_no'.",
                ["phone", "id_no"],
                "To query location information, please provide either a phone number or an ID number."
            )

        # ——模拟数据（mock data）——
        data = {
            "target": {
                "phone": phone or "96890001122",
                "id_no": id_no or "ID202511290001",
                "name": "Zhang Wei",
            },
            "query_time_range": {
                "start_time": start_time or "2025-11-01 00:00:00",
                "end_time": end_time or "2025-11-29 23:59:59",
            },
            "points": [
                {
                    "time": "2025-11-28 09:15:00",
                    "lat": 23.5880,
                    "lon": 58.3829,
                    "city": "Muscat",
                    "address": "Muscat City Center Mall",
                    "type": "cell_tower",
                },
                {
                    "time": "2025-11-28 20:30:00",
                    "lat": 23.6150,
                    "lon": 58.5450,
                    "city": "Muscat",
                    "address": "Home Location",
                    "type": "wifi",
                },
            ][:limit]
        }
        return self._ok(data)

    # ============================================================
    # 3. 查询联系人列表
    # ============================================================
    def get_contacts(
        self,
        phone: Optional[str] = None,
        id_no: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Query contacts list (mock).
        At least one of `phone` or `id_no` is required.
        """

        if not phone and not id_no:
            return self._err(
                "Missing required identifier: you must provide 'phone' or 'id_no'.",
                ["phone", "id_no"],
                "To query contacts, please provide either a phone number or an ID number."
            )

        data = {
            "owner": {
                "phone": phone or "96890001122",
                "id_no": id_no or "ID202511290001",
                "name": "Zhang Wei",
            },
            "contacts": [
                {
                    "name": "Li Hua",
                    "phone": "96890002233",
                    "relation": "colleague",
                    "total_calls": 56,
                    "total_sms": 12,
                    "last_contact_time": "2025-11-28 21:10:00",
                },
                {
                    "name": "Ahmed",
                    "phone": "96890004455",
                    "relation": "friend",
                    "total_calls": 8,
                    "total_sms": 3,
                    "last_contact_time": "2025-11-20 17:30:00",
                },
            ][:limit]
        }

        return self._ok(data)

    # ============================================================
    # 4. 查询 CDR（通话详单）
    # ============================================================
    def get_cdr(
        self,
        phone: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        direction: str = "all",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Query Call Detail Records (CDR) (mock).
        Parameter `phone` is required.
        """

        if not phone:
            return self._err(
                "Missing required parameter: 'phone'.",
                ["phone"],
                "To query call detail records, please provide the target phone number."
            )

        # ——模拟数据（mock data）——
        all_cdr = [
            {
                "call_id": "CDR202511280001",
                "from": phone,
                "to": "96890002233",
                "start_time": "2025-11-28 10:15:00",
                "duration_sec": 180,
                "direction": "out",
            },
            {
                "call_id": "CDR202511270045",
                "from": "96890003344",
                "to": phone,
                "start_time": "2025-11-27 22:05:30",
                "duration_sec": 60,
                "direction": "in",
            },
        ]

        # 根据方向过滤
        if direction in ("in", "out"):
            cdr_list = [c for c in all_cdr if c["direction"] == direction]
        else:
            cdr_list = all_cdr

        cdr_list = cdr_list[:limit]

        data = {
            "target_phone": phone,
            "query_time_range": {
                "start_time": start_time or "2025-11-20 00:00:00",
                "end_time": end_time or "2025-11-29 23:59:59",
            },
            "direction": direction,
            "cdr_list": cdr_list,
            "summary": {
                "total_calls": len(cdr_list),
                "total_duration_sec": sum(c["duration_sec"] for c in cdr_list)
            }
        }

        return self._ok(data)

    # ============================================================
    # 5. 查询公司注册信息
    # ============================================================
    def get_company_info(
        self,
        reg_no: Optional[str] = None,
        company_name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query company registration information (mock).
        At least one of `reg_no`, `company_name`, or `phone` is required.
        """

        if not reg_no and not company_name and not phone:
            return self._err(
                "Missing required identifier: you must provide 'reg_no' or 'company_name' or 'phone'.",
                ["reg_no", "company_name", "phone"],
                "To query company registration information, please provide at least one of: registration number, company name, or phone number."
            )

        # ——模拟数据（mock data）——
        data = {
            "company_name": company_name or "OneCloudTech LLC",
            "reg_no": reg_no or "CR-2025-001122",
            "status": "Active",
            "legal_person": "Zhang Wei",
            "phone": phone or "+96890001122",
            "address": "Muscat, Oman",
            "industry": "Information Technology Services",
            "establish_date": "2023-06-15",
            "shareholders": [
                {"name": "Zhang Wei", "share_ratio": "60%"},
                {"name": "Ahmed", "share_ratio": "40%"}
            ]
        }

        return self._ok(data)
