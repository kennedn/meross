import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

# Example data
data = {
    "id": "03000BDF",
    "data": [
        {
            "day": "mon",
            "min": [[0, 420], [420, 600], [600, 780], [780, 1080], [1080, 1320], [1320, 1440]],
            "temp": ["10.01", "18.02", "18.02", "18.02", "18.02", "10.01"],
        }
    ],
}

# Extract relevant data
day_data = data["data"][0]
x_vals = [interval[0] / 60 for interval in day_data["min"]]  # Convert start time to hours since midnight
y_vals = [float(temp) for temp in day_data["temp"]]

# Helper to format y-axis as time
def time_formatter(x, _):
    hours = int(x // 1)
    minutes = int((x % 1) * 60)
    return f"{hours:02}:{minutes:02}"


# Create the plot
fig, ax = plt.subplots(figsize=(10, 6))
ax.set_title(f"Temperature Schedule ({data['id']})")
ax.set_xlabel("Time (hours since midnight)")
ax.set_ylabel("Temperature (°C)")
ax.grid(True)

# Set y-axis to show time format
ax.yaxis.set_major_formatter(FuncFormatter(time_formatter))

# Plot initial data
(line,) = ax.plot(x_vals, y_vals, marker="o", markersize=10, linestyle="-", label=day_data["day"])
ax.legend()

# State for dragging
dragging_point = None
lock_axis = None
start_pos = None  # Initial mouse press position


def on_press(event):
    """Handle mouse press to identify a point to drag."""
    global dragging_point, lock_axis, start_pos
    if event.inaxes != ax:
        return
    # Check proximity to points
    for i, (x, y) in enumerate(zip(x_vals, y_vals)):
        if np.hypot(event.xdata - x, event.ydata - y) < 0.2:  # Proximity threshold
            dragging_point = i
            start_pos = (event.xdata, event.ydata)
            lock_axis = None  # Reset lock until movement
            break


def on_motion(event):
    """Handle mouse motion to drag a point."""
    global dragging_point, lock_axis
    if dragging_point is None or event.inaxes != ax:
        return
    if start_pos is not None and lock_axis is None:
        # Determine axis lock based on initial movement direction
        dx = abs(event.xdata - start_pos[0]) if event.xdata is not None else 0
        dy = abs(event.ydata - start_pos[1]) if event.ydata is not None else 0
        lock_axis = "x" if dx > dy else "y"

    if lock_axis == "x" and event.xdata is not None:
        # Update x (time)
        x_vals[dragging_point] = max(0, min(24, event.xdata))  # Constrain x to valid hours
    elif lock_axis == "y" and event.ydata is not None:
        # Update y (temperature)
        y_vals[dragging_point] = event.ydata

    # Update line data
    line.set_xdata(x_vals)
    line.set_ydata(y_vals)
    fig.canvas.draw_idle()


def on_release(event):
    """Handle mouse release to stop dragging."""
    global dragging_point, lock_axis, start_pos
    dragging_point = None
    lock_axis = None
    start_pos = None


# Connect events
fig.canvas.mpl_connect("button_press_event", on_press)
fig.canvas.mpl_connect("motion_notify_event", on_motion)
fig.canvas.mpl_connect("button_release_event", on_release)

plt.show()

