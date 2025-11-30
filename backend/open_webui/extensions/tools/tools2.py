"""
title: OneCloudTech Unified Mock Tools
author: Your Name
author_url: https://your-company-internal
description: Mock tools for demo: return fake data for people, calls, base DB, location and CDR.
required_open_webui_version: 0.6.0
version: 0.1.0
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class Tools:
    """
    OneCloudTech unified MOCK tools.

    This toolkit does NOT call any real HTTPS API.
    It only returns mock data so that the agent flow can be demonstrated.

    Exposed methods:
    - query_person_basic_info
    - query_call_detail
    - query_db_basic
    - query_location
    - query_cdr

    All methods return a standardized dictionary:
        {
            "ok": bool,
            "message": str,
            "data": Any
        }
    """

    # ===================== 配置占位（目前没用，仅为了之后真实版兼容） =====================
    class Valves(BaseModel):
        # 这里的配置暂时没用，只是为了之后切换到“真实接口版”时可以无缝兼容
        BASE_URL: str = Field(
            "https://mock-api.example.com",
            description="Mock backend base URL (not actually used in this mock version).",
        )
        API_KEY: str = Field(
            "",
            description="Mock API key (not actually used in this mock version).",
        )
        VERIFY_SSL: bool = Field(
            True,
            description="Whether to verify SSL (not used in this mock version).",
        )

    def __init__(self):
        # 虽然是 mock，但仍然初始化 valves，方便之后直接替换为真实实现
        self.valves = self.Valves()

    # ===================== 1. 人员基础信息（模拟数据） =====================

    def query_person_basic_info(
        self,
        person_id: Optional[str] = None,
        id_type: str = "id_card",
        name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        MOCK: Query basic person information by ID number, name and/or phone.

        This mock implementation does NOT call any real API.
        It always returns a fake person record based on the provided parameters.

        Parameters:
            person_id: ID number of the person (e.g., identity card number).
            id_type: Type of ID, e.g. "id_card", "passport", "other".
            name: Person name, optional.
            phone: Phone number, optional.

        Returns:
            Standard dict: { "ok": bool, "message": str, "data": Any }.
        """
        # 简单参数校验：至少有 person_id 或 name + phone 之一
        if not person_id and not (name and phone):
            return {
                "ok": False,
                "message": "Missing required parameters: provide 'person_id', or 'name' and 'phone'. (mock tool)",
                "data": None,
            }

        # 模拟生成一个“人员信息”，将传入的参数回显出来
        mock_person_id = person_id or "MOCK_ID_0001"
        mock_name = name or "Mock User"
        mock_phone = phone or "13800000000"

        person_summary = {
            "personId": mock_person_id,
            "name": mock_name,
            "gender": "M",
            "birthDate": "1990-01-01",
            "idType": id_type,
            "idNumber": mock_person_id,
            "phone": mock_phone,
            "address": "Mock City, Mock District, Mock Street 001",
            "raw": {
                "personId": mock_person_id,
                "name": mock_name,
                "gender": "M",
                "birthDate": "1990-01-01",
                "idType": id_type,
                "idNumber": mock_person_id,
                "phone": mock_phone,
                "address": "Mock City, Mock District, Mock Street 001",
                "source": "MOCK_DATA",
            },
        }

        return {
            "ok": True,
            "message": "Person basic info mock query succeeded.",
            "data": person_summary,
        }

    # ===================== 2. 通话详情（模拟数据） =====================

    def query_call_detail(
        self,
        caller: Optional[str] = None,
        callee: Optional[str] = None,
        phone: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        MOCK: Query call detail records for a given phone or caller/callee pair.

        This mock implementation does NOT call any real API.
        It returns a small list of fake call records.

        Parameters:
            caller: Calling number (A number).
            callee: Called number (B number).
            phone: If only one number is provided, you can use phone instead of caller/callee.
            start_time: Optional start time.
            end_time: Optional end time.
            limit: Maximum number of records to return (ignored in mock; we return 2).

        Returns:
            Standard dict: { "ok": bool, "message": str, "data": Any }.
        """
        # phone / caller / callee 至少要有一个，否则模型就知道是参数不全
        if not caller and not callee and not phone:
            return {
                "ok": False,
                "message": "Missing required parameters: provide 'caller', 'callee' or 'phone'. (mock tool)",
                "data": None,
            }

        # 选择一个主号码用于展示
        base_phone = phone or caller or callee or "10086"

        # 模拟两条通话记录
        records: List[Dict[str, Any]] = [
            {
                "callId": "MOCK_CALL_001",
                "caller": caller or base_phone,
                "callee": callee or "13900000001",
                "startTime": start_time or "2024-10-01 10:00:00",
                "endTime": "2024-10-01 10:05:30",
                "durationSeconds": 330,
                "direction": "outgoing",
                "result": "answered",
                "raw": {"source": "MOCK_DATA"},
            },
            {
                "callId": "MOCK_CALL_002",
                "caller": caller or "13900000002",
                "callee": callee or base_phone,
                "startTime": start_time or "2024-10-01 11:20:00",
                "endTime": "2024-10-01 11:21:10",
                "durationSeconds": 70,
                "direction": "incoming",
                "result": "missed",
                "raw": {"source": "MOCK_DATA"},
            },
        ]

        return {
            "ok": True,
            "message": "Call detail mock query succeeded.",
            "data": records,
        }

    # ===================== 3. 基础库（模拟数据） =====================

    def query_db_basic(
        self,
        id_number: str,
        id_type: str = "id_card",
        db_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        MOCK: Query base database information by ID number.

        This mock implementation does NOT call any real API.
        It returns a fake base database record.

        Parameters:
            id_number: ID number of the person (required).
            id_type: Type of ID, e.g. "id_card", "passport", "other".
            db_type: Optional database type or category (e.g. "blacklist", "customer", etc.).

        Returns:
            Standard dict: { "ok": bool, "message": str, "data": Any }.
        """
        if not id_number:
            return {
                "ok": False,
                "message": "Missing required parameter: 'id_number'. (mock tool)",
                "data": None,
            }

        mock_db_type = db_type or "general"
        # 模拟基础库记录
        data = {
            "idNumber": id_number,
            "idType": id_type,
            "dbType": mock_db_type,
            "riskLevel": "low",
            "tags": ["mock", "demo"],
            "remark": "This is a mock base DB record for demo purpose.",
            "raw": {"source": "MOCK_DATA"},
        }

        return {
            "ok": True,
            "message": "Base DB mock query succeeded.",
            "data": data,
        }

    # ===================== 4. 位置（模拟数据） =====================

    def query_location(
        self,
        phone: Optional[str] = None,
        device_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        MOCK: Query location / trajectory information for a given phone or device ID.

        This mock implementation does NOT call any real API.
        It returns a small list of fake location points.

        Parameters:
            phone: Phone number of the target.
            device_id: Device identifier of the target.
            start_time: Optional start time.
            end_time: Optional end time.
            limit: Maximum number of points or records (ignored in mock; we return 3).

        Returns:
            Standard dict: { "ok": bool, "message": str, "data": Any }.
        """
        if not phone and not device_id:
            return {
                "ok": False,
                "message": "Missing required parameters: provide 'phone' or 'device_id'. (mock tool)",
                "data": None,
            }

        target = phone or device_id or "MOCK_TARGET"

        # 模拟三条轨迹点
        records: List[Dict[str, Any]] = [
            {
                "target": target,
                "time": start_time or "2024-10-01 09:00:00",
                "lat": 23.123456,
                "lon": 113.123456,
                "address": "Mock City - Location A",
                "raw": {"source": "MOCK_DATA"},
            },
            {
                "target": target,
                "time": "2024-10-01 10:30:00",
                "lat": 23.223456,
                "lon": 113.223456,
                "address": "Mock City - Location B",
                "raw": {"source": "MOCK_DATA"},
            },
            {
                "target": target,
                "time": end_time or "2024-10-01 12:00:00",
                "lat": 23.323456,
                "lon": 113.323456,
                "address": "Mock City - Location C",
                "raw": {"source": "MOCK_DATA"},
            },
        ]

        return {
            "ok": True,
            "message": "Location mock query succeeded.",
            "data": records,
        }

    # ===================== 5. CDR（模拟数据） =====================

    def query_cdr(
        self,
        phone: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        MOCK: Query CDR (call detail records) for a phone number.

        This mock implementation does NOT call any real API.
        It returns a fixed set of fake CDR records with pagination info.

        Parameters:
            phone: Phone number (required).
            start_time: Optional start time.
            end_time: Optional end time.
            page: Page index for pagination.
            page_size: Page size for pagination.

        Returns:
            Standard dict: { "ok": bool, "message": str, "data": Any }.
        """
        if not phone:
            return {
                "ok": False,
                "message": "Missing required parameter: 'phone'. (mock tool)",
                "data": None,
            }

        # 模拟两条 CDR 记录
        records: List[Dict[str, Any]] = [
            {
                "cdrId": "MOCK_CDR_001",
                "phone": phone,
                "otherParty": "13900000001",
                "startTime": start_time or "2024-10-01 08:00:00",
                "durationSeconds": 120,
                "direction": "outgoing",
                "result": "answered",
                "raw": {"source": "MOCK_DATA"},
            },
            {
                "cdrId": "MOCK_CDR_002",
                "phone": phone,
                "otherParty": "13900000002",
                "startTime": "2024-10-01 09:15:00",
                "durationSeconds": 0,
                "direction": "incoming",
                "result": "missed",
                "raw": {"source": "MOCK_DATA"},
            },
        ]

        total = 2  # 模拟总数为 2

        result = {
            "records": records,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "raw": {
                "records": records,
                "total": total,
                "source": "MOCK_DATA",
            },
        }

        return {
            "ok": True,
            "message": "CDR mock query succeeded.",
            "data": result,
        }
