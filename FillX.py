import re
import subprocess
import time
import Xlib.display
import Xlib.X

## Config
# Pretend these windows don't exist when calculating size
# of a different window.
# They can still be selected directly.
ignore_classes = []  # as reported by get_wm_class()
ignore_names = []  # as reported by get_wm_name()
# Button to alternate maximize-width or maximize-height
modifier = Xlib.X.Mod1Mask  # Alt
# Button to finish execution
done_button = Xlib.X.Button1Mask  # Left mouse button
## End config

display = Xlib.display.Display()
root = display.screen().root

def get_prop(window, prop_name):
    return window.get_full_property(display.intern_atom(prop_name), Xlib.X.AnyPropertyType).value

try:
    # xwininfo blocks until the user clicks on a window.
    xwininfo = subprocess.Popen("xwininfo", stdout=subprocess.PIPE, shell=True, bufsize=-1)
    ret = xwininfo.wait()
    target_win_info = xwininfo.stdout.read()[:-1]
    if ret != 0:
        raise subprocess.CalledProcessError(ret, "xwininfo", target_win_info)
    target_win_id = re.search('Window id: ([0-9a-fx]+)', target_win_info).group(1)
    target_win_id = int(target_win_id, 16)
except:
    target_win_id = get_prop(root, "_NET_ACTIVE_WINDOW")[0]

target_win_handle = display.create_resource_object("window", target_win_id)
target_win_frame = get_prop(target_win_handle, "_NET_FRAME_EXTENTS")

client_list_stacking = get_prop(root, "_NET_CLIENT_LIST_STACKING")

win_list = []
for win_id in reversed(client_list_stacking):
    if win_id == target_win_id:
        continue
    win_handle = display.create_resource_object("window", win_id)
    win_state = get_prop(win_handle, "_NET_WM_STATE")
    win_is_maximized = (display.intern_atom("_NET_WM_STATE_MAXIMIZED_VERT") in win_state and
                        display.intern_atom("_NET_WM_STATE_MAXIMIZED_HORZ") in win_state or
                        display.intern_atom("_NET_WM_STATE_FULLSCREEN") in win_state)
    if win_is_maximized:
        break  # ignore all windows beneath a maximized one
    win_is_hidden = (display.intern_atom("_NET_WM_STATE_MINIMIZED") in win_state or
                     display.intern_atom("_NET_WM_STATE_HIDDEN") in win_state)
    win_instance, win_class = win_handle.get_wm_class()
    win_name = win_handle.get_wm_name()
    if win_is_hidden or win_class in ignore_classes or win_name in ignore_names:
        continue  # Don't process these
    win_geometry = win_handle.get_geometry()
    # It's more reliable to translate the upper left of this window into
    # root-based coords than to use the x and y returned by get_geometry
    win_coords = win_handle.translate_coords(root, 0, 0)
    x = -1 * win_coords.x
    y = -1 * win_coords.y
    # Frame is [left, right, top, bottom]
    win_frame = get_prop(win_handle, "_NET_FRAME_EXTENTS")
    win_list.append({
        "handle": win_handle,
        "x": x - win_frame[0],
        "y": y - win_frame[2],
        "right": x + win_geometry.width + win_frame[1],
        "bottom": y + win_geometry.height + win_frame[3],
        "name": win_name})

print win_list

# workarea is [x, y, width, height]
workarea = get_prop(root, "_NET_WORKAREA")
start_rect = {
    "left": workarea[0],
    "top": workarea[1],
    "right": workarea[0] + workarea[2],
    "bottom": workarea[1] + workarea[3]
}
# While left mouse button is up:
while not root.query_pointer().mask & done_button:
    time.sleep(0.05)
    pointer_info = root.query_pointer()
    mouse = {"x": pointer_info.root_x, "y": pointer_info.root_y}
    for window in win_list:
        if (window["x"] <= mouse["x"] <= window["right"] and
                window["y"] <= mouse["y"] <= window["bottom"]):
            break  # The mouse is within this window, so try again.
    else:
        rect = start_rect.copy()
        if pointer_info.mask & modifier:  # Default: Alt is pressed
            # Search horizontally first to maximize window width.
            xy1 = "y"; xy2 = "x"; s1 = "top"; s2 = "left"; s3 = "bottom"; s4 = "right"
        else:
            xy1 = "x"; xy2 = "y"; s1 = "left"; s2 = "top"; s3 = "right"; s4 = "bottom"

        # Search either horizontally from the mouse X for the closest
        # rights and lefts of windows. These will become the left and
        # right of the new position of the target window, respectively.
        # Or, vertically for the nearest bottoms and tops --> top and
        # bottom of the new position.
        for window in win_list:
            if window[xy1] <= mouse[xy1] <= window[s3]:
                if mouse[xy2] < window[xy2] < rect[s4]:
                    rect[s4] = window[xy2]
                elif mouse[xy2] > window[s4] > rect[s2]:
                    rect[s2] = window[s4]

        # Now that we have two opposing sides - a line - we fill the
        # line out into a rectangle by finding the other sides. This
        # is trickier because a window can bound anywhere on the line,
        # rather than just in a straight line from the mouse.
        for window in win_list:
            if window[xy2] <= rect[s2] <= window[s4] or rect[s2] <= window[xy2] <= rect[s4]:
                if mouse[xy1] < window[xy1] < rect[s3]:
                    rect[s3] = window[xy1]
                elif mouse[xy1] > window[s3] > rect[s1]:
                    rect[s1] = window[s3]

        x = rect["left"]
        y = rect["top"]
        width = rect["right"] - rect["left"] - target_win_frame[0] - target_win_frame[1]
        height = rect["bottom"] - rect["top"] - target_win_frame[2] - target_win_frame[3]
        target_win_handle.configure(x=x, y=y, width=width, height=height)
