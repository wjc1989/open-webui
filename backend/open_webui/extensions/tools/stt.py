"""
title: UM STT
author: OneCloudTech
description: STT tool for UM system. Calls /ai/stt by parsing playNewJsp URL or .wav URL. Kept separate to avoid impacting other tools.
version: 0.1.0
requirements: requests
"""

from typing import Optional, Any, Dict, List, Tuple
from pydantic import BaseModel, Field
import requests
import logging
import re
import sys
from urllib.parse import urlparse, parse_qs, urlencode, quote


DEFAULT_TIMEOUT_SEC = 60
STT_TIMEOUT_SEC = 300

PLAY_URL_PATH = "/vmind/playNewJsp.do"
PLAY_BASE_URL = "https://192.168.80.185/vmind/playNewJsp.do"

WAV_URL_RE = re.compile(
    r"(https?://[^\s\"']+?\.wav)(\?[^\s\"']*)?",
    flags=re.IGNORECASE,
)


class Tools:
    """
    UM STT tool (separate).

    - Parse:
      A) playNewJsp.do?sid=...&capturetime=...
      B) playNewJsp.do?wavePath=...wav
      C) Any text that contains http(s)://...wav
    - Call backend: /ai/stt
    - Return AjaxResult-like dict (code/msg/data) and attach jump_url into data.
    """

    def __init__(self):
        self.citation = False
        self.valves = self.Valves()

        self.logger = logging.getLogger("UM_STT")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            sh = logging.StreamHandler(sys.stdout)
            sh.setLevel(logging.INFO)
            sh.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
            )
            self.logger.addHandler(sh)
        self.logger.propagate = False

        self._session = requests.Session()

    class Valves(BaseModel):
        backend_base_url: str = Field(
            "http://192.168.80.185:8654",
            description="Backend Spring Boot base URL (without /ai), e.g. http://192.168.80.185:8654",
        )

    # ------------------ helpers ------------------

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
            else:
                cleaned[k] = v
        return cleaned

    def _need_more_input(
        self, message: str, missing_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        return {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }

    def _attach_jump_url_to_ajax(self, ajax: Dict[str, Any], jump_url: str) -> Dict[str, Any]:
        if not jump_url or not isinstance(ajax, dict):
            return ajax

        data = ajax.get("data")
        if isinstance(data, dict):
            # 不破坏原结构，仅附加 jump_url
            data["jump_url"] = jump_url
            ajax["data"] = data
            return ajax

        # data 不是 dict：包一层
        ajax["data"] = {"value": data, "jump_url": jump_url}
        return ajax

    def _build_play_jump_from_wav(self, wav_url: str) -> str:
        # wavePath 里需要把完整 wav url 传进去
        return f"{PLAY_BASE_URL}?wavePath={quote(wav_url, safe=':/?&=%')}"

    def _get_ajax(
        self,
        path: str,
        params: Dict[str, Any],
        timeout_sec: int,
    ) -> Dict[str, Any]:
        """
        直接返回后端 AjaxResult 原包:
        {code, msg, data}
        """
        url = self._build_url(path)
        query = self._clean_params(params)

        self.logger.info(f"Calling backend GET {url} params={query}")
        resp = self._session.get(url, params=query, timeout=timeout_sec)
        # HTTP 级错误直接抛（方便定位）
        resp.raise_for_status()

        body = resp.json()
        if not isinstance(body, dict) or "code" not in body:
            # 非 AjaxResult：也包成 ajax 形态
            return {"code": 200, "msg": "OK", "data": body}

        return body

    # ------------------ public tool method ------------------

    def stt_auto(self, content: Optional[str] = None) -> Any:
        """
        Input: content (string)
        Supports:
          - playNewJsp.do?sid=...&capturetime=...
          - playNewJsp.do?wavePath=...wav
          - any text containing a .wav URL
        Output:
          - AjaxResult-like dict and data contains jump_url
        """
        if not content or not str(content).strip():
            return self._need_more_input(
                "To run STT, please provide a play URL (contains /vmind/playNewJsp.do) or a .wav URL.",
                ["content"],
            )

        s = str(content).strip()

        # Case A/B: playNewJsp URL
        if PLAY_URL_PATH in s:
            try:
                u = urlparse(s)
                qs = parse_qs(u.query or "")

                sid = (qs.get("sid") or qs.get("SID") or [None])[0]
                capturetime = (
                    qs.get("capturetime")
                    or qs.get("captureTime")
                    or qs.get("CAPTURETIME")
                    or [None]
                )[0]
                wave_path = (
                    qs.get("wavePath")
                    or qs.get("wavepath")
                    or qs.get("WAVEPATH")
                    or [None]
                )[0]

                jump_url = f"{PLAY_BASE_URL}?{u.query}" if u.query else PLAY_BASE_URL

                if sid and capturetime:
                    ajax = self._get_ajax(
                        "/ai/stt",
                        {"sid": sid, "capturetime": capturetime},
                        timeout_sec=STT_TIMEOUT_SEC,
                    )
                    return self._attach_jump_url_to_ajax(ajax, jump_url)

                if wave_path:
                    ajax = self._get_ajax(
                        "/ai/stt",
                        {"url": wave_path},
                        timeout_sec=STT_TIMEOUT_SEC,
                    )
                    return self._attach_jump_url_to_ajax(ajax, jump_url)

                return self._need_more_input(
                    "playNewJsp.do URL must include (sid + capturetime) OR wavePath in query string.",
                    ["sid", "capturetime", "wavePath"],
                )

            except Exception as e:
                self.logger.error(f"stt_auto parse playNewJsp.do failed: {e}")
                return {"code": 500, "msg": f"Failed to parse play URL: {e}", "data": None}

        # Case C: contains wav url
        wav_match = WAV_URL_RE.search(s)
        if wav_match:
            wav_url = wav_match.group(0)
            jump_url = self._build_play_jump_from_wav(wav_url)

            ajax = self._get_ajax(
                "/ai/stt",
                {"url": wav_url},
                timeout_sec=STT_TIMEOUT_SEC,
            )
            return self._attach_jump_url_to_ajax(ajax, jump_url)

        return self._need_more_input(
            "Unsupported content. Please provide a URL containing /vmind/playNewJsp.do or a direct .wav URL.",
            ["content"],
        )
