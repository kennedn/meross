import matplotlib.pyplot as plt
from functools import partial
from matplotlib.ticker import FuncFormatter, FixedLocator
from matplotlib.widgets import TextBox, Button
import numpy as np
import hashlib
import os
import requests
import argparse

class ScheduleManager:
    def __init__(self, ip_addr, device_id):
        self.ip_addr = ip_addr  # IP address of the target device
        self.device_id = device_id  # Unique device identifier
        self.key = os.environ.get("KEY")  # Secret key retrieved from environment variables
        self.schedule_data = None  # To store fetched schedule data

    def _generate_signature(self, message_id, timestamp):
        # Generate an MD5 signature for authentication
        sign_data = f"{message_id}{self.key}{timestamp}".encode()
        return hashlib.md5(sign_data).hexdigest()

    def fetch_schedule(self):
        # Fetch the current schedule from the device
        message_id = os.urandom(16).hex()  # Generate a random message ID
        timestamp = 0  # Placeholder timestamp
        sign = self._generate_signature(message_id, timestamp)  # Generate authentication signature

        # Construct the request payload
        json_data = {
            "header": {
                "from": "http://10.10.10.1/config",
                "messageId": message_id,
                "method": "GET",
                "namespace": "Appliance.Hub.Mts100.ScheduleB",
                "payloadVersion": 1,
                "sign": sign,
                "timestamp": timestamp
            },
            "payload": {
                "schedule": [
                    {"id": self.device_id}
                ]
            }
        }

        try:
            url = f"http://{self.ip_addr}/config"  # Device endpoint
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=json_data, headers=headers, timeout=3)  # Make the request
            # Extract schedule data from the response
            json = response.json()
            self.schedule_data = response.json().get("payload", {}).get("schedule", [{}])[0]
            if response.status_code != 200 or self.schedule_data.get("exception", None) is not None:
                self.schedule_data = None

        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")


    def save_schedule(self, updated_schedule):
        # Save an updated schedule to the device
        message_id = os.urandom(16).hex()  # Generate a random message ID
        timestamp = 0  # Placeholder timestamp
        sign = self._generate_signature(message_id, timestamp)  # Generate authentication signature

        # Construct the request payload
        json_data = {
            "header": {
                "from": "http://10.10.10.1/config",
                "messageId": message_id,
                "method": "SET",
                "namespace": "Appliance.Hub.Mts100.ScheduleB",
                "payloadVersion": 1,
                "sign": sign,
                "timestamp": timestamp
            },
            "payload": {
                "schedule": [
                    {
                        "id": self.device_id,
                        **updated_schedule
                    }
                ]
            }
        }

        try:
            url = f"http://{self.ip_addr}/config"  # Device endpoint
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=json_data, headers=headers, timeout=3)  # Make the request
            print(response.json())  # Print response for debugging
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")

class ScheduleVisualizer:
    def __init__(self, schedule_manager):
        self.manager = schedule_manager  # Manager to handle schedule operations
        self.selected_day = "mon"  # Default day selected for visualization
        self.dragging_point = None  # Track point dragging state
        self.last_clicked_idx = None  # Track last clicked point
        self.lock_axis = None  # Lock axis during drag
        self.start_pos = None  # Starting position of a drag
        self.buttons = []

        self.days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # Days of the week
        self.vals = self._data_to_schedule()  # Prepare initial schedule data

        plt.rcParams['toolbar'] = 'None'
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        plt.subplots_adjust(top=0.85,bottom=0.15,left=0.075,right=0.925)

        self.line, = self.ax.step([], [], where='post', marker="o", markersize=10, linestyle="-")
        self.highlight, = self.ax.plot([], [], marker='o', markersize=10, color='r')
        
        self._initialize_plot()
        self.update_graph()
        self._initialize_controls()

        self.fig.canvas.mpl_connect('button_press_event', self.on_press)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.time_textbox.on_submit(self.on_submit)
        self.temp_textbox.on_submit(self.on_submit)

    def _data_to_schedule(self):
        vals = {}
        for day in self.days:
            day_data = self.manager.schedule_data.get(day, [])
            x_vals = np.cumsum([i[0] / 60 for i in day_data])  # Convert relative minutes to absolute hours
            y_vals = [i[1] / 10 for i in day_data]  # Scale temperature values
            x_vals = [x_vals[-1] - 9999] + list(x_vals) + [x_vals[-1] + 9999] # Add virtual nodes to x axes to wrap final line
            y_vals = [y_vals[-1]] + y_vals + [y_vals[-1]] # Add virtual nodes to y axes to wrap final line
            vals[day] = {"x_vals": x_vals, "y_vals": y_vals}
        return vals


    def _schedule_to_data(self):
        data = {}
        for day in self.days:
            # Convert absolute hours to relative minutes
            relative_mins = [int(i * 60) for i in np.diff(self.vals[day]["x_vals"][1:-1],prepend=0)]
            # Convert temperatures to integer representation
            temps = [int(v*10) for v in self.vals[day]["y_vals"][1:-1]]
            data[day] = list(zip(relative_mins, temps))
        return data


    def _initialize_plot(self):
        self.ax.set_title("Temperature Schedule")
        self.ax.set_xlabel("Time (hours since midnight)")
        self.ax.set_ylabel("Temperature (°C)")
        self.ax.xaxis.set_major_formatter(FuncFormatter(self._time_formatter))
        self.ax.xaxis.set_minor_formatter(FuncFormatter(self._time_formatter))
        self.ax.yaxis.set_major_formatter(FuncFormatter(self._temp_formatter))
        self.ax.tick_params(which='major', pad=20, axis='x')
        self.ax.set_xlim(-1, 25)
        self.ax.set_ylim(4, 31)

    def _initialize_controls(self):
        self.time_textbox = TextBox(plt.axes([0.11, 0.025, 0.045, 0.05]), 'Time (hours)  ', initial='')
        self.temp_textbox = TextBox(plt.axes([0.25, 0.025, 0.045, 0.05]), 'Temp (°C)  ', initial='')

        button_height = 0.05 
        button_width = 1.0 / len(self.days)
        button_pad = 0.01
        for i, day in enumerate(self.days):
            button_ax = self.fig.add_axes([i * button_width + button_pad, 0.925, button_width - button_pad * 2, button_height])
            day_button = Button(button_ax, day.capitalize())
            day_button.on_clicked(lambda event, calling_button=day_button, day=day, cb_func=self.update_graph: self._button_handler(calling_button, lambda day=day: cb_func(day)))
            if i == 0:
                self._button_handler(day_button, lambda *args, **kwargs: None)
            self.buttons.append(day_button)

        save_button = Button(plt.axes([ 1 - button_width + button_pad, 0.025, button_width - button_pad * 2, button_height]), "Save")
        save_button.on_clicked(lambda event: self.save_schedule())
        self.buttons.append(save_button)

    def _button_handler(self, calling_button, cb_func):
        for i in range(len(self.buttons)):
            self.buttons[i].color = "silver"
        calling_button.color = "0.95"
        cb_func() 

    def _time_formatter(self, x, _):
        hours = int(x // 1)
        minutes = int((x % 1) * 60)
        return f"{hours:02}:{minutes:02}"
    
    def _temp_formatter(self, x, _):
        return f"{x:.01f}"

    def update_graph(self, day=None):
        if day:
            self.selected_day = day
        self.line.set_xdata(self.vals[self.selected_day]["x_vals"])
        self.line.set_ydata(self.vals[self.selected_day]["y_vals"])
        if self.last_clicked_idx is not None:
            self.highlight.set_xdata(self.vals[self.selected_day]["x_vals"][self.last_clicked_idx])
            self.highlight.set_ydata(self.vals[self.selected_day]["y_vals"][self.last_clicked_idx])
        self.ax.xaxis.set_major_locator(FixedLocator(self.vals[self.selected_day]["x_vals"][::2]))
        self.ax.xaxis.set_minor_locator(FixedLocator(self.vals[self.selected_day]["x_vals"][1::2]))
        self.ax.set_yticks(sorted(set(self.vals[self.selected_day]["y_vals"])))
        self.fig.canvas.draw_idle()

    def save_schedule(self):
        self.manager.save_schedule(self._schedule_to_data())

    def on_press(self, event):
        if event.inaxes != self.ax:
            return
        for i, (x, y) in enumerate(zip(self.vals[self.selected_day]["x_vals"], self.vals[self.selected_day]["y_vals"])):
            if np.hypot(event.xdata - x, event.ydata - y) < 0.5:
                self.dragging_point = i
                self.start_pos = (event.xdata, event.ydata)
                self.lock_axis = None
                break
        if self.dragging_point is not None:
            self.temp_textbox.set_val(str(self.vals[self.selected_day]["y_vals"][self.dragging_point]))
            self.time_textbox.set_val(str(self.vals[self.selected_day]["x_vals"][self.dragging_point]))
            self.last_clicked_idx = self.dragging_point
            self.update_graph()

    def on_motion(self, event):
        if self.dragging_point is None or event.inaxes != self.ax:
            return
        if self.start_pos and self.lock_axis is None:
            dx = abs(event.xdata - self.start_pos[0]) if event.xdata else 0
            dy = abs(event.ydata - self.start_pos[1]) if event.ydata else 0
            self.lock_axis = "x" if dx > dy else "y"

        if self.lock_axis == "x" and event.xdata:
            min_point = self.vals[self.selected_day]["x_vals"][self.dragging_point - 1] if self.dragging_point > 1 else 0
            max_point = self.vals[self.selected_day]["x_vals"][self.dragging_point + 1] if self.dragging_point < len(self.vals[self.selected_day]["x_vals"]) - 2 else 24
            self.vals[self.selected_day]["x_vals"][self.dragging_point] = max(min_point, min(max_point, round(event.xdata / 0.25) * 0.25))
        elif self.lock_axis == "y" and event.ydata:
            self.vals[self.selected_day]["y_vals"][self.dragging_point] = max(5, min(30, round(event.ydata / 0.5) * 0.5))
            if self.dragging_point == len(self.vals[self.selected_day]["y_vals"])-2:
                self.vals[self.selected_day]["y_vals"][0] = self.vals[self.selected_day]["y_vals"][self.dragging_point]
                self.vals[self.selected_day]["y_vals"][-1] = self.vals[self.selected_day]["y_vals"][self.dragging_point]

        if self.dragging_point is not None:
            self.temp_textbox.set_val(str(self.vals[self.selected_day]["y_vals"][self.dragging_point]))
            self.time_textbox.set_val(str(self.vals[self.selected_day]["x_vals"][self.dragging_point]))
            self.update_graph()

    def on_release(self, event):
        self.dragging_point = None
        self.lock_axis = None
        self.start_pos = None
    
    def on_submit(self, event):
        if self.last_clicked_idx is None or self.dragging_point is not None:
            return
        try:
            min_point = self.vals[self.selected_day]["x_vals"][self.last_clicked_idx-1] if self.last_clicked_idx > 0 else 0
            max_point = self.vals[self.selected_day]["x_vals"][self.last_clicked_idx+1] if self.last_clicked_idx < len(self.vals[self.selected_day]["x_vals"])-1 else 24
            new_time = max(min_point, min(max_point, round(float(self.time_textbox.text) / 0.25) * 0.25))
            new_temp = max(5, min(30, round(float(self.temp_textbox.text)/ 0.5) * 0.5)) 
            # Update the values for the last clicked node
            self.time_textbox.set_val(str(new_time))
            self.temp_textbox.set_val(str(new_temp))
            self.vals[self.selected_day]["x_vals"][self.last_clicked_idx] = new_time
            self.vals[self.selected_day]["y_vals"][self.last_clicked_idx] = new_temp
            if self.last_clicked_idx == len(self.vals[self.selected_day]["y_vals"])-2:
                self.vals[self.selected_day]["y_vals"][0] = self.vals[self.selected_day]["y_vals"][self.last_clicked_idx]
                self.vals[self.selected_day]["y_vals"][-1] = self.vals[self.selected_day]["y_vals"][self.last_clicked_idx]
            self.update_graph()
            # update_schedule_data()
        except ValueError:
            pass  # Handle invalid input gracefully


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Fetch and visualize schedule data.")
    parser.add_argument('-i', '--ip', type=str, default='192.168.1.170', help='IP address of the device (default: 192.168.1.170)')
    parser.add_argument('-d', '--device_id', type=str, required=True, help='Device ID (required)')

    # Parse arguments
    args = parser.parse_args()

    manager = ScheduleManager(args.ip, args.device_id)  # Initialize the manager with device info
    manager.fetch_schedule()  # Fetch the current schedule
    if not manager.schedule_data:
        print(f"Failed to fetch schedule data for {args.ip=},{args.device_id=}")
        exit(1)  # Exit if fetching schedule fails

    visualizer = ScheduleVisualizer(manager)  # Create the visualizer
    # Display the visualization
    plt.show()

if __name__ == "__main__":
    main()