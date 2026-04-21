"""
title: UM AI Insight
author: OneCloudTech
description: Tools for UM system. Provides UM tools calling backend /ai/* APIs. Records (voip/sms/email) return plain text so <jump> is always rendered as iframe in Open WebUI.
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
    UM_chat is an investigative backend tool.

    Usage rules:
    - Call this tool ONLY when investigation data is required.
    - Never guess or auto-fill missing parameters.
    - If required parameters are missing, wait for user input.

    Response handling rules:
    - If "found" is true, the result MUST be treated as valid.
    - If a "message" field exists, it MUST be returned verbatim as the final answer.
    - Never summarize, interpret, or rewrite the message.
    - Preserve <jump> and any embedded markers exactly.
    """

    def __init__(self):
        self.citation = False
        self.valves = self.Valves()

        self.logger = logging.getLogger("UM_AI_Insight")
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            )

        self._session = requests.Session()

    class Valves(BaseModel):
        backend_base_url: str = Field(
            "http://192.168.80.185:8654",
            description="Backend Spring Boot base URL (without /ai), e.g. http://192.168.80.185:8654",
        )

    # ------------------ Common helper methods ------------------

    def _build_url(self, path: str) -> str:
        base = self.valves.backend_base_url.rstrip("/")
        return f"{base}{path}"

    def _clean_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, str):
                vv = v.strip()
                if vv == "":
                    continue
                cleaned[k] = vv
                continue
            cleaned[k] = v
        return cleaned

    def _normalize_found_flag(self, data: Any) -> bool:
        if data is None:
            return False
        if isinstance(data, (list, dict)) and len(data) == 0:
            return False
        return True

    def _build_full_url_with_params(self, url: str, params: Dict[str, Any]) -> str:
        req = requests.Request("GET", url, params=params).prepare()
        return req.url

    def _get(self, path: str, params: Dict[str, Any]) -> Tuple[Any, str]:
        url = self._build_url(path)
        query = self._clean_params(params)
        request_url = self._build_full_url_with_params(url, query)

        self.logger.info(f"Calling backend GET {request_url}")

        try:
            resp = self._session.get(url, params=query, timeout=15)
            self.logger.info(
                f"Backend response status={resp.status_code} for {request_url}"
            )
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
                self.logger.error(
                    f"Backend business error for {request_url}: code={body.get('code')}, msg={msg}"
                )
                raise Exception(f"Backend error: {msg}")
            self.logger.info(f"Backend call succeeded: {request_url}")
            return body.get("data"), request_url

        self.logger.warning(
            f"Backend did not return AjaxResult; returning raw body. url={request_url}"
        )
        return body, request_url

    def _need_more_input(
        self, message: str, missing_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        payload = {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }
        self.logger.warning(
            f"Missing required params: {payload['missing_fields']}, message='{message}'"
        )
        return payload

    def _attach_jump_url(self, data: Any, jump_url: Optional[str]) -> Any:
        if not jump_url:
            return data
        if isinstance(data, dict):
            new_data = dict(data)
            new_data["jump_url"] = jump_url
            return new_data
        return {"value": data, "jump_url": jump_url}

    def _wrap_result(
        self, endpoint: str, raw_params: dict, data: Any, request_url: str
    ) -> Any:
        found = None
        if isinstance(data, dict) and "found" in data:
            found = bool(data.get("found"))

        jump_url = data.get("jump_url") if isinstance(data, dict) else None

        data_out = data
        if jump_url and isinstance(data, dict):
            data_out = dict(data)
            data_out.pop("jump_url", None)

        if found is None:
            if isinstance(data, dict) and "value" in data:
                found = self._normalize_found_flag(data.get("value"))
            else:
                found = self._normalize_found_flag(data)

        lines = [
            (
                "Relevant records were found."
                if found
                else "No relevant records were found."
            )
        ]

        if jump_url:
            lines.append("")
            lines.append(f'<jump url="{jump_url}" height="600"></jump>')

        ui_text = "\n".join(lines)

        result = {
            "found": found,
            "request_url": request_url,
            "data": data_out,
            "text": ui_text,
        }
        if jump_url:
            result["_jump_url"] = jump_url
        return result

    # --------- PLAIN TEXT wrapper for records endpoints (voip/sms/email) ---------

    def _wrap_plain_text_records(
        self,
        *,
        title: str,
        data: Any,
        request_url: str,
        jump_url: Optional[str],
        found: Optional[bool] = None,
    ) -> str:
        if found is None:
            if isinstance(data, dict) and "value" in data:
                found = self._normalize_found_flag(data.get("value"))
            else:
                found = self._normalize_found_flag(data)

        lines: List[str] = []
        lines.append(
            f"{title}: {'Relevant records were found.' if found else 'No relevant records were found.'}"
        )
        lines.append(f"request_url: {request_url}")

        if jump_url:
            lines.append("")
            lines.append(f'<jump url="{jump_url}" height="600"></jump>')
        else:
            lines.append("")
            lines.append("(No available jump link.)")

        return "\n".join(lines)

    # ------------------ Jump URL builders ------------------

    def _build_track_jump(
        self, id: Optional[str], phonenum: Optional[str], passport: Optional[str]
    ) -> Optional[str]:
        base = "https://192.168.80.185:8443/faceboard/#/trackQuery?opentype=ai"
        if id:
            return f"{base}&{urlencode({'searchType': 10, 'searchKey': id})}"
        if phonenum:
            return f"{base}&{urlencode({'searchType': 30, 'searchKey': phonenum})}"
        if passport:
            return f"{base}&{urlencode({'searchType': 40, 'searchKey': passport})}"
        return None

    def _build_ecr_jump(self, search_key: Optional[str]) -> Optional[str]:
        if not search_key:
            return None
        base = "https://192.168.80.185:8443/faceboard/#/ecrPage?opentype=ai"
        return f"{base}&{urlencode({'searchType': 11, 'searchKey': search_key})}"

    def _build_mass_jump_url(
        self,
        *,
        phonenum: Optional[str] = None,
        keyword: Optional[str] = None,
        type_: Optional[int] = None,
    ) -> str:
        base = "https://192.168.80.185/vmd/advance_mass?opentype=ai"

        parts: List[str] = []
        if keyword:
            parts.append(str(keyword))
        if phonenum:
            parts.append(str(phonenum))

        params: Dict[str, Any] = {}
        if type_ is not None:
            params["type"] = type_
        if parts:
            params["keyword"] = ",".join(parts)

        return f"{base}&{urlencode(params)}" if params else base

    def _build_export_person_word_url(
        self,
        idNo: str,
        id_record: Optional[int] = 1,
        work_record: Optional[int] = 1,
        family: Optional[int] = 1,
        company: Optional[int] = 1,
        vehicle: Optional[int] = 1,
        phone: Optional[int] = 1,
        expired: Optional[int] = 1,
        social: Optional[int] = 1,
        caller: Optional[int] = 1,
        called: Optional[int] = 1,
    ) -> str:
        """
        Export Word URL:
        /business/persona/exportWord?idNo=xxxx&id_record=1&...

        Rules:
        - All switches default to 1
        - Pass 0 to exclude a section
        - None also falls back to 1
        """
        params: Dict[str, Any] = {
            "idNo": str(idNo).strip(),
            "id_record": 1 if id_record is None else int(id_record),
            "work_record": 1 if work_record is None else int(work_record),
            "family": 1 if family is None else int(family),
            "company": 1 if company is None else int(company),
            "vehicle": 1 if vehicle is None else int(vehicle),
            "phone": 1 if phone is None else int(phone),
            "expired": 1 if expired is None else int(expired),
            "social": 1 if social is None else int(social),
            "caller": 1 if caller is None else int(caller),
            "called": 1 if called is None else int(called),
        }

        return f"https://192.168.80.185/prod-api/business/persona/exportWord?{urlencode(params)}"

    # ------------------ AIController API mappings ------------------

    def get_person_baseinfo(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query base information, please provide at least one of: id, passport, or phonenum.",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/baseinfo", raw_params)

        jump_url = self._build_track_jump(id=id, phonenum=phonenum, passport=passport)
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/baseinfo", raw_params, data, request_url)

    def get_family_members(
        self, id: Optional[str] = None, phonenum: Optional[str] = None
    ) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query family members, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/family", raw_params)

        base = "https://192.168.80.185:8443/anlyze.html?showback=false&opentype=ai&expandBy=famliy"
        jump_url = f"{base}&{urlencode({'clue': phonenum, 'identityId': id})}"
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/family", raw_params, data, request_url)

    def get_cr_info(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query CR information, please provide at least one of: id, passport, or phonenum.",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/cr", raw_params)

        search_key = id or phonenum or passport
        jump_url = self._build_ecr_jump(search_key)
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/cr", raw_params, data, request_url)

    def get_top_contacts(
        self, id: Optional[str] = None, phonenum: Optional[str] = None
    ) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query top contacts, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/contact", raw_params)

        base = "https://192.168.80.185:8443/anlyze.html?showback=false&opentype=ai&expandBy=contacts"
        jump_url = f"{base}&{urlencode({'clue': phonenum, 'identityId': id})}"
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/contact", raw_params, data, request_url)

    def get_vehicles(
        self, id: Optional[str] = None, phonenum: Optional[str] = None
    ) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query vehicle information, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/car", raw_params)

        base = "https://192.168.80.185:8443/faceboard/#/carNo?opentype=ai&queryMode=20&page=1&pageSize=20"
        jump_url = f"{base}&{urlencode({'phoneNum': phonenum})}"
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/car", raw_params, data, request_url)

    def get_social_accounts(
        self, id: Optional[str] = None, phonenum: Optional[str] = None
    ) -> Any:
        if not id and not phonenum:
            return self._need_more_input(
                "To query social accounts, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/social", raw_params)

        base = "https://192.168.80.185:8443/faceboard/#/snsAccount?opentype=ai&page=1&pageSize=20&queryMode=20"
        jump_url = f"{base}&{urlencode({'phoneNumber': phonenum})}"
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/social", raw_params, data, request_url)

    def get_locations(self, phonenum: Optional[str] = None) -> Any:
        if not phonenum:
            return self._need_more_input(
                "To query locations, please provide: phonenum.",
                ["phonenum"],
            )

        raw_params = {"phonenum": phonenum}
        data, request_url = self._get("/ai/location", raw_params)

        base = "https://192.168.80.185:8443/vthink-ui-v3/#/tracking?opentype=ai"
        jump_url = f"{base}&{urlencode({'searchKey': phonenum})}"
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/location", raw_params, data, request_url)

    # ------------------ Records: PLAIN TEXT mode ------------------

    def search_voip_records(self, phonenum: Optional[str] = None) -> Any:
        if not phonenum:
            return self._need_more_input(
                "To search VoIP call records, please provide: phonenum.",
                ["phonenum"],
            )

        raw_params = {"phonenum": phonenum}
        data, request_url = self._get("/ai/voip", raw_params)

        jump_url = self._build_mass_jump_url(
            phonenum=phonenum,
            keyword=None,
            type_=16,
        )

        return self._wrap_plain_text_records(
            title="VoIP Records",
            data=data,
            request_url=request_url,
            jump_url=jump_url,
        )

    def search_sms_records(
        self, keyword: Optional[str] = None, phonenum: Optional[str] = None
    ) -> Any:
        if not keyword and not phonenum:
            return self._need_more_input(
                "To search SMS records, please provide: keyword or phonenum.",
                ["keyword", "phonenum"],
            )

        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/sms", raw_params)

        jump_url = self._build_mass_jump_url(
            phonenum=phonenum,
            keyword=keyword,
            type_=8,
        )

        return self._wrap_plain_text_records(
            title="SMS Records",
            data=data,
            request_url=request_url,
            jump_url=jump_url,
        )

    def search_email_records(
        self, keyword: Optional[str] = None, email: Optional[str] = None
    ) -> Any:
        if not keyword and not email:
            return self._need_more_input(
                "To search email records, please provide: keyword or email.",
                ["keyword", "email"],
            )

        raw_params = {"keyword": keyword, "email": email}
        data, request_url = self._get("/ai/email", raw_params)

        jump_url = self._build_mass_jump_url(
            phonenum=email,
            keyword=keyword,
            type_=5,
        )

        return self._wrap_plain_text_records(
            title="Email Records",
            data=data,
            request_url=request_url,
            jump_url=jump_url,
        )

    # ------------------ Export person Word ------------------

    def exportPerson(
        self,
        idNo: Optional[str] = None,
        id_record: Optional[int] = 1,
        work_record: Optional[int] = 1,
        family: Optional[int] = 1,
        company: Optional[int] = 1,
        vehicle: Optional[int] = 1,
        phone: Optional[int] = 1,
        expired: Optional[int] = 1,
        social: Optional[int] = 1,
        caller: Optional[int] = 1,
        called: Optional[int] = 1,
    ) -> Any:
        """
        Export person profile as a Word document.

        Required:
        - idNo

        Optional switches:
        - id_record
        - work_record
        - family
        - company
        - vehicle
        - phone
        - expired
        - social
        - caller
        - called

        Rules:
        - Default is 1 for every section
        - Pass 0 to exclude a section
        - If omitted, it stays 1
        """
        if not idNo:
            return self._need_more_input(
                "To export the person profile to Word, please provide: idNo.",
                ["idNo"],
            )

        export_url = self._build_export_person_word_url(
            idNo=str(idNo).strip(),
            id_record=id_record,
            work_record=work_record,
            family=family,
            company=company,
            vehicle=vehicle,
            phone=phone,
            expired=expired,
            social=social,
            caller=caller,
            called=called,
        )

        return f"✅ Export is ready: [Download Word]({export_url})"