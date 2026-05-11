from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

from nexus_core.tools import ToolError


class _BrowserState:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._headless = True

    async def ensure(self, *, headless: Optional[bool] = None) -> None:
        async with self._lock:
            if headless is None:
                env = os.getenv("NEXUS_BROWSER_HEADLESS", "1").strip().lower()
                headless = env in {"1", "true", "yes", "on"}
            self._headless = bool(headless)

            if self._page is not None and self._context is not None:
                return

            try:
                from playwright.async_api import async_playwright  # type: ignore
            except Exception as e:
                raise ToolError(
                    "Dependência ausente: instale 'playwright' (pip) e rode 'playwright install'."
                ) from e

            self._playwright = await async_playwright().start()
            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=self._headless
                )
                self._context = await self._browser.new_context()
                self._page = await self._context.new_page()
                await self._page.set_viewport_size({"width": 1280, "height": 720})
            except Exception as e:
                await self.close()
                raise ToolError(
                    "Falha ao iniciar navegador (Chromium). Em geral: falta 'playwright install' "
                    "ou não há display para modo headless=0."
                ) from e

    async def close(self) -> None:
        async with self._lock:
            try:
                if self._context is not None:
                    await self._context.close()
            except Exception:
                pass
            try:
                if self._browser is not None:
                    await self._browser.close()
            except Exception:
                pass
            try:
                if self._playwright is not None:
                    await self._playwright.stop()
            except Exception:
                pass

            self._playwright = None
            self._browser = None
            self._context = None
            self._page = None

    @property
    def page(self):
        return self._page


_STATE = _BrowserState()


async def browser_control(parameters: dict) -> Dict[str, Any]:
    p = parameters or {}
    action = str(p.get("action") or "").strip().lower()
    if not action:
        raise ToolError("browser_control requer 'action'.")

    headless = p.get("headless", None)
    if headless is not None:
        headless = bool(headless)

    await _STATE.ensure(headless=headless)
    page = _STATE.page
    if page is None:
        raise ToolError("Browser não inicializado.")

    timeout_ms = int(p.get("timeout_ms") or 25_000)

    if action == "go_to":
        url = str(p.get("url") or "").strip()
        if not url:
            raise ToolError("go_to requer 'url'.")
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        return {"ok": True, "url": page.url}

    if action == "search":
        query = str(p.get("query") or "").strip()
        if not query:
            raise ToolError("search requer 'query'.")
        url = "https://duckduckgo.com/?q=" + _urlencode(query)
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        return {"ok": True, "url": page.url, "query": query}

    if action == "click":
        selector = str(p.get("selector") or "").strip()
        if not selector:
            raise ToolError("click requer 'selector'.")
        await page.click(selector, timeout=timeout_ms)
        return {"ok": True}

    if action == "type":
        selector = str(p.get("selector") or "").strip()
        text = str(p.get("text") or "").strip()
        if not selector:
            raise ToolError("type requer 'selector'.")
        await page.fill(selector, text, timeout=timeout_ms)
        return {"ok": True}

    if action == "scroll":
        direction = str(p.get("direction") or "down").strip().lower()
        amount = int(p.get("amount") or 3)
        dy = 300 * max(1, min(amount, 20))
        if direction == "up":
            dy = -dy
        await page.mouse.wheel(0, dy)
        return {"ok": True, "dy": dy}

    if action == "press":
        key = str(p.get("key") or "").strip()
        if not key:
            raise ToolError("press requer 'key'.")
        await page.keyboard.press(key)
        return {"ok": True, "key": key}

    if action == "get_text":
        selector = str(p.get("selector") or "body").strip()
        text = await page.inner_text(selector, timeout=timeout_ms)
        return {"ok": True, "selector": selector, "text": text[:50_000]}

    if action == "close":
        await _STATE.close()
        return {"ok": True, "closed": True}

    raise ToolError(f"Ação desconhecida em browser_control: {action}")


def _urlencode(text: str) -> str:
    try:
        from urllib.parse import quote_plus

        return quote_plus(text)
    except Exception:
        return text.replace(" ", "+")
