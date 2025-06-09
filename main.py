# coding: utf-8

import json
import time
import socket
import uvicorn
from pathlib import Path
from threading import Timer, Lock
from typing import List
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from HardwareMonitor.Util import OpenComputer, HardwareTypeString, SensorTypeString, SensorValueToString, GroupSensorsByType
from HardwareMonitor.Hardware import SensorType, IComputer, IHardware, ISensor


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
    SensorType.Noise: "Noises"
}


# ------------------------------------------------------------------------------
class NodeFormatter():
    _counter = 0
    def getId(self):
        node_id = self._counter
        self._counter += 1
        return node_id

    def _makeNode(self, Text, Min="", Value="", Max="", ImageURL="", **kwargs):
        return dict(id=self.getId(), Text=Text, Min=Min, Value=Value, Max=Max,
                    ImageURL=ImageURL, Children=[], **kwargs)

    def makeSensorGroupNode(self, sensors: List[ISensor]):
        sensor_type = sensors[0].SensorType
        type_str    = SensorTypeString[sensor_type]
        def makeSensorNode(sensor: ISensor):
            min_str = SensorValueToString(sensor.Min,   sensor_type)
            val_str = SensorValueToString(sensor.Value, sensor_type)
            max_str = SensorValueToString(sensor.Max,   sensor_type)
            return self._makeNode(sensor.Name, Min=min_str, Value=val_str, Max=max_str, Type=type_str,
                                  SensorId=sensor.Identifier.ToString())

        group_node = self._makeNode(SensorTypeStringPlurals.get(sensor_type, type_str))
        group_node["Children"].extend(map(makeSensorNode, sensors))
        return group_node

    def makeHardwareNode(self, hardware: IHardware):
        sensors_grouped = GroupSensorsByType(hardware.Sensors)
        hardware_type   = HardwareTypeString[hardware.HardwareType]
        hardware_node   = self._makeNode(hardware.Name, Type=hardware_type)
        hardware_node["Children"].extend(map(self.makeSensorGroupNode, sensors_grouped))
        hardware_node["Children"].extend(map(self.makeHardwareNode, hardware.SubHardware))
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
class SensorApp():
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
            return Path("index.html").read_text(encoding="utf-8")

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
    print(f"Loading devices and sensors...")
    app = SensorApp()
    print(f"Serving on 'http://localhost:{app.port}/', press 'Ctrl + C' to stop")
    try:
        app.serve()
    except KeyboardInterrupt:
        app.close()

if __name__ == "__main__":
    main()