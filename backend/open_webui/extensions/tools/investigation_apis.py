"""
title: UM AI Insight
author: OneCloudTech
description: Tools for UM system. Provides UM tools calling backend /ai/* APIs. Records (voip/sms/email) return plain text so <jump> is always rendered as iframe in Open WebUI.
version: 0.4.2
requirements: requests
"""

from typing import Optional, Any, Dict, List, Tuple
from pydantic import BaseModel, Field
import requests
import logging
from urllib.parse import urlencode
from io import BytesIO
import os


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
        # 不在聊天输出中生成 citations
        self.citation = False
        self.valves = self.Valves()

        # ----- logging -----
        self.logger = logging.getLogger("UM_AI_Insight")
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
        """清理参数：去掉 None / 空字符串 / 纯空白字符串"""
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

    def _get(self, path: str, params: Dict[str, Any], timeout: int = 15) -> Tuple[Any, str]:
        """
        执行 GET 请求。期望后端返回 AjaxResult:
        { "code": 200, "msg": "...", "data": ... }
        返回：(data, request_url)
        """
        url = self._build_url(path)
        query = self._clean_params(params)
        request_url = self._build_full_url_with_params(url, query)

        self.logger.info(f"Calling backend GET {request_url}")

        try:
            resp = self._session.get(url, params=query, timeout=timeout)
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

        # 标准 AjaxResult
        if isinstance(body, dict) and "code" in body:
            if body.get("code") != 200:
                msg = body.get("msg")
                self.logger.error(f"Backend business error for {request_url}: code={body.get('code')}, msg={msg}")
                raise Exception(f"Backend error: {msg}")
            return body.get("data"), request_url

        # 非标准返回，直接透传
        self.logger.warning(f"Backend did not return AjaxResult; returning raw body. url={request_url}")
        return body, request_url

    def _post_multipart_path(
        self,
        path: str,
        file_path: str,
        *,
        field_name: str = "file",
        extra_form: Optional[Dict[str, Any]] = None,
        timeout: int = 300,
    ) -> Any:
        """multipart 上传本地文件给后端（POST）"""
        url = self._build_url(path)
        form = self._clean_params(extra_form or {})

        self.logger.info(f"Calling backend POST(multipart-path) {url} file={file_path}")

        with open(file_path, "rb") as f:
            files = {field_name: (os.path.basename(file_path), f)}
            resp = self._session.post(url, data=form, files=files, timeout=timeout)

        resp.raise_for_status()
        out = resp.json()
        if isinstance(out, dict) and "code" in out:
            if out.get("code") != 200:
                raise Exception(f"Backend error: {out.get('msg')}")
            return out.get("data")
        return out

    def _post_multipart_bytes(
        self,
        path: str,
        *,
        filename: str,
        content: bytes,
        field_name: str = "file",
        extra_form: Optional[Dict[str, Any]] = None,
        timeout: int = 300,
    ) -> Any:
        """multipart 上传二进制内容给后端（POST）"""
        url = self._build_url(path)
        form = self._clean_params(extra_form or {})

        self.logger.info(f"Calling backend POST(multipart-bytes) {url} filename={filename} bytes={len(content)}")

        f = BytesIO(content)
        files = {field_name: (filename, f)}
        resp = self._session.post(url, data=form, files=files, timeout=timeout)
        resp.raise_for_status()

        out = resp.json()
        if isinstance(out, dict) and "code" in out:
            if out.get("code") != 200:
                raise Exception(f"Backend error: {out.get('msg')}")
            return out.get("data")
        return out

    def _need_more_input(self, message: str, missing_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        payload = {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }
        self.logger.warning(f"Missing required params: {payload['missing_fields']}, message='{message}'")
        return payload

    def _attach_jump_url(self, data: Any, jump_url: Optional[str]) -> Any:
        if not jump_url:
            return data
        if isinstance(data, dict):
            new_data = dict(data)
            new_data["jump_url"] = jump_url
            return new_data
        return {"value": data, "jump_url": jump_url}

    def _wrap_result(self, endpoint: str, raw_params: dict, data: Any, request_url: str) -> Any:
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

        lines = [("Relevant records were found." if found else "No relevant records were found.")]
        if jump_url:
            lines.append("")
            lines.append(f'<jump url="{jump_url}" height="600"></jump>')

        return {
            "found": found,
            "request_url": request_url,
            "data": data_out,
            "text": "\n".join(lines),
            **({"_jump_url": jump_url} if jump_url else {}),
        }

    def _wrap_plain_text_records(
        self,
        *,
        title: str,
        data: Any,
        request_url: str,
        jump_url: Optional[str],
        found: Optional[bool] = None,
        expose_request_url: bool = False,
    ) -> str:
        if found is None:
            if isinstance(data, dict) and "value" in data:
                found = self._normalize_found_flag(data.get("value"))
            else:
                found = self._normalize_found_flag(data)

        lines: List[str] = []
        lines.append(f"{title}: {'Relevant records were found.' if found else 'No relevant records were found.'}")
        if expose_request_url:
            lines.append(f"request_url: {request_url}")

        lines.append("")
        if jump_url:
            lines.append(f'<jump url="{jump_url}" height="600"></jump>')
        else:
            lines.append("(No available jump link.)")

        return "\n".join(lines)

    # ------------------ Jump URL builders ------------------

    def _build_track_jump(self, id: Optional[str], phonenum: Optional[str], passport: Optional[str]) -> Optional[str]:
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

    def _build_export_person_word_url(self, id_no: str) -> str:
        return f"https://192.168.80.185/prod-api/business/persona/exportWord?{urlencode({'idNo': id_no})}"

    # ------------------ Open WebUI files helpers ------------------

    def _pick_audio_from_files(self, __files__: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not __files__:
            return None
        audio_exts = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".webm")
        for item in __files__:
            name = (item.get("name") or "").lower()
            if name.endswith(audio_exts):
                return item
            f = item.get("file") or {}
            filename = (f.get("filename") or "").lower()
            if filename.endswith(audio_exts):
                return item
        return None

    def _get_auth_headers_from_request(self, __request__: Any) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if not __request__:
            return headers
        try:
            req_headers = dict(__request__.headers)
            if req_headers.get("authorization"):
                headers["Authorization"] = req_headers["authorization"]
            if req_headers.get("cookie"):
                headers["Cookie"] = req_headers["cookie"]
        except Exception:
            pass
        return headers

    def _download_file_by_url(self, file_url: str, *, __request__: Any = None) -> bytes:
        headers = self._get_auth_headers_from_request(__request__)
        self.logger.info(f"Downloading file from Open WebUI url: {file_url} headers={list(headers.keys())}")
        resp = self._session.get(file_url, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()
        return resp.content

    # ------------------ AIController API mappings ------------------

    def get_person_baseinfo(self, id: Optional[str] = None, passport: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
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

    def get_family_members(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input("To query family members, please provide: id or phonenum.", ["id", "phonenum"])

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/family", raw_params)

        base = "https://192.168.80.185:8443/anlyze.html?showback=false&opentype=ai&expandBy=famliy"
        jump_url = f"{base}&{urlencode({'clue': phonenum, 'identityId': id})}"
        data = self._attach_jump_url(data, jump_url)
        return self._wrap_result("/ai/family", raw_params, data, request_url)

    def get_cr_info(self, id: Optional[str] = None, passport: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
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

    def get_top_contacts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input("To query top contacts, please provide: id or phonenum.", ["id", "phonenum"])

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/contact", raw_params)

        base = "https://192.168.80.185:8443/anlyze.html?showback=false&opentype=ai&expandBy=contacts"
        jump_url = f"{base}&{urlencode({'clue': phonenum, 'identityId': id})}"
        data = self._attach_jump_url(data, jump_url)
        return self._wrap_result("/ai/contact", raw_params, data, request_url)

    def get_vehicles(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input("To query vehicle information, please provide: id or phonenum.", ["id", "phonenum"])

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/car", raw_params)

        base = "https://192.168.80.185:8443/faceboard/#/carNo?opentype=ai&queryMode=20&page=1&pageSize=20"
        jump_url = f"{base}&{urlencode({'phoneNum': phonenum})}"
        data = self._attach_jump_url(data, jump_url)
        return self._wrap_result("/ai/car", raw_params, data, request_url)

    def get_social_accounts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not id and not phonenum:
            return self._need_more_input("To query social accounts, please provide: id or phonenum.", ["id", "phonenum"])

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/social", raw_params)

        base = "https://192.168.80.185:8443/faceboard/#/snsAccount?opentype=ai&page=1&pageSize=20&queryMode=20"
        jump_url = f"{base}&{urlencode({'phoneNumber': phonenum})}"
        data = self._attach_jump_url(data, jump_url)
        return self._wrap_result("/ai/social", raw_params, data, request_url)

    def get_locations(self, phonenum: Optional[str] = None) -> Any:
        if not phonenum:
            return self._need_more_input("To query locations, please provide: phonenum.", ["phonenum"])

        raw_params = {"phonenum": phonenum}
        data, request_url = self._get("/ai/location", raw_params)

        base = "https://192.168.80.185:8443/vthink-ui-v3/#/tracking?opentype=ai"
        jump_url = f"{base}&{urlencode({'searchKey': phonenum})}"
        data = self._attach_jump_url(data, jump_url)
        return self._wrap_result("/ai/location", raw_params, data, request_url)

    # ------------------ Records: PLAIN TEXT mode ------------------

    def search_voip_records(self, phonenum: Optional[str] = None) -> Any:
        if not phonenum:
            return self._need_more_input("To search VoIP call records, please provide: phonenum.", ["phonenum"])

        raw_params = {"phonenum": phonenum}
        data, request_url = self._get("/ai/voip", raw_params)

        jump_url = self._build_mass_jump_url(phonenum=phonenum, keyword=None, type_=16)

        return self._wrap_plain_text_records(
            title="VoIP Records",
            data=data,
            request_url=request_url,
            jump_url=jump_url,
            expose_request_url=False,
        )

    def search_sms_records(self, keyword: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not keyword and not phonenum:
            return self._need_more_input("To search SMS records, please provide: keyword or phonenum.", ["keyword", "phonenum"])

        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/sms", raw_params)

        jump_url = self._build_mass_jump_url(phonenum=phonenum, keyword=keyword, type_=8)

        return self._wrap_plain_text_records(
            title="SMS Records",
            data=data,
            request_url=request_url,
            jump_url=jump_url,
            expose_request_url=False,
        )

    def search_email_records(self, keyword: Optional[str] = None, email: Optional[str] = None) -> Any:
        if not keyword and not email:
            return self._need_more_input("To search email records, please provide: keyword or email.", ["keyword", "email"])

        raw_params = {"keyword": keyword, "email": email}
        data, request_url = self._get("/ai/email", raw_params)

        jump_url = self._build_mass_jump_url(phonenum=email, keyword=keyword, type_=5)

        return self._wrap_plain_text_records(
            title="Email Records",
            data=data,
            request_url=request_url,
            jump_url=jump_url,
            expose_request_url=False,
        )

    # ------------------ STT: file=POST, sid/url=GET ------------------

    def stt(
        self,
        sid: Optional[str] = None,
        url: Optional[str] = None,
        __files__: Optional[List[Dict[str, Any]]] = None,
        __request__: Any = None,
    ) -> Any:
        """
        STT routing:
          - if user uploaded file => POST /ai/stt (multipart)
          - if sid provided      => GET  /ai/stt?sid=...
          - if url provided      => GET  /ai/stt?url=...
        Return: backend AjaxResult.data (e.g., wavPath, text, ...)
        """

        # sid/url => GET
        if sid or url:
            params = {"sid": sid, "url": url}
            data, _request_url = self._get("/ai/stt", params, timeout=300)
            return data

        # file => POST
        if __files__:
            audio = self._pick_audio_from_files(__files__)
            if not audio:
                return self._need_more_input(
                    "Please upload an audio file (.wav/.mp3/.m4a...) or provide sid/url.",
                    ["__files__", "sid", "url"],
                )

            f = audio.get("file") or {}
            data = f.get("data") or {}
            file_path = data.get("path")

            filename = audio.get("name") or f.get("filename") or "audio.wav"

            if file_path and os.path.exists(file_path):
                return self._post_multipart_path(
                    "/ai/stt",
                    file_path,
                    field_name="file",
                    extra_form={},
                    timeout=300,
                )

            # 没有本地 path 就下载 url 再转发
            file_url = audio.get("url")
            if not file_url:
                return {
                    "error": "FILE_URL_NOT_AVAILABLE",
                    "message": "Open WebUI did not provide file url in __files__. Please check your Open WebUI configuration.",
                    "debug_keys": list(audio.keys()),
                }

            try:
                content = self._download_file_by_url(file_url, __request__=__request__)
            except Exception as e:
                self.logger.error(f"Failed to download uploaded file url: {e}")
                return {
                    "error": "FAILED_TO_DOWNLOAD_FILE_URL",
                    "message": f"Failed to download the uploaded file from Open WebUI url. {e}",
                    "file_url": file_url,
                }

            return self._post_multipart_bytes(
                "/ai/stt",
                filename=filename,
                content=content,
                field_name="file",
                extra_form={},
                timeout=300,
            )

        return self._need_more_input(
            "To run STT, please upload an audio file or provide sid or url.",
            ["__files__", "sid", "url"],
        )

    # ------------------ Export person Word ------------------

    def exportPerson(self, idNo: Optional[str] = None) -> Any:
        if not idNo:
            return self._need_more_input(
                "To export the person profile to Word, please provide: idNo.",
                ["idNo"],
            )
        export_url = self._build_export_person_word_url(str(idNo).strip())
        return f"✅ Export is ready: [Download Word]({export_url})"
