"""
title: ESCT AI Insight
author: OneCloudTech
description: Call backend /ai APIs to get person base info, family, contacts, social accounts, locations, VoIP/SMS/Email records, etc.
version: 0.3.0
requirements: requests
"""

from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import requests
import logging


class Tools:
    """
    Tool class: map Open WebUI Tool calls to backend AIController APIs.
    Base path of AIController: /ai
    """

    def __init__(self):
        self.citation = False
        self.valves = self.Valves()

        # ----- logging setup -----
        # You can adjust level to DEBUG/INFO as needed.
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

    # ------------ common helper methods ------------

    def _build_url(self, path: str) -> str:
        base = self.valves.backend_base_url.rstrip("/")
        return f"{base}{path}"

    def _clean_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in params.items() if v is not None and v != ""}

    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        """
        Perform actual GET request to backend.
        Expected AjaxResult structure:
        { "code": 200, "msg": "...", "data": ... }
        """
        url = self._build_url(path)
        query = self._clean_params(params)

        # log request
        self.logger.info(f"Calling backend GET {url} with params={query}")

        try:
            resp = requests.get(url, params=query, timeout=10)
            self.logger.info(
                f"Backend response status={resp.status_code} for {url}"
            )
            resp.raise_for_status()
        except Exception as e:
            self.logger.error(f"HTTP error while calling {url}: {e}")
            raise

        try:
            body = resp.json()
        except Exception as e:
            self.logger.error(f"Failed to parse JSON from {url}: {e}")
            raise

        # log truncated body for debugging
        self.logger.debug(f"Backend raw JSON body from {url}: {body}")

        if isinstance(body, dict) and "code" in body:
            if body.get("code") != 200:
                msg = body.get("msg")
                self.logger.error(
                    f"Backend business error for {url}: code={body.get('code')}, msg={msg}"
                )
                raise Exception(f"Backend error: {msg}")
            self.logger.info(f"Backend call {url} succeeded.")
            return body.get("data")

        # no standard AjaxResult, just return body
        self.logger.warning(
            f"Backend {url} did not return AjaxResult structure; returning raw body."
        )
        return body

    def _need_more_input(
        self,
        message: str,
        missing_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        When required parameters are missing, we do NOT call backend.
        Instead, return a structured message so the model can ask the user
        for the missing info (in English by default).
        """
        payload = {
            "error": "MISSING_REQUIRED_PARAMS",
            "message": message,
            "missing_fields": missing_fields or [],
        }
        # log missing param situation
        self.logger.warning(
            f"Missing required params: {payload['missing_fields']}, message='{message}'"
        )
        return payload

    # ------------ API mappings to AIController ------------

    # 1. /ai/baseinfo
    def get_person_baseinfo(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query person base info (/ai/baseinfo).

        Required: at least one of id / passport / phonenum.
        """
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query base info, please provide at least one of: ID number, passport, or phone number.",
                ["id", "passport", "phonenum"],
            )

        return self._get(
            "/ai/baseinfo",
            {"id": id, "passport": passport, "phonenum": phonenum},
        )

    # 2. /ai/family
    def get_family_members(
        self,
        id: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query family members (/ai/family).

        Required: ID number or phone number.
        """
        if not id and not phonenum:
            return self._need_more_input(
                "To query family members, please provide an ID number or a phone number.",
                ["id", "phonenum"],
            )

        return self._get(
            "/ai/family",
            {"id": id, "phonenum": phonenum},
        )

    # 3. /ai/cr
    def get_cr_info(
        self,
        id: Optional[str] = None,
        passport: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query CR information (/ai/cr).

        Required: at least one of id / passport / phonenum.
        """
        if not id and not passport and not phonenum:
            return self._need_more_input(
                "To query CR information, please provide at least one of: ID number, passport, or phone number.",
                ["id", "passport", "phonenum"],
            )

        return self._get(
            "/ai/cr",
            {"id": id, "passport": passport, "phonenum": phonenum},
        )

    # 4. /ai/contact
    def get_top_contacts(
        self,
        id: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query TOP contacts (/ai/contact).

        Required: ID number or phone number.
        """
        if not id and not phonenum:
            return self._need_more_input(
                "To query top contacts, please provide an ID number or a phone number.",
                ["id", "phonenum"],
            )

        return self._get(
            "/ai/contact",
            {"id": id, "phonenum": phonenum},
        )

    # 5. /ai/car
    def get_vehicles(
        self,
        id: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query vehicle information (/ai/car).

        Required: ID number or phone number.
        """
        if not id and not phonenum:
            return self._need_more_input(
                "To query vehicle information, please provide an ID number or a phone number.",
                ["id", "phonenum"],
            )

        return self._get(
            "/ai/car",
            {"id": id, "phonenum": phonenum},
        )

    # 6. /ai/social
    def get_social_accounts(
        self,
        id: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query social account aggregation (/ai/social).

        Required: ID number or phone number.
        """
        if not id and not phonenum:
            return self._need_more_input(
                "To query social accounts, please provide an ID number or a phone number.",
                ["id", "phonenum"],
            )

        return self._get(
            "/ai/social",
            {"id": id, "phonenum": phonenum},
        )

    # 7. /ai/location
    def get_locations(
        self,
        id: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query location list (/ai/location).

        Required: ID number or phone number.
        """
        if not id and not phonenum:
            return self._need_more_input(
                "To query locations, please provide an ID number or a phone number.",
                ["id", "phonenum"],
            )

        return self._get(
            "/ai/location",
            {"id": id, "phonenum": phonenum},
        )

    # 8. /ai/voip
    def search_voip_records(
        self,
        keyword: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query VoIP call records (/ai/voip).

        Required: at least one of keyword / phone number.
        """
        if not keyword and not phonenum:
            return self._need_more_input(
                "To query VoIP call records, please provide a keyword or a phone number.",
                ["keyword", "phonenum"],
            )

        return self._get(
            "/ai/voip",
            {"keyword": keyword, "phonenum": phonenum},
        )

    # 9. /ai/sms
    def search_sms_records(
        self,
        keyword: Optional[str] = None,
        phonenum: Optional[str] = None,
    ) -> Any:
        """
        Query SMS records (/ai/sms).

        Required: at least one of keyword / phone number.
        """
        if not keyword and not phonenum:
            return self._need_more_input(
                "To query SMS records, please provide a keyword or a phone number.",
                ["keyword", "phonenum"],
            )

        return self._get(
            "/ai/sms",
            {"keyword": keyword, "phonenum": phonenum},
        )

    # 10. /ai/email
    def search_email_records(
        self,
        keyword: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Any:
        """
        Query email records (/ai/email).

        Required: at least one of keyword / email address.
        """
        if not keyword and not email:
            return self._need_more_input(
                "To query email records, please provide a keyword or an email address.",
                ["keyword", "email"],
            )

        return self._get(
            "/ai/email",
            {"keyword": keyword, "email": email},
        )
