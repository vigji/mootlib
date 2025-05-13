import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

from mootlib.scrapers.common_markets import (
    BaseMarket,
    BaseScraper,
    MarketFilter,
    PooledMarket,
)

VALID_MARKETS_FILTER = MarketFilter(min_n_forecasters=40)

BASE_URL = "https://www.gjopen.com"
QUESTIONS_URL = f"{BASE_URL}/questions"
LOGIN_URL = f"{BASE_URL}/users/sign_in"


@dataclass
class GJOpenAnswer:
    """Dataclass for GJOpen answers."""

    name: str
    probability: float | None = None


@dataclass
class GJOpenMarket(BaseMarket):
    """Dataclass for GJOpen markets."""

    id: str
    question: str
    published_at: str
    predictors_count: int
    comments_count: int
    description: str
    binary: bool
    continuous_scored: bool
    outcomes: list[GJOpenAnswer]
    formatted_outcomes: str
    url: str
    q_type: str

    @classmethod
    def from_gjopen_question_data(
        cls,
        q_props: dict,
        question_url: str,
    ) -> "GJOpenMarket | None":
        """Create a GJOpenMarket from GJOpen question data."""
        if not q_props:
            return None

        outcomes_data = q_props.get("answers", [])
        outcomes_list = [
            GJOpenAnswer(
                name=a.get("name"),
                probability=a.get("probability"),
            )
            for a in outcomes_data
        ]

        # Format outcomes with proper line breaks
        outcomes_parts = []
        for a in outcomes_list:
            prob_str = (
                f"{a.probability * 100:.1f}%" if a.probability is not None else "N/A"
            )
            outcomes_parts.append(f"{a.name.strip()}: {prob_str}")

        formatted_outcomes_str = (
            "; ".join(outcomes_parts).replace("\n", "").replace("\r", "")
        )

        return cls(
            id="gjopen_" + str(q_props.get("id")),
            question=q_props.get("name", ""),
            published_at=q_props.get("published_at"),
            predictors_count=q_props.get("predictors_count"),
            comments_count=q_props.get("comments_count"),
            description=q_props.get("description", ""),
            binary=bool(q_props.get("binary?")),
            continuous_scored=bool(q_props.get("continuous_scored?")),
            outcomes=outcomes_list,
            url=question_url,
            q_type=q_props.get("type"),
            formatted_outcomes=formatted_outcomes_str,
        )

    def to_pooled_market(self) -> PooledMarket:
        """Convert a GJOpenMarket to a PooledMarket."""
        outcome_names = [ans.name for ans in self.outcomes]
        outcome_probs = [ans.probability for ans in self.outcomes]

        return PooledMarket(
            id=self.id,
            question=self.question,
            outcomes=outcome_names,
            outcome_probabilities=outcome_probs,
            formatted_outcomes=self.formatted_outcomes,
            url=self.url,
            published_at=BaseMarket.parse_datetime_flexible(self.published_at),
            source_platform="GJOpen",
            volume=None,  # Not available directly from GJOpen API structure shown
            n_forecasters=self.predictors_count,
            comments_count=self.comments_count,
            original_market_type=self.q_type,
            is_resolved=None,  # No such field in GJOpen API
            raw_market_data=self,
        )


class GoodJudgmentOpenScraper(BaseScraper):
    """Scrapes market data from Good Judgment Open."""

    BASE_URL = "https://www.gjopen.com"
    QUESTIONS_URL = f"{BASE_URL}/questions"
    LOGIN_URL = f"{BASE_URL}/users/sign_in"

    MAX_PAGES = 20
    PAUSE_AFTER_PAGE = 0.6
    PAUSE_AFTER_MARKET = 0.7

    def __init__(self, email: str | None = None, password: str | None = None) -> None:
        """Initialize scraper with optional credentials."""
        self.session = None
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; PythonScraper/1.0)"}

        env_email = os.getenv("GJO_EMAIL")
        env_password = os.getenv("GJO_PASSWORD")

        if email and password:
            self.email = email
            self.password = password
        elif env_email and env_password:
            self.email = env_email
            self.password = env_password
        else:
            msg = "No credentials provided for GJOpen"
            raise ValueError(msg)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        await self._login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _login(self) -> None:
        """Log into Good Judgment Open."""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        try:
            async with self.session.get(self.LOGIN_URL, timeout=10) as response:
                response.raise_for_status()
                login_page = await response.text()
        except aiohttp.ClientError as e:
            msg = "Failed to fetch login page"
            raise ConnectionError(msg) from e

        soup = BeautifulSoup(login_page, "html.parser")
        csrf_token_tag = soup.select_one('meta[name="csrf-token"]')
        if not csrf_token_tag or not csrf_token_tag.get("content"):
            msg = "Could not find CSRF token on login page"
            raise ValueError(msg)

        csrf_token = csrf_token_tag["content"]
        login_data = {
            "user[email]": self.email,
            "user[password]": self.password,
            "authenticity_token": csrf_token,
        }

        try:
            async with self.session.post(
                self.LOGIN_URL,
                data=login_data,
                timeout=10,
            ) as response:
                response.raise_for_status()
                resp_text = await response.text()
        except aiohttp.ClientError as e:
            msg = "Login request failed"
            raise ConnectionError(msg) from e

        if "Invalid Email or password" in resp_text or "sign_in" in str(response.url):
            msg = "Login failed - please check credentials"
            raise ValueError(msg)

    async def _fetch_question_links_for_page(
        self, page: int | None = None
    ) -> list[str]:
        """Fetch all question links from a given results page."""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        url = f"{self.QUESTIONS_URL}?sort=predictors_count&sort_dir=desc"
        if page is not None:
            url = f"{url}&page={page}"

        try:
            async with self.session.get(url, timeout=10) as response:
                response.raise_for_status()
                resp_text = await response.text()
        except aiohttp.ClientError:
            return []

        soup = BeautifulSoup(resp_text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"/questions/\d+"))
        return [urljoin(self.BASE_URL, link["href"]) for link in links]

    async def _fetch_market_data_for_url(
        self,
        question_url: str,
    ) -> GJOpenMarket | None:
        """Fetch and parse market data for a single question URL."""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        try:
            async with self.session.get(
                question_url,
                timeout=10,
            ) as response:
                response.raise_for_status()
                resp_text = await response.text()
        except aiohttp.ClientError:
            return None

        soup = BeautifulSoup(resp_text, "html.parser")
        react_class = "FOF.Forecast.PredictionInterfaces.OpinionPoolInterface"
        react_div = soup.find(
            "div",
            {"data-react-class": react_class},
        )

        if not (react_div and react_div.has_attr("data-react-props")):
            return None

        try:
            props = json.loads(react_div["data-react-props"])
        except json.JSONDecodeError:
            return None

        q_props = props.get("question", {})
        return GJOpenMarket.from_gjopen_question_data(q_props, question_url)

    async def fetch_markets(
        self,
        only_open: bool = True,
        min_n_forecasters: int = VALID_MARKETS_FILTER.min_n_forecasters,
        **kwargs: Any,
    ) -> list[GJOpenMarket]:
        """Fetch markets from Good Judgment Open.

        Args:
            only_open: If True, attempts to fetch only open markets.
                      Note: GJOpen API doesn't directly support filtering by status.
            min_n_forecasters: Minimum number of forecasters required.
            **kwargs: Supports 'max_pages' (int, default 15) for pagination.

        Returns:
            A list of GJOpenMarket objects.
        """
        all_markets_data: list[GJOpenMarket] = []

        for page_num in tqdm(
            range(1, self.MAX_PAGES + 1), desc="Scraping GJOpen pages"
        ):
            question_links = await self._fetch_question_links_for_page(page_num)
            if not question_links:
                break

            market_objs_on_page: list[GJOpenMarket] = []
            for i, link in enumerate(question_links):
                try:
                    market_obj = await self._fetch_market_data_for_url(link)
                    if market_obj and market_obj.question not in [
                        m.question for m in all_markets_data
                    ]:
                        market_objs_on_page.append(market_obj)
                except Exception:
                    pass
                finally:
                    if i < len(question_links) - 1:
                        time.sleep(self.PAUSE_AFTER_MARKET)

            if not market_objs_on_page and question_links:
                break

            all_markets_data.extend(market_objs_on_page)

            # Break if we've seen enough low-forecaster markets
            if all(
                market.predictors_count < min_n_forecasters
                for market in market_objs_on_page
            ):
                break

            if not market_objs_on_page and not question_links:
                break

            time.sleep(self.PAUSE_AFTER_PAGE)

        return all_markets_data


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        try:
            scraper = GoodJudgmentOpenScraper()

            time.time()

            async with scraper:
                pooled_markets = await scraper.get_pooled_markets(only_open=True)

                time.time()

                if pooled_markets:
                    pd.DataFrame([pm.__dict__ for pm in pooled_markets])
                else:
                    pass

        except (FileNotFoundError, ValueError, ConnectionError):
            pass

    asyncio.run(_main())
