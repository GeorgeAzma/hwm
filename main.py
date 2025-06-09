import time
import socket
import uvicorn
import sys
import ctypes
from pathlib import Path
from threading import Timer, Lock
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from HardwareMonitor.Util import (
    OpenComputer,
    HardwareTypeString,
    SensorTypeString,
    SensorValueToString,
    GroupSensorsByType,
)
from HardwareMonitor.Hardware import SensorType, IComputer, IHardware, ISensor


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    if not is_admin():
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()


# ------------------------------------------------------------------------------
SensorTypeStringPlurals = {
    SensorType.Voltage: "Voltages",
    SensorType.Current: "Currents",
    SensorType.Clock: "Clocks",
    SensorType.Load: "Loads",
    SensorType.Temperature: "Temperatures",
    SensorType.Fan: "Fans",
    SensorType.Level: "Levels",
    SensorType.Power: "Powers",
    SensorType.Frequency: "Frequencies",
    SensorType.Flow: "Flows",
    SensorType.Control: "Controls",
    SensorType.Factor: "Factors",
    SensorType.Data: "Data",
    SensorType.SmallData: "SmallData",
    SensorType.Throughput: "Throughputs",
    SensorType.TimeSpan: "TimeSpans",
    SensorType.Energy: "Energies",
    SensorType.Noise: "Noises",
}


# ------------------------------------------------------------------------------
class NodeFormatter:
    _counter = 0

    def getId(self):
        node_id = self._counter
        self._counter += 1
        return node_id

    def _makeNode(self, Text, Min="", Value="", Max="", ImageURL="", **kwargs):
        return dict(
            id=self.getId(),
            Text=Text,
            Min=Min,
            Value=Value,
            Max=Max,
            ImageURL=ImageURL,
            Children=[],
            **kwargs,
        )

    def makeSensorGroupNode(self, sensors: List[ISensor]):
        sensor_type = sensors[0].SensorType
        type_str = SensorTypeString[sensor_type]

        def makeSensorNode(sensor: ISensor):
            min_str = SensorValueToString(sensor.Min, sensor_type)
            val_str = SensorValueToString(sensor.Value, sensor_type)
            max_str = SensorValueToString(sensor.Max, sensor_type)
            return self._makeNode(
                sensor.Name,
                Min=min_str,
                Value=val_str,
                Max=max_str,
                Type=type_str,
                SensorId=sensor.Identifier.ToString(),
            )

        group_node = self._makeNode(SensorTypeStringPlurals.get(sensor_type, type_str))
        group_node["Children"].extend(map(makeSensorNode, sensors))
        return group_node

    def makeHardwareNode(self, hardware: IHardware):
        sensors_grouped = GroupSensorsByType(hardware.Sensors)
        hardware_type = HardwareTypeString[hardware.HardwareType]
        hardware_node = self._makeNode(hardware.Name, Type=hardware_type)
        hardware_node["Children"].extend(map(self.makeSensorGroupNode, sensors_grouped))
        hardware_node["Children"].extend(
            map(self.makeHardwareNode, hardware.SubHardware)
        )
        return hardware_node

    def buildNodeTree(self, computer: IComputer):
        self._counter = 0
        root_node = self._makeNode("Sensor")
        computer_node = self._makeNode(socket.gethostname())

        root_node["Children"].append(computer_node)
        computer_node["Children"].extend(map(self.makeHardwareNode, computer.Hardware))
        return root_node


# ------------------------------------------------------------------------------
class IndefiniteTimer(Timer):
    def start(self):
        self.daemon = True
        super().start()
        return self

    def run(self):
        delay = self.interval
        while not self.finished.wait(delay):
            start_time = time.perf_counter()
            self.function(*self.args, **self.kwargs)
            delay = max(0, self.interval - (time.perf_counter() - start_time))


# ------------------------------------------------------------------------------
class SensorApp:
    def __init__(self, port=8085, interval=0.2):
        self.port = port
        self.interval = interval
        self.mutex = Lock()
        self.computer = OpenComputer(all=True, time_window=interval)
        self.timer = IndefiniteTimer(interval, self.update).start()
        self.app = FastAPI()

        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allows all origins
            allow_credentials=True,
            allow_methods=["*"],  # Allows all methods
            allow_headers=["*"],  # Allows all headers
        )

        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/data.json")
        async def get_data():
            return JSONResponse(content=self.getSensors())

        @self.app.get("/", response_class=HTMLResponse)
        async def get_root():
            script_dir = Path(__file__).parent
            index_path = script_dir / "index.html"
            try:
                return index_path.read_text(encoding="utf-8")
            except (FileNotFoundError, PermissionError):
                raise HTTPException(status_code=404, detail="Index file not found")

        @self.app.get("/{filename:path}")
        async def get_static_files(filename: str):
            # Security check: prevent directory traversal
            if (
                ".." in filename
                or filename.startswith("/")
                or filename.startswith("\\")
            ):
                raise HTTPException(status_code=404, detail="File not found")

            # Get the directory where this script is located
            script_dir = Path(__file__).parent
            file_path = script_dir / filename

            # Additional security check: ensure the resolved path is within the script directory
            try:
                file_path = file_path.resolve()
                script_dir = script_dir.resolve()
                if not str(file_path).startswith(str(script_dir)):
                    raise HTTPException(status_code=404, detail="File not found")
            except (OSError, ValueError):
                raise HTTPException(status_code=404, detail="File not found")

            # Check if file exists
            if not file_path.exists() or not file_path.is_file():
                raise HTTPException(status_code=404, detail="File not found")

            # Determine content type based on file extension
            content_type = "text/plain"
            if filename.endswith(".js"):
                content_type = "application/javascript"
            elif filename.endswith(".css"):
                content_type = "text/css"
            elif filename.endswith(".html"):
                content_type = "text/html"
            elif filename.endswith(".json"):
                content_type = "application/json"
            elif filename.endswith(".png"):
                content_type = "image/png"
            elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
                content_type = "image/jpeg"
            elif filename.endswith(".gif"):
                content_type = "image/gif"
            elif filename.endswith(".svg"):
                content_type = "image/svg+xml"

            # Read and return file content
            try:
                if content_type.startswith("image/"):
                    # For binary files like images
                    with open(file_path, "rb") as f:
                        content = f.read()
                    return Response(content=content, media_type=content_type)
                else:
                    # For text files
                    content = file_path.read_text(encoding="utf-8")
                    return Response(content=content, media_type=content_type)
            except (PermissionError, OSError):
                raise HTTPException(status_code=403, detail="Access denied")

    def update(self):
        with self.mutex:
            self.computer.Update()

    def getSensors(self):
        with self.mutex:
            return NodeFormatter().buildNodeTree(self.computer)

    def serve(self):
        uvicorn.run(self.app, host="", port=self.port, log_config=None)

    def close(self):
        self.timer.cancel()


# ------------------------------------------------------------------------------
def main():
    # Check for admin privileges
    run_as_admin()

    print(f"Loading devices and sensors...")
    app = SensorApp()
    print(f"Serving on 'http://localhost:{app.port}/', press 'Ctrl + C' to stop")
    try:
        app.serve()
    except KeyboardInterrupt:
        app.close()


if __name__ == "__main__":
    run_as_admin()
    main()
