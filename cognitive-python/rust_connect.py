import grpc
import grpc.aio
import os
from typing import Dict, List, Optional, AsyncGenerator

# Import generated stubs
try:
    from .stubs import nexus_core_pb2
    from .stubs import nexus_core_pb2_grpc
except ImportError:
    import sys

    sys.path.append(os.path.dirname(__file__))
    from stubs import nexus_core_pb2
    from stubs import nexus_core_pb2_grpc


class RustConnect:
    """
    Async gRPC Client for ZEUS Core (Rust).
    Replaces subprocess calls with remote Rust execution.
    """

    def __init__(self, host: str = "localhost", port: int = 50051):
        self.target = f"{host}:{port}"
        self.channel: Optional[grpc.aio.Channel] = None
        self.stub = None

    async def connect(self):
        """Establishes connection to Rust Core."""
        self.channel = grpc.aio.insecure_channel(self.target)
        self.stub = nexus_core_pb2_grpc.ZeusCoreStub(self.channel)
        print(f"🔗 Connected to ZEUS CORE (Rust) at {self.target}")

    async def disconnect(self):
        """Closes connection."""
        if self.channel:
            await self.channel.close()
            print("🔌 Disconnected from ZEUS CORE")

    async def execute_command(
        self, command: str, target_files: List[str] = None
    ) -> Dict:
        """Sends command for execution via Rust Core."""
        request = nexus_core_pb2.ActionRequest(
            command=command, target_files=target_files or []
        )
        try:
            response = await self.stub.ExecuteAction(request)
            return {
                "success": response.success,
                "output": response.output,
                "error": response.error,
                "backup_id": response.backup_id,
            }
        except grpc.aio.AioRpcError as e:
            return {
                "success": False,
                "error": f"gRPC Error: {e.code()} - {e.details()}",
            }

    async def simulate_command(
        self, command: str, target_files: List[str] = None
    ) -> Dict:
        """Simulates command in Rust Shadow Environment."""
        request = nexus_core_pb2.SimulationRequest(
            command=command, target_files=target_files or []
        )
        try:
            response = await self.stub.SimulateAction(request)
            return {
                "success": response.success,
                "confidence": response.confidence,
                "output": response.output,
                "error": response.error,
            }
        except grpc.aio.AioRpcError as e:
            return {
                "success": False,
                "error": f"gRPC Error: {e.code()} - {e.details()}",
                "confidence": 0.0,
            }

    async def stream_telemetry(self) -> AsyncGenerator[Dict, None]:
        """Receives realtime telemetry stream from Rust."""
        request = nexus_core_pb2.TelemetryRequest(include_processes=True)

        try:
            async for telemetry in self.stub.StreamTelemetry(request):
                yield {
                    "cpu": telemetry.cpu_usage,
                    "ram": telemetry.ram_usage,
                    "disk": telemetry.disk_usage,
                    "processes": telemetry.processes,
                }
        except grpc.aio.AioRpcError as e:
            print(f"Telemetry stream error: {e}")
            yield {"cpu": 0, "ram": 0, "disk": 0, "processes": []}

    async def set_mode(self, mode: str) -> bool:
        """Sets Rust Core mode (SAFE, DEV, AUTONOMOUS)."""
        request = nexus_core_pb2.ModeRequest(mode=mode)
        try:
            resp = await self.stub.SetMode(request)
            print(f"🛡️ Core Mode set to: {resp.current_mode}")
            return resp.success
        except grpc.aio.AioRpcError as e:
            print(f"Failed to set mode: {e}")
            return False
