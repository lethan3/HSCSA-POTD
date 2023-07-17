from __future__ import annotations

import asyncio
from collections import namedtuple
from typing import Any, Dict, Iterable, Literal, Optional, Union

import aiohttp


class CodeforcesAPI:
    def __init__(self: CodeforcesAPI):
        pass

    async def api_response(
        self: CodeforcesAPI, url: str, params: Optional[Union[Dict[str, Any], Iterable[str]]] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            tries = 0
            async with aiohttp.ClientSession() as session:
                while tries < 5:
                    tries += 1
                    async with session.get(url, params=params) as resp:
                        response = {}
                        if resp.status == 503:
                            response["status"] = "FAILED"
                            response["comment"] = "limit exceeded"
                        else:
                            response = await resp.json()

                        if (
                            response["status"] == "FAILED"
                            and "limit exceeded" in response["comment"].lower()
                        ):
                            await asyncio.sleep(1)
                        else:
                            return response
                else:
                    return response
        except Exception as e:
            return None

    async def check_handle(
        self: CodeforcesAPI, handle: str
    ) -> Iterable[Union[bool, str, None]]:
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if not response:
            return [False, "Codeforces API Error"]
        if response["status"] != "OK":
            return [False, response["comment"]]
        else:
            return [True, response["result"][0]]

    async def get_contest_list(
        self: CodeforcesAPI,
    ) -> Union[Iterable[Dict[str, str]], Literal[False]]:
        url = "https://codeforces.com/api/contest.list"
        response = await self.api_response(url)
        if not response:
            return False
        else:
            return response["result"]

    async def get_problem_list(
        self: CodeforcesAPI,
    ) -> Union[Iterable[Dict[str, str]], Literal[False]]:
        url = "https://codeforces.com/api/problemset.problems"
        response = await self.api_response(url)
        if not response:
            return False
        else:
            return response["result"]["problems"]

    async def get_user_problems(
        self: CodeforcesAPI, handle: str, count: int = None
    ) -> Iterable[Union[bool, str, Iterable[Any], None]]:
        url = f"https://codeforces.com/api/user.status?handle={handle}"
        if count:
            url += f"&from=1&count={count}"
        response = await self.api_response(url)
        if not response:
            return [False, "CF API Error"]
        if response["status"] != "OK":
            return [False, response["comment"]]
        try:
            data = []
            Problem = namedtuple(
                "Problem", "id index name type rating, sub_time, verdict"
            )
            for x in response["result"]:
                y = x["problem"]
                if "rating" not in y:
                    continue
                if "verdict" not in x:
                    x["verdict"] = None
                data.append(
                    Problem(
                        y["contestId"],
                        y["index"],
                        y["name"],
                        y["type"],
                        y["rating"],
                        x["creationTimeSeconds"],
                        x["verdict"],
                    )
                )
            return [True, data]
        except Exception as e:
            return [False, str(e)]

    async def get_rating(
        self: CodeforcesAPI, handle: str
    ) -> Optional[Union[int, Literal[0]]]:
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if response is None:
            return None
        if "rating" in response["result"][0]:
            return response["result"][0]["rating"]
        else:
            return 0

    async def get_first_name(self: CodeforcesAPI, handle: str) -> Optional[str]:
        url = f"https://codeforces.com/api/user.info?handles={handle}"
        response = await self.api_response(url)
        if not response or "firstName" not in response["result"][0]:
            return None
        return response["result"][0]["firstName"]

    async def get_user_info(self: CodeforcesAPI, handles: Iterable[str]) -> Optional[Dict[str, Any]]:
        url = f"https://codeforces.com/api/user.info"
        response = await self.api_response(url, handles)
        if not response: # Codeforces API Error
            return None
        return response["result"]
