"""
title: ESCT AI Insight (Mock)
author: OneCloudTech
description: Development-only mock tool that simulates /ai APIs and returns fake data without calling the real backend.
version: 0.4.0-dev
requirements: requests
"""

from typing import Optional, Any, Dict, List, Tuple
from pydantic import BaseModel, Field
import requests
import logging


class Tools:
    """
    Development-only tool:
    - External method signatures are identical to the real ESCT AI Insight tool.
    - _get does NOT call the real backend. It returns mock data based on the API path.
    """

    def __init__(self):
        # Disable citations in chat output
        self.citation = False
        self.valves = self.Valves()

        # ----- logging -----
        self.logger = logging.getLogger("ESCT_AI_Insight_MOCK")
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            )

    class Valves(BaseModel):
        backend_base_url: str = Field(
            "http://mock-backend.local:8654",
            description="Mock base URL for development (only used to construct request_url; no real HTTP requests).",
        )

    # ------------------ Common helper methods ------------------

    def _build_url(self, path: str) -> str:
        """Build base URL (without querystring)."""
        base = self.valves.backend_base_url.rstrip("/")
        return f"{base}{path}"

    def _clean_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out None / empty string parameters."""
        return {k: v for k, v in params.items() if v is not None and v != ""}

    def _normalize_found_flag(self, data: Any) -> bool:
        """
        Decide whether data should be considered "found".
        - None -> not found
        - empty list/dict -> not found
        - otherwise -> found
        """
        if data is None:
            return False
        if isinstance(data, (list, dict)) and len(data) == 0:
            return False
        return True

    def _build_full_url_with_params(self, url: str, params: Dict[str, Any]) -> str:
        """
        Build a user-friendly URL including querystring.
        Uses requests.Request for proper encoding.
        """
        req = requests.Request("GET", url, params=params).prepare()
        return req.url

    # In this mock version, _get does NOT send HTTP requests.
    def _get(self, path: str, params: Dict[str, Any]) -> Tuple[Any, str]:
        """
        Mock version of GET:
        - Does not call the real backend.
        - Returns (data, request_url) with fake data.
        """
        url = self._build_url(path)
        query = self._clean_params(params)
        request_url = self._build_full_url_with_params(url, query)

        self.logger.info(f"[MOCK] Returning fake data for {request_url}")

        # Build mock data based on API path
        if path == "/ai/baseinfo":
            data = {
                "id": query.get("id", "ID1234567890"),
                "passport": query.get("passport", "P1234567"),
                "phonenum": query.get("phonenum", "+96890000000"),
                "name": "Test User",
                "gender": "M",
                "birthday": "1990-01-01",
                "nationality": "OM",
                "address": "Muscat, Oman",
                "remarks": "This is mock base info for development testing.",
            }

        elif path == "/ai/family":
            data = [
                {
                    "relation": "spouse",
                    "name": "Mock Spouse",
                    "id": "ID_FAMILY_001",
                    "phonenum": "+96890000001",
                },
                {
                    "relation": "child",
                    "name": "Mock Child",
                    "id": "ID_FAMILY_002",
                    "phonenum": "+96890000002",
                },
            ]

        elif path == "/ai/cr":
            data = {
                "id": query.get("id", "ID1234567890"),
                "phonenum": query.get("phonenum", "+96890000000"),
                "score": 780,
                "level": "A",
                "update_time": "2025-01-01 10:00:00",
                "remarks": "This is mock CR info for integration testing.",
            }

        elif path == "/ai/contact":
            data = [
                {
                    "rank": 1,
                    "phonenum": "+96890000011",
                    "name": "Top Contact A",
                    "call_times": 128,
                    "sms_times": 56,
                    "last_contact_time": "2025-01-02 12:34:56",
                },
                {
                    "rank": 2,
                    "phonenum": "+96890000022",
                    "name": "Top Contact B",
                    "call_times": 96,
                    "sms_times": 33,
                    "last_contact_time": "2025-01-01 09:20:00",
                },
            ]

        elif path == "/ai/car":
            data = [
                {
                    "plate_no": "TEST-1234",
                    "brand": "Toyota",
                    "model": "Camry",
                    "color": "White",
                    "owner_id": query.get("id", "ID1234567890"),
                    "register_date": "2020-05-01",
                },
                {
                    "plate_no": "TEST-5678",
                    "brand": "Nissan",
                    "model": "Altima",
                    "color": "Black",
                    "owner_id": query.get("id", "ID1234567890"),
                    "register_date": "2022-03-15",
                },
            ]

        elif path == "/ai/social":
            data = [
                {
                    "platform": "WhatsApp",
                    "account": "+96890000000",
                    "nickname": "Mock WhatsApp",
                    "last_active": "2025-01-01 08:00:00",
                },
                {
                    "platform": "Instagram",
                    "account": "mock_instagram",
                    "nickname": "Mock IG",
                    "last_active": "2024-12-31 22:10:00",
                },
            ]

        elif path == "/ai/location":
            data = [
                {
                    "time": "2025-01-01 09:00:00",
                    "lat": 23.5880,
                    "lon": 58.3829,
                    "addr": "Muscat City Center",
                },
                {
                    "time": "2025-01-01 10:30:00",
                    "lat": 23.6000,
                    "lon": 58.4000,
                    "addr": "Office Building",
                },
            ]

        elif path == "/ai/voip":
            data = [
                {
                    "call_id": "VOIP_TEST_001",
                    "from": query.get("phonenum", "+96890000000"),
                    "to": "+96890000011",
                    "start_time": "2025-01-01 10:00:00",
                    "duration_sec": 180,
                    "direction": "OUT",
                    "keyword_hit": query.get("keyword"),
                },
                {
                    "call_id": "VOIP_TEST_002",
                    "from": "+96890000022",
                    "to": query.get("phonenum", "+96890000000"),
                    "start_time": "2025-01-01 11:00:00",
                    "duration_sec": 60,
                    "direction": "IN",
                    "keyword_hit": query.get("keyword"),
                },
            ]

        elif path == "/ai/sms":
            data = [
                {
                    "sms_id": "SMS_TEST_001",
                    "phonenum": query.get("phonenum", "+96890000000"),
                    "peer": "+96890000011",
                    "time": "2025-01-01 09:30:00",
                    "content": f"[MOCK SMS] This is a test SMS. keyword={query.get('keyword')}",
                },
                {
                    "sms_id": "SMS_TEST_002",
                    "phonenum": "+96890000022",
                    "peer": query.get("phonenum", "+96890000000"),
                    "time": "2025-01-01 09:35:00",
                    "content": "[MOCK SMS] Second test SMS message.",
                },
            ]

        elif path == "/ai/email":
            data = [
                {
                    "email_id": "MAIL_TEST_001",
                    "from": "sender@example.com",
                    "to": query.get("email", "user@example.com"),
                    "subject": "[MOCK EMAIL] Test subject 1",
                    "time": "2025-01-01 08:00:00",
                    "snippet": f"This is the first mock email snippet. keyword={query.get('keyword')}",
                },
                {
                    "email_id": "MAIL_TEST_002",
                    "from": query.get("email", "user@example.com"),
                    "to": "receiver@example.com",
                    "subject": "[MOCK EMAIL] Test subject 2",
                    "time": "2025-01-01 09:15:00",
                    "snippet": "This is the second mock email snippet.",
                },
            ]

        else:
            # Fallback: echo structure if no specific mock is defined for the path
            data = {
                "echo_path": path,
                "echo_params": query,
                "note": "No dedicated mock data defined for this path. Echoing request parameters.",
            }

        return data, request_url

    def _need_more_input(self, message: str, missing_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        When required parameters are missing: do not call backend.
        Return a structured error so the model / frontend can ask the user for more input.
        """
        payload = {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }
        self.logger.warning(f"[MOCK] Missing required params: {payload['missing_fields']}, message='{message}'")
        return payload

    def _wrap_result(
        self,
        api_path: str,
        raw_params: Dict[str, Any],
        data: Any,
        request_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Unified result wrapper:
        - api: API path
        - query_params: cleaned query params
        - request_url: full URL with querystring (for inspection)
        - found: boolean flag derived from data
        - data: mock data
        """
        query_params = self._clean_params(raw_params)
        found = self._normalize_found_flag(data)

        wrapped = {
            "api": api_path,
            "query_params": query_params,
            "request_url": request_url,
            "found": found,
            "data": data,
        }

        self.logger.info(
            f"[MOCK] API {api_path} finished. found={found}, query_params={query_params}, url={request_url}"
        )
        return wrapped

    # ------------------ AIController API mapping (same signatures as real tool) ------------------

    # 1) /ai/baseinfo
    def get_person_baseinfo(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query base info, please provide at least one of: id, passport, or phonenum.",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/baseinfo", raw_params)
        return self._wrap_result("/ai/baseinfo", raw_params, data, request_url)

    # 2) /ai/family
    def get_family_members(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query family members, please provide id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/family", raw_params)
        return self._wrap_result("/ai/family", raw_params, data, request_url)

    # 3) /ai/cr
    def get_cr_info(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query CR info, please provide at least one of: id, passport, or phonenum.",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/cr", raw_params)
        return self._wrap_result("/ai/cr", raw_params, data, request_url)

    # 4) /ai/contact
    def get_top_contacts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query top contacts, please provide id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/contact", raw_params)
        return self._wrap_result("/ai/contact", raw_params, data, request_url)

    # 5) /ai/car
    def get_vehicles(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query vehicle info, please provide id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/car", raw_params)
        return self._wrap_result("/ai/car", raw_params, data, request_url)

    # 6) /ai/social
    def get_social_accounts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query social accounts, please provide id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/social", raw_params)
        return self._wrap_result("/ai/social", raw_params, data, request_url)

    # 7) /ai/location
    def get_locations(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query locations, please provide id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/location", raw_params)
        return self._wrap_result("/ai/location", raw_params, data, request_url)

    # 8) /ai/voip
    def search_voip_records(self, keyword: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not keyword and not phonenum:
            return self._need_more_input(
                "To search VoIP call records, please provide keyword or phonenum.",
                ["keyword", "phonenum"],
            )

        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/voip", raw_params)
        return self._wrap_result("/ai/voip", raw_params, data, request_url)

    # 9) /ai/sms
    def search_sms_records(self, keyword: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not keyword and not phonenum:
            return self._need_more_input(
                "To search SMS records, please provide keyword or phonenum.",
                ["keyword", "phonenum"],
            )

        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/sms", raw_params)
        return self._wrap_result("/ai/sms", raw_params, data, request_url)

    # 10) /ai/email
    def search_email_records(self, keyword: Optional[str] = None, email: Optional[str] = None) -> Any:
        if not keyword and not email:
            return self._need_more_input(
                "To search email records, please provide keyword or email.",
                ["keyword", "email"],
            )

        raw_params = {"keyword": keyword, "email": email}
        data, request_url = self._get("/ai/email", raw_params)
        return self._wrap_result("/ai/email", raw_params, data, request_url)
