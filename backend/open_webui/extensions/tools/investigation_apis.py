"""
title: ESCT AI Insight
author: OneCloudTech
description: 调用后端 /ai 接口，查询人员基础信息、家庭、联系人、社交账号、位置、VoIP/SMS/Email 等记录
version: 0.4.0
requirements: requests
"""

from typing import Optional, Any, Dict, List, Tuple
from pydantic import BaseModel, Field
import requests
import logging


class Tools:
    """
    工具类：把 Open WebUI Tool 调用映射到后端 AIController 接口。
    AIController Base Path: /ai

    重要提示（给模型/调用方看的约束）：
    - 如果工具返回对象里包含 {"found": true, "data": ...}，
      即使 data 里没有出现原始查询参数（例如 phone 字段没回显），也必须视为“查到了”。
    - 只有在 found 为 false，或返回明确 error 时，才能说“未找到”。
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

    class Valves(BaseModel):
        backend_base_url: str = Field(
            "http://192.168.80.185:8654",
            description="后端 Spring Boot Base URL（不含 /ai），例如：http://192.168.80.185:8654",
        )

    # ------------------ 通用工具方法 ------------------

    def _build_url(self, path: str) -> str:
        """拼接后端请求 URL（不含 querystring）"""
        base = self.valves.backend_base_url.rstrip("/")
        return f"{base}{path}"

    def _clean_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """清理参数：过滤 None / 空字符串"""
        return {k: v for k, v in params.items() if v is not None and v != ""}

    def _normalize_found_flag(self, data: Any) -> bool:
        """
        判断是否“查到”：
        - data 为 None -> 未找到
        - data 是空 list / 空 dict -> 未找到
        - 其它情况 -> 找到
        """
        if data is None:
            return False
        if isinstance(data, (list, dict)) and len(data) == 0:
            return False
        return True

    def _build_full_url_with_params(self, url: str, params: Dict[str, Any]) -> str:
        """
        生成“可直接打开”的完整 URL（含 querystring）。
        注意：使用 requests 的 PreparedRequest 来保证编码正确。
        """
        req = requests.Request("GET", url, params=params).prepare()
        return req.url

    def _get(self, path: str, params: Dict[str, Any]) -> Tuple[Any, str]:
        """
        发起 GET 请求。
        期望后端返回 AjaxResult 结构：
        { "code": 200, "msg": "...", "data": ... }

        返回：(data, request_url)
        - data: body.data 或 raw body
        - request_url: 最终请求 URL（含 querystring，可直接打开/复制）
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

        # AjaxResult 结构处理
        if isinstance(body, dict) and "code" in body:
            if body.get("code") != 200:
                msg = body.get("msg")
                self.logger.error(f"Backend business error for {request_url}: code={body.get('code')}, msg={msg}")
                raise Exception(f"Backend error: {msg}")
            self.logger.info(f"Backend call succeeded: {request_url}")
            return body.get("data"), request_url

        # 非标准结构
        self.logger.warning(f"Backend did not return AjaxResult; returning raw body. url={request_url}")
        return body, request_url

    def _need_more_input(self, message: str, missing_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        当必填参数缺失时：不请求后端，直接返回结构化错误，方便前端/模型提示用户补充信息。
        """
        payload = {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }
        self.logger.warning(f"Missing required params: {payload['missing_fields']}, message='{message}'")
        return payload

    def _wrap_result(
        self,
        api_path: str,
        raw_params: Dict[str, Any],
        data: Any,
        request_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        统一包装返回结构：
        - api: 调用的接口路径
        - query_params: 清洗后的查询参数
        - request_url: 可直接打开的完整 URL（含 querystring）
        - found: 是否查到（由 data 是否为空决定）
        - data: 后端返回的数据
        """
        query_params = self._clean_params(raw_params)
        found = self._normalize_found_flag(data)

        wrapped = {
            "api": api_path,
            "query_params": query_params,
            "request_url": request_url,   # ⭐ 关键：每个接口都带一个可打开 URL
            "found": found,
            "data": data,
        }

        self.logger.info(f"API {api_path} finished. found={found}, query_params={query_params}, url={request_url}")
        return wrapped

    # ------------------ AIController API 映射 ------------------

    # 1) /ai/baseinfo
    def get_person_baseinfo(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        查询人员基础信息（/ai/baseinfo）

        必填：id / passport / phonenum 三选一（至少一个）。

        模型提示：
        - 返回 {"found": true, "data": {...}} 就视为查到，
          不要因为 data 里没回显手机号就说“手机号不存在”。
        """
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "查询基础信息请至少提供一个：身份证号(id) / 护照号(passport) / 手机号(phonenum)。",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/baseinfo", raw_params)
        return self._wrap_result("/ai/baseinfo", raw_params, data, request_url)

    # 2) /ai/family
    def get_family_members(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询家庭成员（/ai/family），必填：身份证号(id)或手机号(phonenum)"""
        if not id and not phonenum:
            return self._need_more_input(
                "查询家庭成员请提供：身份证号(id) 或 手机号(phonenum)。",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/family", raw_params)
        return self._wrap_result("/ai/family", raw_params, data, request_url)

    # 3) /ai/cr
    def get_cr_info(self, id: Optional[str] = None, passport: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询 CR 信息（/ai/cr），必填：id / passport / phonenum 三选一（至少一个）"""
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "查询 CR 信息请至少提供一个：身份证号(id) / 护照号(passport) / 手机号(phonenum)。",
                ["id", "passport", "phonenum"],
            )

        raw_params = {"id": id, "passport": passport, "phonenum": phonenum}
        data, request_url = self._get("/ai/cr", raw_params)
        return self._wrap_result("/ai/cr", raw_params, data, request_url)

    # 4) /ai/contact
    def get_top_contacts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询 TOP 联系人（/ai/contact），必填：身份证号(id)或手机号(phonenum)"""
        if not id and not phonenum:
            return self._need_more_input(
                "查询 TOP 联系人请提供：身份证号(id) 或 手机号(phonenum)。",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/contact", raw_params)
        return self._wrap_result("/ai/contact", raw_params, data, request_url)

    # 5) /ai/car
    def get_vehicles(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询车辆信息（/ai/car），必填：身份证号(id)或手机号(phonenum)"""
        if not id and not phonenum:
            return self._need_more_input(
                "查询车辆信息请提供：身份证号(id) 或 手机号(phonenum)。",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/car", raw_params)
        return self._wrap_result("/ai/car", raw_params, data, request_url)

    # 6) /ai/social
    def get_social_accounts(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询社交账号聚合（/ai/social），必填：身份证号(id)或手机号(phonenum)"""
        if not id and not phonenum:
            return self._need_more_input(
                "查询社交账号请提供：身份证号(id) 或 手机号(phonenum)。",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/social", raw_params)
        return self._wrap_result("/ai/social", raw_params, data, request_url)

    # 7) /ai/location
    def get_locations(self, id: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询位置列表（/ai/location），必填：身份证号(id)或手机号(phonenum)"""
        if not id and not phonenum:
            return self._need_more_input(
                "查询位置列表请提供：身份证号(id) 或 手机号(phonenum)。",
                ["id", "phonenum"],
            )

        raw_params = {"id": id, "phonenum": phonenum}
        data, request_url = self._get("/ai/location", raw_params)
        return self._wrap_result("/ai/location", raw_params, data, request_url)

    # 8) /ai/voip
    def search_voip_records(self, keyword: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询 VoIP 通话记录（/ai/voip），必填：keyword 或 phonenum 至少一个"""
        if not keyword and not phonenum:
            return self._need_more_input(
                "查询 VoIP 通话记录请提供：关键词(keyword) 或 手机号(phonenum)。",
                ["keyword", "phonenum"],
            )

        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/voip", raw_params)
        return self._wrap_result("/ai/voip", raw_params, data, request_url)

    # 9) /ai/sms
    def search_sms_records(self, keyword: Optional[str] = None, phonenum: Optional[str] = None) -> Any:
        """查询短信记录（/ai/sms），必填：keyword 或 phonenum 至少一个"""
        if not keyword and not phonenum:
            return self._need_more_input(
                "查询短信记录请提供：关键词(keyword) 或 手机号(phonenum)。",
                ["keyword", "phonenum"],
            )

        raw_params = {"keyword": keyword, "phonenum": phonenum}
        data, request_url = self._get("/ai/sms", raw_params)
        return self._wrap_result("/ai/sms", raw_params, data, request_url)

    # 10) /ai/email
    def search_email_records(self, keyword: Optional[str] = None, email: Optional[str] = None) -> Any:
        """查询邮件记录（/ai/email），必填：keyword 或 email 至少一个"""
        if not keyword and not email:
            return self._need_more_input(
                "查询邮件记录请提供：关键词(keyword) 或 邮箱地址(email)。",
                ["keyword", "email"],
            )

        raw_params = {"keyword": keyword, "email": email}
        data, request_url = self._get("/ai/email", raw_params)
        return self._wrap_result("/ai/email", raw_params, data, request_url)
