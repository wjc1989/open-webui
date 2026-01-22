"""
title: UM AI Insight
author: OneCloudTech
description: Tools for UM system. Provides UM tools calling backend /ai/* APIs. Records (voip/sms/email) return plain text so <jump> is always rendered as iframe in Open WebUI.
version: 0.4.4
requirements: requests
"""

from typing import Optional, Any, Dict, List, Tuple, Union
from pydantic import BaseModel, Field
import requests
import logging
from urllib.parse import urlencode, urlparse
from io import BytesIO
import os
import time


class Tools:
    """
    UM_chat is an investigative backend tool.

    ========== 使用规则 ==========
    - 只有在需要调查数据/转写时才调用 tool
    - 不要凭空猜参数；缺参就返回缺参结构（让前端提示用户补）

    ========== 响应规则 ==========
    - 如果后端返回 {"code":200,"data":...}，取 data
    - 如果后端返回 {"code":非200,...}，抛异常（或返回可读错误）
    - records (voip/sms/email) 为了保住 <jump>，返回纯文本（避免模型重写丢失）
    """

    def __init__(self):
        self.citation = False
        self.valves = self.Valves()

        # ----- logging -----
        self.logger = logging.getLogger("UM_AI_Insight")
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            )

        # 复用 HTTP 连接
        self._session = requests.Session()

    # ------------------ Config ------------------

    class Valves(BaseModel):
        backend_base_url: str = Field(
            "http://192.168.80.185:8654",
            description="Backend Spring Boot base URL (without /ai), e.g. http://192.168.80.185:8654",
        )

        # Open WebUI base（可选：你也可以在这里固定写死，避免推断失败）
        webui_base_url: Optional[str] = Field(
            None,
            description="Optional: Open WebUI base URL, e.g. http://127.0.0.1:3000. If not set, infer from __request__.",
        )

        # STT 上传超时（语音长时可能需要更久）
        stt_timeout_sec: int = Field(300, description="Timeout for /ai/stt request in seconds")

        # Open WebUI 下载超时
        webui_download_timeout_sec: int = Field(180, description="Timeout for downloading file content from Open WebUI")

    # ------------------ Common helper methods ------------------

    def _build_url(self, path: str) -> str:
        """拼接后端 URL"""
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
            else:
                cleaned[k] = v
        return cleaned

    def _normalize_found_flag(self, data: Any) -> bool:
        """后端没给 found 时的兜底 found 判断"""
        if data is None:
            return False
        if isinstance(data, (list, dict)) and len(data) == 0:
            return False
        return True

    def _build_full_url_with_params(self, url: str, params: Dict[str, Any]) -> str:
        """构造带 query 的 URL（用于日志 request_url）"""
        req = requests.Request("GET", url, params=params).prepare()
        return req.url

    def _get(self, path: str, params: Dict[str, Any], timeout: int = 15) -> Tuple[Any, str]:
        """
        GET 请求。
        期望后端 AjaxResult:
          { "code": 200, "msg": "...", "data": ... }
        返回: (data, request_url)
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
            snippet = (resp.text or "")[:200]
            self.logger.error(f"Failed to parse JSON from {request_url}: {e}; body_snippet={snippet!r}")
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

        size = None
        try:
            size = os.path.getsize(file_path)
        except Exception:
            pass

        self.logger.info(f"Calling backend POST(multipart-path) {url} field={field_name} file={file_path} size={size}")

        with open(file_path, "rb") as f:
            files = {field_name: (os.path.basename(file_path), f)}
            resp = self._session.post(url, data=form, files=files, timeout=timeout)

        self.logger.info(f"Backend response status={resp.status_code} for POST {url}")
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
        content_type: Optional[str] = None,
    ) -> Any:
        """
        multipart 上传 bytes 给后端（POST）
        注意：requests 的 files 支持三元组 (filename, fileobj, content_type)
        """
        url = self._build_url(path)
        form = self._clean_params(extra_form or {})

        self.logger.info(
            f"Calling backend POST(multipart-bytes) {url} field={field_name} filename={filename} "
            f"bytes={len(content)} content_type={content_type}"
        )

        f = BytesIO(content)
        if content_type:
            files = {field_name: (filename, f, content_type)}
        else:
            files = {field_name: (filename, f)}

        resp = self._session.post(url, data=form, files=files, timeout=timeout)
        self.logger.info(f"Backend response status={resp.status_code} for POST {url}")
        resp.raise_for_status()

        out = resp.json()
        if isinstance(out, dict) and "code" in out:
            if out.get("code") != 200:
                raise Exception(f"Backend error: {out.get('msg')}")
            return out.get("data")
        return out

    def _need_more_input(self, message: str, missing_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """统一缺参返回格式（便于前端提示用户补参数）"""
        payload = {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }
        self.logger.warning(f"Missing required params: {payload['missing_fields']}, message='{message}'")
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

    def _wrap_result(self, endpoint: str, raw_params: dict, data: Any, request_url: str) -> Any:
        """统一 baseinfo 类返回结构"""
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

        result = {
            "found": found,
            "request_url": request_url,
            "data": data_out,
            "text": "\n".join(lines),
        }
        if jump_url:
            result["_jump_url"] = jump_url
        return result

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
        """records 类返回纯文本，保证 <jump> 不被模型重写丢失"""
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
        """faceboard trackQuery 跳转：优先级 id > phone > passport"""
        base = "https://192.168.80.185:8443/faceboard/#/trackQuery?opentype=ai"
        if id:
            return f"{base}&{urlencode({'searchType': 10, 'searchKey': id})}"
        if phonenum:
            return f"{base}&{urlencode({'searchType': 30, 'searchKey': phonenum})}"
        if passport:
            return f"{base}&{urlencode({'searchType': 40, 'searchKey': passport})}"
        return None

    def _build_ecr_jump(self, search_key: Optional[str]) -> Optional[str]:
        """CR 跳转：searchType 固定 11"""
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
        """vmd/advance_mass 跳转：type + keyword(keyword,phonenum 合并)"""
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

    # ------------------ Open WebUI file download helpers ------------------

    def _is_probable_uuid(self, s: str) -> bool:
        """粗略判断是否 UUID（用于识别 file_id）"""
        if not s:
            return False
        s = s.strip()
        if len(s) < 32:
            return False
        # 形如 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        return s.count("-") == 4

    def _pick_audio_from_files(self, __files__: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        从 Open WebUI __files__ 中挑第一个音频文件
        兼容更多情况：
        - item['name'] 可能含后缀
        - item['file']['filename'] 可能含后缀
        - item['type'] / item['content_type'] 可能包含 audio/*
        """
        if not __files__:
            return None

        audio_exts = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".webm")
        for item in __files__:
            # 1) content-type 判断
            ct = (item.get("content_type") or item.get("type") or "").lower()
            if ct.startswith("audio/"):
                return item

            # 2) 文件名后缀判断
            name = (item.get("name") or "").lower()
            if name.endswith(audio_exts):
                return item

            f = item.get("file") or {}
            filename = (f.get("filename") or f.get("name") or "").lower()
            if filename.endswith(audio_exts):
                return item

        return None

    def _get_auth_headers_from_request(self, __request__: Any) -> Dict[str, str]:
        """
        从请求中抽取 Authorization/Cookie，用来请求 Open WebUI /api/v1/files/{id}/content
        """
        headers: Dict[str, str] = {}
        if not __request__:
            return headers

        try:
            req_headers = dict(__request__.headers)
            auth = req_headers.get("authorization") or req_headers.get("Authorization")
            cookie = req_headers.get("cookie") or req_headers.get("Cookie")
            if auth:
                headers["Authorization"] = auth
            if cookie:
                headers["Cookie"] = cookie
        except Exception:
            pass
        return headers

    def _infer_webui_base_url(self, __request__: Any) -> Optional[str]:
        """
        推断 Open WebUI base URL：
        优先 valves.webui_base_url（如果你配置了，就不猜）
        """
        if self.valves.webui_base_url:
            return self.valves.webui_base_url.rstrip("/")

        if not __request__:
            return None

        # 1) request.url 最准确
        try:
            u = __request__.url
            scheme = getattr(u, "scheme", None)
            netloc = getattr(u, "netloc", None)
            if scheme and netloc:
                return f"{scheme}://{netloc}"
        except Exception:
            pass

        # 2) origin / referer 兜底
        try:
            h = dict(__request__.headers)
            origin = h.get("origin") or h.get("Origin")
            if origin:
                return origin.rstrip("/")
            referer = h.get("referer") or h.get("Referer")
            if referer:
                p = urlparse(referer)
                if p.scheme and p.netloc:
                    return f"{p.scheme}://{p.netloc}"
        except Exception:
            pass

        return None

    def _normalize_file_url_or_id(self, file_url_or_id: str, __request__: Any = None) -> str:
        """
        把 file_url_or_id 规范化为可 GET 的 URL：
        - 如果是 http(s) URL，直接返回
        - 如果看起来像 UUID（file_id），拼接 {webui_base}/api/v1/files/{id}/content
        """
        s = (file_url_or_id or "").strip()
        if not s:
            raise ValueError("Empty file url/id")

        if s.startswith("http://") or s.startswith("https://"):
            return s

        # 当作 file_id
        base = self._infer_webui_base_url(__request__)
        if not base:
            raise ValueError(f"Cannot infer Open WebUI base URL from request; file_id={s}")
        return f"{base.rstrip('/')}/api/v1/files/{s}/content"

    def _download_openwebui_file(self, file_url_or_id: str, *, __request__: Any = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        从 Open WebUI 下载文件 content（返回 bytes + debug 信息）
        """
        headers = self._get_auth_headers_from_request(__request__)
        url = self._normalize_file_url_or_id(file_url_or_id, __request__=__request__)

        self.logger.info(f"[STT] Downloading from Open WebUI: {url} headers={list(headers.keys())}")

        t0 = time.time()
        resp = self._session.get(url, headers=headers, timeout=self.valves.webui_download_timeout_sec)
        cost_ms = int((time.time() - t0) * 1000)

        debug = {
            "download_url": url,
            "status_code": resp.status_code,
            "content_type": resp.headers.get("Content-Type"),
            "content_length": resp.headers.get("Content-Length"),
            "cost_ms": cost_ms,
        }

        self.logger.info(f"[STT] OpenWebUI download status={resp.status_code} ct={debug['content_type']} cost_ms={cost_ms}")
        resp.raise_for_status()

        content = resp.content or b""
        if len(content) == 0:
            raise ValueError(f"Downloaded content is empty from {url}")

        debug["bytes"] = len(content)
        return content, debug

    # ------------------ API mappings ------------------

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

    # ------------------ Records (plain text) ------------------

    def search_voip_records(self, phonenum: Optional[str] = None) -> Any:
        if not phonenum:
            return self._need_more_input("To search VoIP call records, please provide: phonenum.", ["phonenum"])
        raw_params = {"phonenum": phonenum}
        data, request_url = self._get("/ai/voip", raw_params)
        jump_url = self._build_mass_jump_url(phonenum=phonenum, keyword=None, type_=16)
        return self._wrap_plain_text_records(title="VoIP Records", data=data, request_url=request_url, jump_url=jump_url)

    def search_sms_records(self, keyword: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        if not keyword and not phonenum:
            return self._need_more_input("To search SMS records, please provide: keyword or phonenum.", ["keyword", "phonenum"])
        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/sms", raw_params)
        jump_url = self._build_mass_jump_url(phonenum=phonenum, keyword=keyword, type_=8)
        return self._wrap_plain_text_records(title="SMS Records", data=data, request_url=request_url, jump_url=jump_url)

    def search_email_records(self, keyword: Optional[str] = None, email: Optional[str] = None) -> Any:
        if not keyword and not email:
            return self._need_more_input("To search email records, please provide: keyword or email.", ["keyword", "email"])
        raw_params = {"keyword": keyword, "email": email}
        data, request_url = self._get("/ai/email", raw_params)
        jump_url = self._build_mass_jump_url(phonenum=email, keyword=keyword, type_=5)
        return self._wrap_plain_text_records(title="Email Records", data=data, request_url=request_url, jump_url=jump_url)

    # ------------------ STT (核心) ------------------

    def stt(
        self,
        sid: Optional[str] = None,
        url: Optional[str] = None,
        __files__: Optional[List[Dict[str, Any]]] = None,
        __request__: Any = None,
    ) -> Any:
        """
        STT routing:
          - sid/url:  GET  /ai/stt?sid=... or ?url=...
          - file:     POST /ai/stt multipart(file)
        Return: backend AjaxResult.data (e.g. wavPath, text, ...)
        """

        self.logger.info(f"[STT] ENTER sid={sid}, url={url}, files_count={(len(__files__) if __files__ else 0)}")

        # ----- 1) sid/url -----
        if sid or url:
            self.logger.info(f"[STT] mode=GET sid={sid} url={url}")
            params = {"sid": sid, "url": url}
            data, req_url = self._get("/ai/stt", params, timeout=self.valves.stt_timeout_sec)
            self.logger.info(f"[STT] GET success request_url={req_url}")
            return data

        # ----- 2) file upload from __files__ -----
        if __files__:
            self.logger.info(f"[STT] Raw __files__ = {__files__}")

            audio = self._pick_audio_from_files(__files__)
            self.logger.info(f"[STT] Picked audio = {audio}")

            if not audio:
                self.logger.warning("[STT] No audio detected in __files__")
                return self._need_more_input(
                    "Please upload an audio file (.wav/.mp3/.m4a...) or provide sid/url.",
                    ["__files__", "sid", "url"],
                )

            # 兼容更多字段位置
            f = audio.get("file") or {}
            fdata = f.get("data") or {}

            filename = audio.get("name") or f.get("filename") or f.get("name") or "audio.wav"
            content_type = (audio.get("content_type") or audio.get("type") or f.get("content_type") or "").strip() or None

            # Open WebUI 某些版本会提供本地 path
            file_path = fdata.get("path") or f.get("path") or audio.get("path")

            self.logger.info(
                f"[STT] filename={filename} content_type={content_type} file_path={file_path} "
                f"exists={bool(file_path and os.path.exists(str(file_path)))}"
            )

            # 2.1 同机/同容器：直接用 path 上传后端
            if file_path and os.path.exists(str(file_path)):
                self.logger.info("[STT] branch=LOCAL_PATH")
                return self._post_multipart_path(
                    "/ai/stt",
                    str(file_path),
                    field_name="file",
                    extra_form={},
                    timeout=self.valves.stt_timeout_sec,
                )

            # 2.2 没 path：尝试从 url / id 走 Open WebUI 下载再上传后端
            file_url_or_id = (
                audio.get("url")
                or f.get("url")
                or f.get("id")
                or audio.get("id")
                or audio.get("file_id")
                or f.get("file_id")
            )

            self.logger.info(f"[STT] file_url_or_id={file_url_or_id}")

            if not file_url_or_id:
                self.logger.error("[STT] No usable file url/id from Open WebUI")
                return {
                    "error": "FILE_URL_NOT_AVAILABLE",
                    "message": "Open WebUI did not provide file url/id/path.",
                    "debug": {
                        "audio_keys": list(audio.keys()),
                        "file_keys": list(f.keys()),
                        "file_data_keys": list(fdata.keys()),
                    },
                }

            try:
                base = self._infer_webui_base_url(__request__)
                self.logger.info(f"[STT] inferred webui_base={base}")

                content, dl_debug = self._download_openwebui_file(file_url_or_id, __request__=__request__)
                self.logger.info(f"[STT] Download success bytes={len(content)} dl_debug={dl_debug}")

            except Exception as e:
                self.logger.exception("[STT] Download from Open WebUI FAILED")
                return {
                    "error": "FAILED_TO_DOWNLOAD_FILE",
                    "message": str(e),
                    "file_url_or_id": str(file_url_or_id),
                }

            self.logger.info("[STT] branch=UPLOAD_BYTES_TO_BACKEND")
            try:
                result = self._post_multipart_bytes(
                    "/ai/stt",
                    filename=filename,
                    content=content,
                    content_type=content_type,
                    field_name="file",
                    extra_form={},
                    timeout=self.valves.stt_timeout_sec,
                )
                self.logger.info("[STT] POST multipart-bytes success")
                return result
            except Exception as e:
                self.logger.exception("[STT] Upload bytes to backend FAILED")
                return {
                    "error": "FAILED_TO_UPLOAD_TO_BACKEND",
                    "message": str(e),
                }

        # ----- 3) nothing -----
        self.logger.warning("[STT] No sid/url/__files__ provided")
        return self._need_more_input(
            "To run STT, please upload an audio file or provide sid or url.",
            ["__files__", "sid", "url"],
        )

    # ------------------ STT: 手动兜底工具（排查时非常好用） ------------------

    def stt_by_file_id(self, file_id: Optional[str] = None, __request__: Any = None) -> Any:
        """
        兜底入口：你可以手动把 Open WebUI 的 file_id 贴进来做转写。
        用途：
          - 模型没触发 tool call 时，你至少能手动跑通链路
          - 用于定位：Open WebUI 文件是否能下载、后端 /ai/stt 是否可用
        """
        if not file_id:
            return self._need_more_input("Please provide Open WebUI file_id.", ["file_id"])

        self.logger.info(f"[STT_BY_FILE_ID] ENTER file_id={file_id}")
        try:
            content, dl_debug = self._download_openwebui_file(file_id, __request__=__request__)
            self.logger.info(f"[STT_BY_FILE_ID] download ok bytes={len(content)} dl_debug={dl_debug}")
        except Exception as e:
            self.logger.exception("[STT_BY_FILE_ID] download failed")
            return {"error": "FAILED_TO_DOWNLOAD_FILE", "message": str(e), "file_id": str(file_id)}

        # filename 不知道就给个默认
        try:
            result = self._post_multipart_bytes(
                "/ai/stt",
                filename=f"{file_id}.wav",
                content=content,
                field_name="file",
                timeout=self.valves.stt_timeout_sec,
            )
            self.logger.info("[STT_BY_FILE_ID] upload ok")
            return result
        except Exception as e:
            self.logger.exception("[STT_BY_FILE_ID] upload to backend failed")
            return {"error": "FAILED_TO_UPLOAD_TO_BACKEND", "message": str(e)}

    def stt_by_path(self, file_path: Optional[str] = None) -> Any:
        """
        兜底入口：如果你知道音频在本机/容器的路径，可直接上传给后端 /ai/stt。
        """
        if not file_path:
            return self._need_more_input("Please provide local file_path.", ["file_path"])

        file_path = str(file_path).strip()
        self.logger.info(f"[STT_BY_PATH] ENTER file_path={file_path}")

        if not os.path.exists(file_path):
            return {"error": "FILE_NOT_FOUND", "message": f"File not found: {file_path}"}

        try:
            result = self._post_multipart_path(
                "/ai/stt",
                file_path,
                field_name="file",
                timeout=self.valves.stt_timeout_sec,
            )
            self.logger.info("[STT_BY_PATH] upload ok")
            return result
        except Exception as e:
            self.logger.exception("[STT_BY_PATH] upload failed")
            return {"error": "FAILED_TO_UPLOAD_TO_BACKEND", "message": str(e)}

    # ------------------ Export person Word ------------------

    def exportPerson(self, idNo: Optional[str] = None) -> Any:
        """
        Export person profile as a Word document.
        Required: idNo
        Return a MARKDOWN LINK so the URL is not shown as plain text.
        """
        if not idNo:
            return self._need_more_input("To export the person profile to Word, please provide: idNo.", ["idNo"])

        export_url = self._build_export_person_word_url(str(idNo).strip())
        return f"✅ Export is ready: [Download Word]({export_url})"
