"""
title: ESCT AI Insight
author: OneCloudTech
description: Call backend /ai APIs to query person base info, family, contacts, social accounts, locations, and VoIP/SMS/Email records
version: 0.4.0
requirements: requests
"""

from typing import Optional, Any, Dict, List, Tuple
from pydantic import BaseModel, Field
import requests
import logging
from urllib.parse import urlencode


class Tools:
    """
    Tool class: maps Open WebUI Tool calls to backend AIController APIs.
    AIController Base Path: /ai

    IMPORTANT RULES (for model / caller):
    - If the tool returns {"found": true, "data": ...}, it MUST be treated as "found",
      even if the original query parameter (e.g. phone number) is not echoed in data.
    - Only when found == false, or a clear error is returned, can it be treated as "not found".
    """

    def __init__(self):
        # Do not generate citations in chat output
        self.citation = False
        self.valves = self.Valves()

        # ----- logging -----
        self.logger = logging.getLogger("ESCT_AI_Insight")
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            )

    class Valves(BaseModel):
        backend_base_url: str = Field(
            "http://192.168.80.185:8654",
            description="Backend Spring Boot base URL (without /ai), e.g. http://192.168.80.185:8654",
        )

    # ------------------ Common helper methods ------------------

    def _build_url(self, path: str) -> str:
        """Build backend request URL (without query string)."""
        base = self.valves.backend_base_url.rstrip("/")
        return f"{base}{path}"

    def _clean_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove None or empty-string parameters."""
        return {k: v for k, v in params.items() if v is not None and v != ""}

    def _normalize_found_flag(self, data: Any) -> bool:
        """
        Decide whether data is considered 'found':
        - None -> not found
        - Empty list / empty dict -> not found
        - Otherwise -> found
        """
        if data is None:
            return False
        if isinstance(data, (list, dict)) and len(data) == 0:
            return False
        return True

    def _build_full_url_with_params(self, url: str, params: Dict[str, Any]) -> str:
        """
        Build a directly openable full URL (with query string).
        Uses requests.PreparedRequest to ensure proper encoding.
        """
        req = requests.Request("GET", url, params=params).prepare()
        return req.url

    def _get(self, path: str, params: Dict[str, Any]) -> Tuple[Any, str]:
        """
        Perform a GET request.

        Expected backend response format (AjaxResult):
        { "code": 200, "msg": "...", "data": ... }

        Returns: (data, request_url)
        """
        url = self._build_url(path)
        query = self._clean_params(params)
        request_url = self._build_full_url_with_params(url, query)

        self.logger.info(f"Calling backend GET {request_url}")

        try:
            resp = requests.get(url, params=query, timeout=10)
            self.logger.info(f"Backend response status={resp.status_code} for {request_url}")
            resp.raise_for_status()
        except Exception as e:
            self.logger.error(f"HTTP error while calling {request_url}: {e}")
            raise

        try:
            body = resp.json()
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {request_url}: {e}")
            raise

        self.logger.debug(f"Backend raw JSON body from {request_url}: {body}")

        if isinstance(body, dict) and "code" in body:
            if body.get("code") != 200:
                msg = body.get("msg")
                self.logger.error(f"Backend business error for {request_url}: code={body.get('code')}, msg={msg}")
                raise Exception(f"Backend error: {msg}")
            self.logger.info(f"Backend call succeeded: {request_url}")
            return body.get("data"), request_url

        self.logger.warning(f"Backend did not return AjaxResult; returning raw body. url={request_url}")
        return body, request_url

    def _need_more_input(self, message: str, missing_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        When required parameters are missing:
        - Do NOT call backend
        - Return a structured error for frontend / model prompting
        """
        payload = {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }
        self.logger.warning(f"Missing required params: {payload['missing_fields']}, message='{message}'")
        return payload

    def _wrap_result(self, endpoint: str, raw_params: dict, data: Any, request_url: str) -> Any:
        """
        Wrap tool output.

        Key behavior:
        - <jump ...> markers are placed in the message (assistant text), not inside pure-JSON fields
        - jump_url is removed from data to avoid auto-rendering as a clickable link
        """

        if isinstance(data, dict):
            found = bool(data.get("found")) if "found" in data else bool(data)
        else:
            found = bool(data)

        jump_url = data.get("jump_url") if isinstance(data, dict) else None

        data_out = data
        if jump_url and isinstance(data, dict):
            data_out = dict(data)
            data_out.pop("jump_url", None)

        msg_lines = []
        if found:
            msg_lines.append("Relevant records were found.")
        else:
            msg_lines.append("No relevant records were found.")

        if jump_url:
            msg_lines.append("")
            msg_lines.append(f'<jump url="{jump_url}" height="300"></jump>')
            msg_lines.append(f'<jumpopen url="{jump_url}"></jumpopen>')

        result = {
            "found": found,
            "request_url": request_url,
            "data": data_out,
            "message": "\n".join(msg_lines),
        }

        if jump_url:
            result["_jump_url"] = jump_url

        return result

    # ------------------ AIController API mappings ------------------

    def get_person_baseinfo(self, id: Optional[str] = None, passport: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Query person base information (/ai/baseinfo). Required: id / passport / phonenum (at least one)."""
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query base information, please provide at least one of: id, passport, or phonenum.",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/baseinfo", raw_params)
        return self._wrap_result("/ai/baseinfo", raw_params, data, request_url)

    def get_family_members(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Query family members (/ai/family). Required: id or phonenum."""
        if not id and not phonenum:
            return self._need_more_input(
                "To query family members, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/family", raw_params)
        return self._wrap_result("/ai/family", raw_params, data, request_url)

    def get_cr_info(self, id: Optional[str] = None, passport: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Query CR information (/ai/cr). Required: id / passport / phonenum (at least one)."""
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query CR information, please provide at least one of: id, passport, or phonenum.",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/cr", raw_params)
        return self._wrap_result("/ai/cr", raw_params, data, request_url)

    def get_top_contacts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Query top contacts (/ai/contact). Required: id or phonenum."""
        if not id and not phonenum:
            return self._need_more_input(
                "To query top contacts, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/contact", raw_params)
        return self._wrap_result("/ai/contact", raw_params, data, request_url)

    def get_vehicles(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Query vehicle information (/ai/car). Required: id or phonenum."""
        if not id and not phonenum:
            return self._need_more_input(
                "To query vehicle information, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/car", raw_params)
        return self._wrap_result("/ai/car", raw_params, data, request_url)

    def get_social_accounts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Query aggregated social accounts (/ai/social). Required: id or phonenum."""
        if not id and not phonenum:
            return self._need_more_input(
                "To query social accounts, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/social", raw_params)
        return self._wrap_result("/ai/social", raw_params, data, request_url)

    def get_locations(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Query location list (/ai/location). Required: id or phonenum."""
        if not id and not phonenum:
            return self._need_more_input(
                "To query locations, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/location", raw_params)

        return self._wrap_result("/ai/location", raw_params, data, request_url)

    def _build_mass_jump_url(self, phonenum: str | None = None, keyword: str | None = None,
                             type_: int | None = None) -> str:
        base = "https://192.168.80.185/vmd/advance_mass"
        # 1) 合并 keyword + phonenum（谁有用谁，用 | 分隔）
        keyword_parts = []
        if keyword:
            keyword_parts.append(keyword)
        if phonenum:
            keyword_parts.append(phonenum)

        params = {}

        params["type"] = type_
        if keyword_parts:
            params["keyword"] = ",".join(keyword_parts)

        return f"{base}?{urlencode(params)}" if params else base

    def search_voip_records(self, phonenum: Optional[str] = None) -> Any:
        """Search VoIP call records (/ai/voip). Required: phonenum."""
        if not phonenum:
            return self._need_more_input(
                "To search VoIP call records, please provide: phonenum.",
                ["phonenum"],
            )
        raw_params = {"phonenum": phonenum}
        data, request_url = self._get("/ai/voip", raw_params)
        jump_url = self._build_mass_jump_url(None,phonenum,16)
        if isinstance(data, dict):
            data_out = dict(data)
            data_out["jump_url"] = jump_url
        else:
            data_out = {"result": data, "jump_url": jump_url}
        return self._wrap_result("/ai/voip", raw_params, data_out, request_url)


    def search_sms_records(self, keyword: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """Search SMS records (/ai/sms). Required: keyword or phonenum."""
        if not keyword and not phonenum:
            return self._need_more_input(
                "To search SMS records, please provide: keyword or phonenum.",
                ["keyword", "phonenum"],
            )

        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/sms", raw_params)
        jump_url = self._build_mass_jump_url(keyword, phonenum, 8)
        if isinstance(data, dict):
            data_out = dict(data)
            data_out["jump_url"] = jump_url
        else:
            data_out = {"result": data, "jump_url": jump_url}
        return self._wrap_result("/ai/sms", raw_params, data_out, request_url)

    def search_email_records(self, keyword: Optional[str] = None, email: Optional[str] = None) -> Any:
        """Search email records (/ai/email). Required: keyword or email."""
        if not keyword and not email:
            return self._need_more_input(
                "To search email records, please provide: keyword or email.",
                ["keyword", "email"],
            )

        raw_params = {"keyword": keyword, "email": email}
        data, request_url = self._get("/ai/email", raw_params)
        jump_url = self._build_mass_jump_url(keyword, email, 5)
        if isinstance(data, dict):
            data_out = dict(data)
            data_out["jump_url"] = jump_url
        else:
            data_out = {"result": data, "jump_url": jump_url}
        return self._wrap_result("/ai/email", raw_params, data_out, request_url)
