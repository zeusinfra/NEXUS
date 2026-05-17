import asyncio


class LifecycleManager:
    """
    Gerenciador de tarefas de background do NEXUS.
    Recebe o dicionário de globais do web_gui para manipular o estado da aplicação sem causar importações circulares.
    """

    def __init__(self, web_globals: dict):
        self.g = web_globals
        self._voice_task_running = False

    async def boot_greeting(self):
        try:
            await asyncio.sleep(3)
            prompt = "O sistema NEXUS acaba de ser iniciado. Crie uma mensagem falada muito curta de boas-vindas (máximo 1 frase). Seja técnico, direto e natural."
            reply = await self.g["call_ollama"](prompt)
            if reply and reply.strip():
                await self.g["speak"](reply)
            else:
                await self.g["speak"]("NEXUS online. Pronto para operar.")
        except Exception as e:
            print(f"Erro na saudação inicial: {e}")
            await self.g["speak"]("NEXUS online. Pronto para operar.")

    async def web_sensing_loop(self):
        while True:
            await asyncio.sleep(5.0)
            url = self.g.get("get_browser_history", lambda: None)()
            if url:
                web_context = self.g["classify_web_context"](url)
                event = {
                    "type": "FILE_EVENT",
                    "event": "WEB_VISIT",
                    "path": url,
                    "project": "WEB_SENSING",
                }
                try:
                    self.g["assimilate_access_event"](url, event)
                except Exception:
                    pass
                await self.g["enqueue_event"](event)
                await self.g["broadcast_message"](
                    {
                        "type": "WEB_EVENT",
                        "url": url,
                        "project": "WEB_SENSING",
                        "domain": web_context["domain"],
                        "category": web_context["category"],
                        "path_hint": web_context["path"],
                        "log": {
                            "channel": "web",
                            "title": "Navegação detectada",
                            "detail": f"{web_context['domain']} entrou no radar.",
                            "meta": f"categoria={web_context['category']}",
                        },
                    }
                )

    async def safe_voice_task(self):
        try:
            voice_module = self.g["voice_module"]
            voice_module.broadcast = self.g["broadcast_message"]
            voice_module.llm_callback = self.g.get("handle_voice_input")

            while True:
                if not self.g["ENABLE_VOICE"] or self.g["LOW_MEM_ACTIVE"]:
                    if voice_module.is_listening:
                        voice_module.stop()
                        self._voice_task_running = False
                    await asyncio.sleep(5.0)
                    continue
                if self.g["resource_control"].is_critical():
                    if voice_module.is_listening:
                        print(
                            "[NEXUS RESOURCE ALERT] Critical Load. Pausing Voice Sensing..."
                        )
                        voice_module.stop()
                        self._voice_task_running = False
                    await asyncio.sleep(10.0)
                    continue

                if not voice_module.is_listening and not self._voice_task_running:
                    self._voice_task_running = True
                    print("[NEXUS] Iniciando módulo de voz local...")
                    asyncio.create_task(voice_module.run())

                await asyncio.sleep(5.0)
        except Exception as e:
            print(f"Erro crítico no safe_voice_task: {e}")
            self._voice_task_running = False

    async def low_mem_guard(self):
        while True:
            try:
                snapshot = self.g["resource_control"].get_system_snapshot()
                ram = float(snapshot.get("ram", 0.0))
            except Exception:
                ram = 0.0

            if not self.g["LOW_MEM_ACTIVE"] and ram >= self.g["LOW_MEM_ENTER_RAM"]:
                self.g["LOW_MEM_ACTIVE"] = True
                print(f"[NEXUS LOW-MEM] Entering low-mem mode (RAM={ram}%).")

                self.g["ENABLE_VOICE"] = False
                voice_module = self.g["voice_module"]
                try:
                    if voice_module.is_listening:
                        voice_module.stop()
                except Exception:
                    pass

                self.g["ENABLE_BROWSER_SENSING"] = False
                try:
                    if self.g.get("_web_sensing_task"):
                        self.g["_web_sensing_task"].cancel()
                        self.g["_web_sensing_task"] = None
                except Exception:
                    pass

                try:
                    self.g["indexing_semaphore"] = asyncio.Semaphore(1)
                except Exception:
                    pass

                try:
                    self.g["prune_synaptic_memory"](force=True)
                except Exception:
                    pass

            elif self.g["LOW_MEM_ACTIVE"] and ram <= self.g["LOW_MEM_EXIT_RAM"]:
                self.g["LOW_MEM_ACTIVE"] = False
                print(f"[NEXUS LOW-MEM] Exiting low-mem mode (RAM={ram}%).")

                if self.g["_env_flag"]("NEXUS_ENABLE_VOICE", "1"):
                    self.g["ENABLE_VOICE"] = True
                if self.g["_env_flag"]("NEXUS_ENABLE_BROWSER_SENSING", "0"):
                    self.g["ENABLE_BROWSER_SENSING"] = True
                    if self.g.get("_web_sensing_task") is None:
                        try:
                            self.g["_web_sensing_task"] = asyncio.create_task(
                                self.web_sensing_loop()
                            )
                        except Exception:
                            pass

                try:
                    self.g["indexing_semaphore"] = asyncio.Semaphore(2)
                except Exception:
                    pass

            await asyncio.sleep(3.0)
