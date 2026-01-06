"""
title: ESCT AI Insight
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
    - Preserve <jump>   and any embedded markers exactly.
    """

    def __init__(self):
        # 不在聊天输出中生成 citations
        self.citation = False
        self.valves = self.Valves()

        # ----- logging -----
        self.logger = logging.getLogger("ESCT_AI_Insight")
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            )

        # 复用 HTTP 连接（频繁请求更快、更省资源）
        self._session = requests.Session()

    class Valves(BaseModel):
        backend_base_url: str = Field(
            "http://192.168.80.185:8654",
            description="Backend Spring Boot base URL (without /ai), e.g. http://192.168.80.185:8654",
        )

    # ------------------ Common helper methods ------------------

    def _build_url(self, path: str) -> str:
        """拼接后端请求 URL（不含 query string）"""
        base = self.valves.backend_base_url.rstrip("/")
        return f"{base}{path}"

    def _clean_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理参数：去掉 None / 空字符串 / 纯空白字符串
        这样不会把无意义参数带给后端（也避免 query string 过长）
        """
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
        """
        统一 found 判定（当后端没有明确提供 found 字段时使用）：
        - None / 空 list / 空 dict => not found
        - 其它 => found
        """
        if data is None:
            return False
        if isinstance(data, (list, dict)) and len(data) == 0:
            return False
        return True

    def _build_full_url_with_params(self, url: str, params: Dict[str, Any]) -> str:
        """生成可直接打开的完整 URL（含 query string），用于审计/排查"""
        req = requests.Request("GET", url, params=params).prepare()
        return req.url

    def _get(self, path: str, params: Dict[str, Any]) -> Tuple[Any, str]:
        """
        执行 GET 请求。

        期望后端返回 AjaxResult:
        { "code": 200, "msg": "...", "data": ... }

        返回：(data, request_url)
        """
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

        # 标准 AjaxResult
        if isinstance(body, dict) and "code" in body:
            if body.get("code") != 200:
                msg = body.get("msg")
                self.logger.error(
                    f"Backend business error for {request_url}: code={body.get('code')}, msg={msg}"
                )
                raise Exception(f"Backend error: {msg}")
            self.logger.info(f"Backend call succeeded: {request_url}")
            return body.get("data"), request_url

        # 非标准返回，直接透传
        self.logger.warning(
            f"Backend did not return AjaxResult; returning raw body. url={request_url}"
        )
        return body, request_url

    def _need_more_input(
        self, message: str, missing_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        必填参数缺失时：
        - 不调用后端
        - 返回结构化错误，便于前端/模型提示用户补参
        """
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
        """把 jump_url 安全附加到 data 上（dict 直接加；非 dict 包一层）"""
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
        """
        Unified tool output (baseinfo style) so frontend can always render <jump>.
        Return keys:
          - found
          - request_url
          - data
          - message   (contains <jump> markers)
          - text      (same as message, for compatibility)
          - _jump_url (optional)
        """
        # found：优先后端明确 found
        found = None
        if isinstance(data, dict) and "found" in data:
            found = bool(data.get("found"))

        # jump_url
        jump_url = data.get("jump_url") if isinstance(data, dict) else None

        # data_out：剔除 jump_url
        data_out = data
        if jump_url and isinstance(data, dict):
            data_out = dict(data)
            data_out.pop("jump_url", None)

        # 如果没有 found：按真实业务数据判定
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
        """
        Records endpoints return PLAIN TEXT to avoid model dropping <jump>.
        We still log/keep request_url in server logs.

        Output includes:
          - title line
          - request_url (optional, but kept for audit; if you don't want to expose it, comment it out)
          - <jump> markers
        """
        if found is None:
            # data may be {"value": [...], ...} or list/dict
            if isinstance(data, dict) and "value" in data:
                found = self._normalize_found_flag(data.get("value"))
            else:
                found = self._normalize_found_flag(data)

        lines: List[str] = []
        lines.append(
            f"{title}: {'Relevant records were found.' if found else 'No relevant records were found.'}"
        )
        # If you don't want to expose request_url in chat, comment out the next line
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
        """
        faceboard trackQuery 跳转：
        - id      -> searchType=10
        - phone   -> searchType=30
        - passport-> searchType=40
        优先级：id > phonenum > passport
        """
        base = "https://192.168.80.185:8443/faceboard/#/trackQuery?opentype=ai"
        if id:
            return f"{base}&{urlencode({'searchType': 10, 'searchKey': id})}"
        if phonenum:
            return f"{base}&{urlencode({'searchType': 30, 'searchKey': phonenum})}"
        if passport:
            return f"{base}&{urlencode({'searchType': 40, 'searchKey': passport})}"
        return None

    def _build_ecr_jump(self, search_key: Optional[str]) -> Optional[str]:
        """
        faceboard ecrPage（CR）跳转：
        - searchType 固定 11
        - searchKey 取 id/phone/passport 之一
        """
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
        """
        vmd/advance_mass 跳转：
        - type: 模块类型（voip/sms/email 对应不同 type）
        - keyword: 把 keyword + phonenum 合并，用逗号连接（谁有用谁）
        """
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

    def _build_export_person_word_url(self, id_no: str) -> str:
        """
        Export Word URL:
        /business/persona/exportWord?idNo=xxxx
        """
        return f"https://192.168.80.185/prod-api/business/persona/exportWord?{urlencode({'idNo': id_no})}"

    # ------------------ AIController API mappings ------------------

    def get_person_baseinfo(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """查询人员基础信息（/ai/baseinfo），至少提供 id/passport/phonenum 之一"""
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
        """查询家庭成员（/ai/family），至少提供 id/phonenum 之一"""
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
        """查询 CR 信息（/ai/cr），至少提供 id/passport/phonenum 之一"""
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
        """查询高频联系人（/ai/contact），至少提供 id/phonenum 之一"""
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
        """查询车辆信息（/ai/car），至少提供 id/phonenum 之一"""
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
        """查询社交账号聚合（/ai/social），至少提供 id/phonenum 之一"""
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

    def get_locations(
        self, id: Optional[str] = None, phonenum: Optional[str] = None
    ) -> Any:
        """查询位置列表（/ai/location），至少提供 id/phonenum 之一"""
        if not id and not phonenum:
            return self._need_more_input(
                "To query locations, please provide: id or phonenum.",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/location", raw_params)

        base = "https://192.168.80.185:8443/vthink-ui-v3/#/tracking?opentype=ai"
        jump_url = f"{base}&{urlencode({'searchKey': phonenum})}"
        data = self._attach_jump_url(data, jump_url)

        return self._wrap_result("/ai/location", raw_params, data, request_url)

    # ------------------ Records: PLAIN TEXT mode ------------------

    def search_voip_records(self, phonenum: Optional[str] = None) -> Any:
        """查询 VoIP 通话记录（/ai/voip），必填 phonenum。返回纯文本（含 <jump>）"""
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
            type_=16,  # 你现有系统里的 voip type
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
        """查询短信记录（/ai/sms），keyword/phonenum 至少一个。返回纯文本（含 <jump>）"""
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
            type_=8,  # 你现有系统里的 sms type
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
        """查询邮件记录（/ai/email），keyword/email 至少一个。返回纯文本（含 <jump>）"""
        if not keyword and not email:
            return self._need_more_input(
                "To search email records, please provide: keyword or email.",
                ["keyword", "email"],
            )

        raw_params = {"keyword": keyword, "email": email}
        data, request_url = self._get("/ai/email", raw_params)

        # 保持你原来的行为：mass 的 keyword 里拼 keyword + email
        jump_url = self._build_mass_jump_url(
            phonenum=email,  # 用 phonenum 这个字段名做拼接，不改变原逻辑
            keyword=keyword,
            type_=5,  # 你现有系统里的 email type
        )

        return self._wrap_plain_text_records(
            title="Email Records",
            data=data,
            request_url=request_url,
            jump_url=jump_url,
        )

    # ------------------ NEW: Export person Word ------------------

    def exportPerson(self, idNo: Optional[str] = None) -> Any:
        """
        Export person profile as a Word document.
        Required: idNo

        Return a DIRECT DOWNLOAD LINK (plain text), NOT an iframe <jump>.
        URL:
          {backend_base_url}/business/persona/exportWord?idNo=xxxx
        """
        if not idNo:
            return self._need_more_input(
                "To export the person profile to Word, please provide: idNo.",
                ["idNo"],
            )

        export_url = self._build_export_person_word_url(str(idNo).strip())

        # Direct link for user click-to-download (no <jump>)
        return f"✅ Export is ready: [Download Word]({export_url})"
