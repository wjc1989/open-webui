"""
title: Investigation Mock APIs
author: OneCloudTech Demo
description: Mock APIs for /business/ai/* (baseinfo, contact, social, cr, voip, sms, email) for Open WebUI tool demo.
version: 2.0.0
"""

# ================================================================
# 说明（仅给开发者看，用户看不到）：
# 1. 这是一个 Open WebUI 合规的 Tools 插件文件
# 2. 放置路径建议为：
#       backend/open_webui/extensions/tools/investigation_mock_apis.py
# 3. 重启 Open WebUI 后即可在 Workspace → Tools 中启用
#
# 4. 所有接口当前均为 Mock（模拟数据，不调用真实 HTTP）
# 5. 统一返回格式（与 aaa.txt 对齐）：
#
#       成功（对象）: { "code": 0, "data": { ... } }
#       成功（列表）: { "code": 0, "data": [ ... ] }
#       失败       : { "code": 500, "msg": "error message", ... }
#
# 6. 如果参数缺失，会返回统一格式的错误，供 LLM 提示用户补齐参数：
#
#       {
#           "code": 500,
#           "msg": "Missing required parameter: phone",
#           "missing_params": ["phone"],
#           "ask_user_prompt": "Please provide a phone number."
#       }
#
# 7. 未来如果要接真实接口：
#    - 只需在对应方法里，用 requests/httpx 等发起 HTTP，
#    - URL 对应 aaa.txt 中的：
#         /business/ai/baseinfo
#         /business/ai/contact
#         /business/ai/social
#         /business/ai/cr
#         /business/ai/voip
#         /business/ai/sms
#         /business/ai/email
# ================================================================

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ================================================================
# 工具主类（必须叫 Tools，Open WebUI 会自动发现）
# ================================================================
class Tools:
    """
    Investigation Mock Tools

    This tool file exposes 7 mock APIs under the logical backend paths:

        1) /business/ai/baseinfo
           - params: id, phone
           - returns: basic person info (name, avatar, id, phone, country, gender)

        2) /business/ai/contact
           - params: phone, email
           - returns: contact statistics (phone/email of contacts, times)

        3) /business/ai/social
           - params: account, phone
           - returns: virtual identity information (protocol, dataid, account, phone)

           Protocol mapping (for reference):
             147701: X (Twitter)
             147801: TikTok
             147501: Instagram
             147201: WhatsApp
             147301: Facebook
             147901: Address Book
             128901: Email
             199901: LinkedIn

        4) /business/ai/cr
           - params: id
           - returns: company registration (CR) information

        5) /business/ai/voip
           - params: phone
           - returns: VoIP call records

        6) /business/ai/sms
           - params: phone
           - returns: SMS records

        7) /business/ai/email
           - params: email
           - returns: Email records

    All methods currently return MOCK data and DO NOT call real HTTP endpoints.
    The LLM can still use them to learn:
      - which parameters are required,
      - what will be returned,
      - and how to ask the user for missing parameters.

    Unified success format:

        { "code": 0, "data": { ... } }
        or
        { "code": 0, "data": [ ... ] }

    Unified error format:

        {
            "code": 500,
            "msg": "Human readable error message",
            "missing_params": [...],          # optional
            "ask_user_prompt": "Ask user ..." # optional
        }
    """

    # ------------------------------------------------------------
    # 全局 Valves 配置，可在 Open WebUI 的前端控制台动态修改
    # ------------------------------------------------------------
    class Valves(BaseModel):
        # demo_mode 用于未来扩展（是否读取真实 API）
        demo_mode: bool = Field(
            True,
            description="If true, use mock data only (no real external APIs).",
        )

    def __init__(self):
        # 自动加载 Valves 配置
        self.valves = self.Valves()

    # ============================================================
    # 内部：构造统一格式成功返回
    # ============================================================
    @staticmethod
    def _ok(data: Any) -> Dict[str, Any]:
        """
        Build success response.

        Returns:
            {
                "code": 0,
                "data": data
            }
        """
        return {
            "code": 0,
            "data": data,
        }

    # ============================================================
    # 内部：构造统一格式错误返回（缺少参数等）
    # ============================================================
    @staticmethod
    def _err(
        msg: str,
        missing: Optional[List[str]] = None,
        ask: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build error response.

        Basic format:
            {"code": 500, "msg": "..."}

        Extended fields:
            - missing_params: which parameters are missing
            - ask_user_prompt: how LLM should ask the user
        """
        body: Dict[str, Any] = {
            "code": 500,
            "msg": msg,
        }
        if missing:
            body["missing_params"] = missing
        if ask:
            body["ask_user_prompt"] = ask
        return body

    # ============================================================
    # 1) /business/ai/baseinfo
    #    -params id/phone
    #    -return: basic person info
    # ============================================================
    def get_person_basic_info(
        self,
        id: Optional[str] = None,
        phone: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        /business/ai/baseinfo (MOCK)

        Query basic person information by id or phone.

        Parameters
        ----------
        id : str, optional
            Person ID (e.g. national ID, internal person id, etc.).
        phone : str, optional
            Phone number of the person.
        query_id : str, optional
            Optional query trace id, used only for logging/tracking.

        Behavior
        --------
        - If both id and phone are missing, returns an error with
          missing_params and ask_user_prompt.
        - Otherwise returns a mock object representing:
            name / avatar_url / id / phone / country / gender

        Unified response:
            Success: { "code": 0, "data": { ... } }
            Error  : { "code": 500, "msg": "...", ... }
        """
        if not id and not phone:
            return self._err(
                "Missing required identifier: you must provide 'id' or 'phone'.",
                ["id", "phone"],
                "To query basic information, please provide an ID or a phone number.",
            )

        # ——模拟数据（mock data）——
        data = {
            "id": id or "P202511300001",
            "phone": phone or "+96890001122",
            "name": "Demo Person",
            "avatar_url": "https://example.com/avatar/demo_person.png",
            "country": "OM",
            "gender": "M",
            "query_id": query_id or "mock-baseinfo-001",
        }
        return self._ok(data)

    # ============================================================
    # 2) /business/ai/contact
    #    -params phone/email
    #    -return: contact list with times
    # ============================================================
    def get_contact_statistics(
        self,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        /business/ai/contact (MOCK)

        Query person's contact statistics by phone or email.

        Parameters
        ----------
        phone : str, optional
            Phone number of the person.
        email : str, optional
            Email address of the person.
        query_id : str, optional
            Optional query trace id.

        Behavior
        --------
        - At least one of phone or email must be provided.
        - Returns a list of contacts with fields like:
            {
                "contact_type": "phone" or "email",
                "contact": "...",
                "times": 123
            }

        Unified response:
            { "code": 0, "data": [ ... ] }
        """
        if not phone and not email:
            return self._err(
                "Missing required identifier: you must provide 'phone' or 'email'.",
                ["phone", "email"],
                "To query contacts, please provide a phone number or an email address.",
            )

        # ——模拟数据（mock data）——
        target = phone or email
        data = [
            {
                "contact_type": "phone",
                "contact": "+96890003344",
                "times": 128,
            },
            {
                "contact_type": "phone",
                "contact": "+96890005566",
                "times": 34,
            },
            {
                "contact_type": "email",
                "contact": "friend@example.com",
                "times": 12,
            },
        ]

        return self._ok(
            {
                "owner": target,
                "items": data,
                "query_id": query_id or "mock-contact-001",
            }
        )

    # ============================================================
    # 3) /business/ai/social
    #    -params account/phone
    #    -return: virtual identity info
    # ============================================================
    def get_social_accounts(
        self,
        account: Optional[str] = None,
        phone: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        /business/ai/social (MOCK)

        Query virtual identity information by social account or phone.

        Parameters
        ----------
        account : str, optional
            Social account (e.g. username, email-style account).
        phone : str, optional
            Phone number used to register or bind the social accounts.
        query_id : str, optional
            Optional query trace id.

        Behavior
        --------
        - At least one of account or phone must be provided.
        - Returns a list of virtual identity records with fields such as:
            {
                "dataid": "128901_xxx",   # unique key in your system
                "protocol": "128901",     # see protocol mapping in class docstring
                "account": "user@example.com",
                "phone": "+96890001122",
                "nickname": "Demo Nick",
                "platform": "Email"
            }
        """
        if not account and not phone:
            return self._err(
                "Missing required identifier: you must provide 'account' or 'phone'.",
                ["account", "phone"],
                "To query social identities, please provide a social account or a phone number.",
            )

        # ——模拟数据（mock data，根据 aaa.txt 的示例结构）——
        owner = account or phone or ""
        items = [
            {
                "dataid": "128901_" + owner,
                "protocol": "128901",
                "account": owner or "demo_user@m.facebook.com",
                "phone": phone or "+96890001122",
                "nickname": "Demo Email",
                "platform": "Email",
            },
            {
                "dataid": "147301_" + (phone or "demo_facebook"),
                "protocol": "147301",
                "account": "demo_facebook_user",
                "phone": phone or "+96890001122",
                "nickname": "Demo FB",
                "platform": "Facebook",
            },
        ]

        return self._ok(
            {
                "owner": owner,
                "items": items,
                "query_id": query_id or "mock-social-001",
            }
        )

    # ============================================================
    # 4) /business/ai/cr
    #    -params id
    #    -return: company registration info
    # ============================================================
    def get_company_registration(
        self,
        id: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        /business/ai/cr (MOCK)

        Query company registration (CR) information.

        Parameters
        ----------
        id : str, optional
            Company registration id or internal company id.
        query_id : str, optional
            Optional query trace id.

        Behavior
        --------
        - id is required.
        - Returns company registration info, including:
            reg_no / name / status / address / legal_person / etc.
        """
        if not id:
            return self._err(
                "Missing required parameter: id.",
                ["id"],
                "To query company registration information, please provide a company id.",
            )

        # ——模拟数据（mock data）——
        data = {
            "id": id,
            "reg_no": "CR-2025-000001",
            "name": "OneCloudTech Demo LLC",
            "status": "Active",
            "legal_person": "Demo Owner",
            "address": "Muscat, Oman",
            "industry": "Information Technology Services",
            "establish_date": "2023-01-01",
            "query_id": query_id or "mock-cr-001",
        }
        return self._ok(data)

    # ============================================================
    # 5) /business/ai/voip
    #    -params phone
    #    -return: VoIP call records
    # ============================================================
    def get_voip_records(
        self,
        phone: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        /business/ai/voip (MOCK)

        Query VoIP call records by phone.

        Parameters
        ----------
        phone : str, optional
            Phone number of the target person.
        query_id : str, optional
            Optional query trace id.

        Behavior
        --------
        - phone is required.
        - Returns a list of VoIP CDRs (call records).
        """
        if not phone:
            return self._err(
                "Missing required parameter: phone.",
                ["phone"],
                "To query VoIP call records, please provide a phone number.",
            )

        # ——模拟数据（mock data）——
        items = [
            {
                "call_id": "VOIP-20251130-0001",
                "from": phone,
                "to": "+96890002233",
                "start_time": "2025-11-30 10:30:00",
                "duration_sec": 180,
                "direction": "outgoing",
            },
            {
                "call_id": "VOIP-20251130-0002",
                "from": "+96890002233",
                "to": phone,
                "start_time": "2025-11-29 21:15:00",
                "duration_sec": 60,
                "direction": "incoming",
            },
        ]

        return self._ok(
            {
                "phone": phone,
                "items": items,
                "query_id": query_id or "mock-voip-001",
            }
        )

    # ============================================================
    # 6) /business/ai/sms
    #    -params phone
    #    -return: SMS records
    # ============================================================
    def get_sms_records(
        self,
        phone: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        /business/ai/sms (MOCK)

        Query SMS records by phone.

        Parameters
        ----------
        phone : str, optional
            Phone number of the target person.
        query_id : str, optional
            Optional query trace id.

        Behavior
        --------
        - phone is required.
        - Returns a list of SMS records.
        """
        if not phone:
            return self._err(
                "Missing required parameter: phone.",
                ["phone"],
                "To query SMS records, please provide a phone number.",
            )

        # ——模拟数据（mock data）——
        items = [
            {
                "sms_id": "SMS-20251130-0001",
                "from": phone,
                "to": "+96890003344",
                "time": "2025-11-30 09:00:00",
                "content": "Demo SMS content 1.",
            },
            {
                "sms_id": "SMS-20251129-0002",
                "from": "+96890005566",
                "to": phone,
                "time": "2025-11-29 18:20:00",
                "content": "Demo SMS content 2.",
            },
        ]

        return self._ok(
            {
                "phone": phone,
                "items": items,
                "query_id": query_id or "mock-sms-001",
            }
        )

    # ============================================================
    # 7) /business/ai/email
    #    -params email
    #    -return: Email records
    # ============================================================
    def get_email_records(
        self,
        email: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        /business/ai/email (MOCK)

        Query Email records by email address.

        Parameters
        ----------
        email : str, optional
            Email address of the target person.
        query_id : str, optional
            Optional query trace id.

        Behavior
        --------
        - email is required.
        - Returns a list of email records.
        """
        if not email:
            return self._err(
                "Missing required parameter: email.",
                ["email"],
                "To query email records, please provide an email address.",
            )

        # ——模拟数据（mock data）——
        items = [
            {
                "message_id": "MAIL-20251130-0001",
                "from": email,
                "to": ["friend1@example.com"],
                "subject": "Demo email subject 1",
                "time": "2025-11-30 08:30:00",
            },
            {
                "message_id": "MAIL-20251129-0002",
                "from": "other@example.com",
                "to": [email],
                "subject": "Demo email subject 2",
                "time": "2025-11-29 16:10:00",
            },
        ]

        return self._ok(
            {
                "email": email,
                "items": items,
                "query_id": query_id or "mock-email-001",
            }
        )
